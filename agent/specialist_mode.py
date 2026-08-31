"""
Specialist Mode: the actual differentiator (see the build brief, Section 1).
Two-sided resting-limit quoting on near-the-money contracts across a small
basket, priced off live Black-Scholes theoretical value (IV solved from the
contract's own NBBO mid each cycle), inside-NBBO, replaced every cycle as
underlying/IV move, with immediate delta hedging on every fill.

One call cycle == one pass over every symbol in the approved MarketPlan:
  1. mark the underlying + refresh its position snapshot
  2. pick 1 ATM call + 1 ATM put in the DTE window
  3. for each contract: reconcile fills on our previous resting orders first
     (hedge immediately if anything filled), then cancel what's left resting,
     reprice off fresh NBBO mid-IV, risk-gate the new bid/ask size, and post
     fresh resting orders inside the NBBO.

Cancel-and-replace each cycle (rather than a partial PATCH-based reprice) is
a deliberate MVP simplification -- correct and simple, at the cost of extra
order churn. Call this out in the write-up.
"""
from datetime import datetime, timedelta, timezone

from agent import clients, ledger, risk_gate
from agent.config import RISK, RISK_FREE_RATE
from agent.occ import parse_occ_symbol
from agent.pricing import implied_volatility, position_dollar_greeks, price_and_greeks

_TICK = 0.01


def _pick_atm_contracts(symbol: str, underlying_price: float) -> list[tuple[str, object]]:
    """Returns up to 2 (occ_symbol, ParsedOccSymbol) pairs: nearest-ATM call
    and nearest-ATM put with an expiration inside the configured DTE window."""
    from alpaca.data.requests import OptionChainRequest

    today = datetime.now(timezone.utc).date()
    lo = today + timedelta(days=RISK.quote_dte_min)
    hi = today + timedelta(days=RISK.quote_dte_max)
    band = underlying_price * RISK.quote_moneyness_band_pct

    try:
        chain = clients.option_data_client.get_option_chain(OptionChainRequest(underlying_symbol=symbol))
    except Exception as exc:  # noqa: BLE001
        print(f"[specialist] {symbol}: chain fetch failed: {exc}")
        return []

    parsed_by_type: dict[str, list[tuple[str, object]]] = {"call": [], "put": []}
    for occ_symbol in chain:
        try:
            p = parse_occ_symbol(symbol, occ_symbol)
        except ValueError:
            continue
        if lo <= p.expiration <= hi and abs(p.strike - underlying_price) <= band:
            parsed_by_type[p.option_type].append((occ_symbol, p))

    out = []
    for option_type in ("call", "put"):
        candidates = parsed_by_type[option_type]
        if not candidates:
            continue
        best = min(candidates, key=lambda pair: abs(pair[1].strike - underlying_price))
        out.append(best)
    return out


def _reconcile_fills(order_row: dict, contract_greeks, underlying_symbol: str, underlying_price: float) -> None:
    """Checks one previously-placed order for a NEW fill since we last looked,
    logs it, and immediately submits the offsetting equity hedge."""
    alpaca_order_id = order_row["alpaca_order_id"]
    if not alpaca_order_id:
        return
    try:
        live = clients.trading_client.get_order_by_id(alpaca_order_id)
    except Exception as exc:  # noqa: BLE001
        print(f"[specialist] could not fetch order {alpaca_order_id}: {exc}")
        return

    filled_qty = int(float(live.filled_qty or 0))
    already_recorded = ledger.filled_qty_for_order(order_row["id"])
    new_fill_qty = filled_qty - already_recorded
    if new_fill_qty <= 0:
        if live.status not in ("new", "accepted", "pending_new", "partially_filled"):
            ledger.update_order_status(order_row["id"], str(live.status))
        return

    fill_price = float(live.filled_avg_price or 0)
    side = order_row["side"]
    symbol = order_row["symbol"]

    fill_id = ledger.log_fill(order_row["id"], "specialist", symbol, side, new_fill_qty, fill_price)
    ledger.update_order_status(order_row["id"], str(live.status), alpaca_order_id=alpaca_order_id)

    inv = ledger.get_specialist_inventory(symbol)
    signed_delta_qty = new_fill_qty if side == "buy" else -new_fill_qty
    old_qty = inv["qty"]
    new_qty = old_qty + signed_delta_qty
    new_avg = fill_price if old_qty == 0 else ((inv["avg_price"] * abs(old_qty)) + (fill_price * new_fill_qty)) / max(abs(new_qty), 1)
    ledger.upsert_specialist_inventory(symbol, underlying_symbol, new_qty, new_avg)

    dollar_greeks = position_dollar_greeks(contract_greeks, new_qty, underlying_price)
    ledger.log_position_snapshot(
        "specialist", symbol, underlying_symbol, new_qty,
        dollar_greeks["delta_dollars"], dollar_greeks["gamma_shares_per_dollar"],
        dollar_greeks["vega_dollars"], dollar_greeks["theta_dollars"],
        notional=abs(new_qty) * contract_greeks.price * 100,
    )

    # immediately flatten the delta this specific fill introduced: one option
    # contract's delta approximates (delta * 100) equivalent underlying shares.
    shares_equivalent_from_fill = contract_greeks.delta * 100 * signed_delta_qty
    hedge_shares = -round(shares_equivalent_from_fill)
    if hedge_shares != 0:
        eq = ledger.get_equity_inventory(underlying_symbol)
        delta_before = eq["qty"]
        try:
            order = clients.place_equity_market_order(
                underlying_symbol, "buy" if hedge_shares > 0 else "sell", abs(hedge_shares)
            )
            hedge_price = float(order.filled_avg_price) if getattr(order, "filled_avg_price", None) else underlying_price
        except Exception as exc:  # noqa: BLE001
            print(f"[specialist] hedge order failed for {underlying_symbol}: {exc}")
            ledger.log_risk_event("reject", f"hedge order failed: {exc}", mode="specialist")
            return
        new_eq_qty = delta_before + hedge_shares
        new_eq_avg = hedge_price if delta_before == 0 else ((eq["avg_price"] * abs(delta_before)) + (hedge_price * abs(hedge_shares))) / max(abs(new_eq_qty), 1)
        ledger.upsert_equity_inventory(underlying_symbol, new_eq_qty, new_eq_avg)
        ledger.log_hedge(fill_id, underlying_symbol, "buy" if hedge_shares > 0 else "sell", abs(hedge_shares),
                          hedge_price, delta_before, new_eq_qty, alpaca_order_id=str(getattr(order, "id", "")))
        ledger.log_position_snapshot("specialist", underlying_symbol, underlying_symbol, new_eq_qty,
                                      delta_dollars=new_eq_qty * hedge_price, gamma=0, vega_dollars=0,
                                      theta_dollars=0, notional=abs(new_eq_qty) * hedge_price)


def _quote_contract(occ_symbol: str, underlying_symbol: str, underlying_price: float, spread_bps: float,
                     halt_new_entries: bool = False) -> None:
    nbbo = clients.get_option_nbbo(occ_symbol)
    if nbbo is None:
        return
    bid, ask = nbbo
    mid = (bid + ask) / 2.0
    parsed = parse_occ_symbol(underlying_symbol, occ_symbol)
    T = max((parsed.expiration - datetime.now(timezone.utc).date()).days, 1) / 365.0

    iv = implied_volatility(mid, underlying_price, parsed.strike, T, RISK_FREE_RATE, parsed.option_type)
    if iv is None:
        return
    greeks = price_and_greeks(underlying_price, parsed.strike, T, RISK_FREE_RATE, iv, parsed.option_type)

    # reconcile any fills on last cycle's resting orders for this contract before touching them
    for row in ledger.recent("orders", limit=50):
        if row["symbol"] == occ_symbol and row["mode"] == "specialist" and row["status"] in ("new", "partially_filled"):
            _reconcile_fills(row, greeks, underlying_symbol, underlying_price)

    for row in ledger.recent("orders", limit=50):
        if row["symbol"] == occ_symbol and row["mode"] == "specialist" and row["alpaca_order_id"] and \
           row["status"] in ("new", "partially_filled"):
            clients.cancel_order(row["alpaca_order_id"])
            ledger.update_order_status(row["id"], "cancelled")

    if halt_new_entries:
        return  # fills above are already reconciled + hedged; just don't post new resting quotes

    half_width = mid * (spread_bps / 2.0) / 10000.0
    target_bid = max(bid, mid - half_width)
    target_ask = min(ask, mid + half_width)
    target_bid = min(target_bid, ask - _TICK)
    target_ask = max(target_ask, bid + _TICK)
    if target_bid >= target_ask:
        return

    inv = ledger.get_specialist_inventory(occ_symbol)
    greeks_totals = ledger.portfolio_greeks_now()

    if risk_gate.flatten_required(greeks_totals["delta_dollars"]):
        print(f"[specialist] {occ_symbol}: portfolio delta over cap, skipping new quotes this cycle")
        return

    equity = float(clients.trading_client.get_account().equity)
    notional_per_contract = mid * 100

    for side, price in (("buy", target_bid), ("sell", target_ask)):
        signed_qty_for_side = 1 if side == "buy" else -1
        incremental = position_dollar_greeks(greeks, signed_qty_for_side, underlying_price)
        approval = risk_gate.pretrade_gate_specialist(
            symbol=occ_symbol, underlying=underlying_symbol, side=side,
            requested_qty=RISK.min_quote_size, equity=equity, underlying_price=underlying_price,
            option_notional_per_contract=notional_per_contract,
            current_underlying_notional=abs(inv["qty"]) * notional_per_contract,
            portfolio_delta_dollars=greeks_totals["delta_dollars"],
            portfolio_vega_dollars=greeks_totals["vega_dollars"],
            portfolio_gamma_shares_per_dollar=greeks_totals["gamma"],
            incremental_greeks=incremental,
        )
        if approval.approved_qty <= 0:
            continue
        order_id = ledger.log_order("specialist", occ_symbol, side, approval.approved_qty, "limit", price, "new")
        try:
            order = clients.place_option_limit_order(occ_symbol, side, approval.approved_qty, price)
            ledger.update_order_status(order_id, "new", alpaca_order_id=str(order.id))
        except Exception as exc:  # noqa: BLE001
            print(f"[specialist] order placement failed for {occ_symbol} {side}: {exc}")
            ledger.update_order_status(order_id, "rejected")
            ledger.log_risk_event("reject", f"order placement failed: {exc}", mode="specialist")


def run_specialist_cycle(approved_plan: dict, halt_new_entries: bool = False) -> None:
    for symbol in approved_plan["symbols"]:
        underlying_price = clients.get_underlying_mid(symbol)
        if underlying_price is None:
            print(f"[specialist] {symbol}: no underlying quote, skipping")
            continue

        eq = ledger.get_equity_inventory(symbol)
        ledger.log_position_snapshot("specialist", symbol, symbol, eq["qty"],
                                      delta_dollars=eq["qty"] * underlying_price, gamma=0, vega_dollars=0,
                                      theta_dollars=0, notional=abs(eq["qty"]) * underlying_price)

        spread_bps = approved_plan["target_spread_bps"].get(symbol, RISK.target_spread_bps)
        for occ_symbol, _parsed in _pick_atm_contracts(symbol, underlying_price):
            _quote_contract(occ_symbol, symbol, underlying_price, spread_bps, halt_new_entries=halt_new_entries)
