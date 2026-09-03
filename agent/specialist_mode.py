"""
Specialist Mode: the actual differentiator (see the build brief, Section 1).
Inventory-driven, one-sided-at-a-time resting-limit quoting on near-the-money
**puts** across a small basket, priced off live Black-Scholes theoretical
value (IV solved from the contract's own NBBO mid each cycle), inside-NBBO,
replaced every cycle as underlying/IV move, with the book's equity hedge
rebalanced to its target delta every cycle.

Two real platform constraints, found live rather than assumed, shaped this:

1. **Puts only, not puts-and-calls.** Alpaca rejects a naked short call
   ("account not eligible to trade uncovered option contracts") unless it's
   covered by 100 held shares per contract or built as a recognized spread.
   A short put is cash-secured (bounded risk, covered by cash) and Alpaca
   allows it as a plain single-leg order. Convexity Mode already covers
   call-side exposure via spreads.
2. **One side per contract per cycle, not both at once.** Alpaca's
   wash-trade protection blocks a resting buy AND a resting sell open on
   the SAME contract simultaneously ("cannot open a short sell while a long
   buy order is open") -- literally the mechanic of posting two live prices
   on one instrument at once. `_pick_quote_side()` instead quotes whichever
   side moves inventory toward flat (sell when long, buy when short,
   alternating when flat) -- still genuine liquidity provision and
   spread-capture over the life of a position, just not two simultaneous
   prices on one contract in the same instant.

See docs/decisions.md D-013 for the full reasoning behind both.

One call cycle == one pass over every symbol in the approved MarketPlan:
  1. pick each symbol's nearest-ATM put in the DTE window
  2. reconcile fills GLOBALLY across every open Specialist order (not just
     ones for contracts still selected this cycle -- a contract that fills
     and then falls off the ATM selection must still be caught) and cancel
     whatever's left resting
  3. rebalance each underlying's equity hedge to its TARGET delta (the sum
     of every currently-held put's delta on that underlying), not by
     incrementally hedging each fill in isolation -- this is what makes a
     position that closes out via the book's own opposite-side fill
     correctly unwind its hedge too, instead of leaving it orphaned
  4. reprice and post a fresh one-sided quote for this cycle's selection

Cancel-and-replace each cycle (rather than a partial PATCH-based reprice) is
a deliberate MVP simplification -- correct and simple, at the cost of extra
order churn. Call this out in the write-up.
"""
from datetime import datetime, timedelta, timezone

from agent import clients, ledger, risk_gate
from agent.config import RISK, RISK_FREE_RATE
from agent.occ import parse_occ_symbol, underlying_from_occ_symbol
from agent.pricing import implied_volatility, position_dollar_greeks, price_and_greeks

_TICK = 0.01


def _pick_atm_put(symbol: str, underlying_price: float) -> tuple[str, object] | None:
    """Returns (occ_symbol, ParsedOccSymbol) for the nearest-ATM put with an
    expiration inside the configured DTE window, or None."""
    from alpaca.data.requests import OptionChainRequest

    today = datetime.now(timezone.utc).date()
    lo = today + timedelta(days=RISK.quote_dte_min)
    hi = today + timedelta(days=RISK.quote_dte_max)
    band = underlying_price * RISK.quote_moneyness_band_pct

    try:
        chain = clients.option_data_client.get_option_chain(OptionChainRequest(underlying_symbol=symbol))
    except Exception as exc:  # noqa: BLE001
        print(f"[specialist] {symbol}: chain fetch failed: {exc}")
        return None

    candidates = []
    for occ_symbol in chain:
        try:
            p = parse_occ_symbol(symbol, occ_symbol)
        except ValueError:
            continue
        # OTM puts only (strike <= spot). A symmetric band picks in-the-money
        # puts, whose delta approaches -1.0: one ITM SPY contract is ~$75k of
        # delta against a $25k book cap, so the risk gate clamps it to zero and
        # we never trade. ITM puts also demand enormous cash-secured-put
        # buying power (observed live: $22k-$37k required for a single
        # contract). Quoting OTM is both risk-sane and what a market maker
        # actually wants to be short.
        in_band = 0 <= (underlying_price - p.strike) <= band
        if p.option_type == "put" and lo <= p.expiration <= hi and in_band:
            candidates.append((occ_symbol, p))

    if not candidates:
        return None
    return min(candidates, key=lambda pair: abs(pair[1].strike - underlying_price))


def compute_quote_prices(bid: float, ask: float, mid: float, spread_bps: float,
                          tick: float = _TICK) -> tuple[float, float] | None:
    """Target (bid, ask) for a resting two-sided quote, clamped inside the
    real NBBO and guaranteed to be at least one tick apart AFTER rounding to
    the cent -- not just at float precision. Orders are placed at
    round(price, 2) independently per side (clients.py), so two prices that
    are "distinct" at float precision (e.g. 7.278 vs 7.282) can collapse to
    the same cent (7.28 == 7.28) once each is rounded on its own. Alpaca
    correctly rejects that as a wash trade (a market maker can't quote a
    $7.28/$7.28 market) -- found by running this live against a real paper
    account. Returns None if the NBBO itself is degenerate (ask <= bid --
    bad data, never quote against it)."""
    if ask <= bid:
        return None
    half_width = mid * (spread_bps / 2.0) / 10000.0
    target_bid = max(bid, mid - half_width)
    target_ask = min(ask, mid + half_width)
    target_bid = min(target_bid, ask - tick)
    target_ask = max(target_ask, bid + tick)

    target_bid = round(target_bid, 2)
    target_ask = round(target_ask, 2)
    if target_ask - target_bid < tick:
        if round(target_bid - tick, 2) >= round(bid, 2):
            target_bid = round(target_bid - tick, 2)
        elif round(target_ask + tick, 2) <= round(ask, 2):
            target_ask = round(target_ask + tick, 2)
        else:
            return None
    if target_bid >= target_ask:
        return None
    return target_bid, target_ask


def _reconcile_all_open_orders() -> None:
    """Global fill reconciliation across EVERY open Specialist order, then
    cancels whatever's still resting -- deliberately not scoped to whatever
    contracts happen to be selected this cycle. Found live: a contract that
    fills and then falls out of nearest-ATM selection next cycle was never
    revisited by the old per-contract-scoped version, leaving a real fill
    unhedged indefinitely."""
    for row in ledger.recent("orders", limit=200):
        if row["mode"] != "specialist" or row["status"] not in ("new", "partially_filled"):
            continue
        alpaca_order_id = row["alpaca_order_id"]
        if not alpaca_order_id:
            continue
        try:
            live = clients.trading_client.get_order_by_id(alpaca_order_id)
        except Exception as exc:  # noqa: BLE001
            print(f"[specialist] could not fetch order {alpaca_order_id}: {exc}")
            continue

        filled_qty = int(float(live.filled_qty or 0))
        already_recorded = ledger.filled_qty_for_order(row["id"])
        new_fill_qty = filled_qty - already_recorded
        if new_fill_qty > 0:
            fill_price = float(live.filled_avg_price or 0)
            occ_symbol, side = row["symbol"], row["side"]
            ledger.log_fill(row["id"], "specialist", occ_symbol, side, new_fill_qty, fill_price)

            inv = ledger.get_specialist_inventory(occ_symbol)
            signed = new_fill_qty if side == "buy" else -new_fill_qty
            old_qty = inv["qty"]
            new_qty = old_qty + signed
            new_avg = fill_price if old_qty == 0 else (
                (inv["avg_price"] * abs(old_qty)) + (fill_price * new_fill_qty)
            ) / max(abs(new_qty), 1)
            underlying = underlying_from_occ_symbol(occ_symbol)
            ledger.upsert_specialist_inventory(occ_symbol, underlying, new_qty, new_avg)
            if new_qty == 0:
                # portfolio_greeks_now() aggregates the LATEST position_snapshot
                # per symbol -- a position that closes to zero must get an
                # explicit zero snapshot here, or its last (nonzero) snapshot
                # keeps counting toward portfolio risk caps forever. Found live.
                ledger.log_position_snapshot("specialist", occ_symbol, underlying, 0,
                                              delta_dollars=0, gamma=0, vega_dollars=0, theta_dollars=0, notional=0)

        terminal_status = str(live.status)
        if terminal_status in ("filled", "canceled", "expired", "rejected"):
            ledger.update_order_status(row["id"], terminal_status)
        else:
            try:
                clients.cancel_order(alpaca_order_id)
            except Exception as exc:  # noqa: BLE001
                print(f"[specialist] cancel failed for {alpaca_order_id}: {exc}")
            ledger.update_order_status(row["id"], "cancelled")


def _rebalance_hedge(underlying: str, underlying_price: float) -> None:
    """Sets the equity hedge to the CURRENT total delta of every held
    put on this underlying -- not an incremental per-fill adjustment. This
    is what makes a position that closes via the book's own opposite-side
    fill correctly unwind its hedge too, rather than leaving it orphaned
    (found live: exactly this happened before this fix existed)."""
    today = datetime.now(timezone.utc).date()
    target_shares = 0.0
    for pos in ledger.all_specialist_inventory():
        if pos["underlying"] != underlying:
            continue
        occ_symbol = pos["symbol"]
        try:
            parsed = parse_occ_symbol(underlying, occ_symbol)
        except ValueError:
            continue
        nbbo = clients.get_option_nbbo(occ_symbol)
        if nbbo is None:
            continue
        mid = sum(nbbo) / 2.0
        T = max((parsed.expiration - today).days, 1) / 365.0
        iv = implied_volatility(mid, underlying_price, parsed.strike, T, RISK_FREE_RATE, parsed.option_type)
        if iv is None:
            continue
        greeks = price_and_greeks(underlying_price, parsed.strike, T, RISK_FREE_RATE, iv, parsed.option_type)
        target_shares += greeks.delta * 100 * pos["qty"]

        # refresh this position's snapshot every cycle (not just at fill
        # time) so portfolio_greeks_now() reflects current market data, not
        # whatever Greeks happened to be true when it last filled.
        dollar_greeks = position_dollar_greeks(greeks, pos["qty"], underlying_price)
        ledger.log_position_snapshot("specialist", occ_symbol, underlying, pos["qty"],
                                      dollar_greeks["delta_dollars"], dollar_greeks["gamma_shares_per_dollar"],
                                      dollar_greeks["vega_dollars"], dollar_greeks["theta_dollars"],
                                      notional=abs(pos["qty"]) * greeks.price * 100)

    target_shares = -round(target_shares)
    eq = ledger.get_equity_inventory(underlying)
    diff = target_shares - eq["qty"]
    if diff == 0:
        return

    # Some paper accounts reject a single equity order that would cross
    # through zero (flip net long to net short or vice versa) with
    # "insufficient qty available" -- found live. Submitting a flatten leg
    # immediately followed by an opening leg also races the first order's
    # settlement (also found live: "held_for_orders" still shows the
    # about-to-be-sold shares as unavailable a moment later). Simplest safe
    # fix: only flatten to zero THIS cycle when crossing the sign; the
    # remainder is a clean flat-to-new-direction order next cycle, once the
    # first leg has settled.
    if eq["qty"] != 0 and (eq["qty"] > 0) != (target_shares > 0) and target_shares != 0:
        legs = [("sell" if eq["qty"] > 0 else "buy", abs(eq["qty"]))]
    else:
        legs = [("buy" if diff > 0 else "sell", abs(diff))]

    running_qty, running_avg = eq["qty"], eq["avg_price"]
    for side, qty in legs:
        if qty == 0:
            continue
        try:
            order = clients.place_equity_market_order(underlying, side, qty)
            hedge_price = float(order.filled_avg_price) if getattr(order, "filled_avg_price", None) else underlying_price
        except Exception as exc:  # noqa: BLE001
            print(f"[specialist] hedge rebalance leg failed for {underlying}: {exc}")
            ledger.log_risk_event("reject", f"hedge rebalance leg failed for {underlying}: {exc}", mode="specialist")
            continue

        signed_qty = qty if side == "buy" else -qty
        new_qty = running_qty + signed_qty
        new_avg = hedge_price if running_qty == 0 else (
            (running_avg * abs(running_qty)) + (hedge_price * qty)
        ) / max(abs(new_qty), 1)
        ledger.upsert_equity_inventory(underlying, new_qty, new_avg)
        ledger.log_hedge(None, underlying, side, qty, hedge_price,
                          delta_before=running_qty, delta_after=new_qty, alpaca_order_id=str(getattr(order, "id", "")))
        ledger.log_position_snapshot("specialist", underlying, underlying, new_qty,
                                      delta_dollars=new_qty * hedge_price, gamma=0, vega_dollars=0, theta_dollars=0,
                                      notional=abs(new_qty) * hedge_price)
        running_qty, running_avg = new_qty, new_avg


def _pick_quote_side(occ_symbol: str, current_qty: int) -> str:
    """Alpaca's wash-trade protection blocks a resting buy AND a resting
    sell open on the SAME contract at once ("cannot open a short sell while
    a long buy order is open") -- found live, and it rules out literally
    posting both sides of a single-contract quote simultaneously. Instead:
    quote whichever side moves inventory toward flat (sell when long, buy
    when short), and alternate when already flat, based on the last side
    quoted for this contract. Still genuine two-sided liquidity provision
    over the life of a position -- just not two live prices on one contract
    in the same instant."""
    if current_qty > 0:
        return "sell"
    if current_qty < 0:
        return "buy"
    for row in ledger.recent("orders", limit=200):
        if row["symbol"] == occ_symbol and row["mode"] == "specialist":
            return "sell" if row["side"] == "buy" else "buy"
    return "buy"


def _quote_put(occ_symbol: str, underlying_symbol: str, underlying_price: float, spread_bps: float) -> None:
    nbbo = clients.get_option_nbbo(occ_symbol)
    if nbbo is None:
        return
    bid, ask = nbbo
    mid = (bid + ask) / 2.0
    parsed = parse_occ_symbol(underlying_symbol, occ_symbol)
    T = max((parsed.expiration - datetime.now(timezone.utc).date()).days, 1) / 365.0

    iv = implied_volatility(mid, underlying_price, parsed.strike, T, RISK_FREE_RATE, "put")
    if iv is None:
        return
    greeks = price_and_greeks(underlying_price, parsed.strike, T, RISK_FREE_RATE, iv, "put")

    quote = compute_quote_prices(bid, ask, mid, spread_bps)
    if quote is None:
        return
    target_bid, target_ask = quote

    inv = ledger.get_specialist_inventory(occ_symbol)
    greeks_totals = ledger.portfolio_greeks_now()

    if risk_gate.flatten_required(greeks_totals["delta_dollars"]):
        print(f"[specialist] {occ_symbol}: portfolio delta over cap, skipping new quotes this cycle")
        return

    equity = float(clients.trading_client.get_account().equity)
    notional_per_contract = mid * 100

    side = _pick_quote_side(occ_symbol, inv["qty"])
    price = target_bid if side == "buy" else target_ask
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
        return
    order_id = ledger.log_order("specialist", occ_symbol, side, approval.approved_qty, "limit", price, "new")
    try:
        order = clients.place_option_limit_order(occ_symbol, side, approval.approved_qty, price)
        ledger.update_order_status(order_id, "new", alpaca_order_id=str(order.id))
    except Exception as exc:  # noqa: BLE001
        print(f"[specialist] order placement failed for {occ_symbol} {side}: {exc}")
        ledger.update_order_status(order_id, "rejected")
        ledger.log_risk_event("reject", f"order placement failed: {exc}", mode="specialist")


def run_specialist_cycle(approved_plan: dict, halt_new_entries: bool = False) -> None:
    underlying_prices: dict[str, float] = {}
    selected: dict[str, tuple[str, object]] = {}  # occ_symbol -> (underlying, parsed)

    for symbol in approved_plan["symbols"]:
        underlying_price = clients.get_underlying_mid(symbol)
        if underlying_price is None:
            print(f"[specialist] {symbol}: no underlying quote, skipping")
            continue
        underlying_prices[symbol] = underlying_price
        ledger.record_underlying_mark(symbol, underlying_price)

        eq = ledger.get_equity_inventory(symbol)
        ledger.log_position_snapshot("specialist", symbol, symbol, eq["qty"],
                                      delta_dollars=eq["qty"] * underlying_price, gamma=0, vega_dollars=0,
                                      theta_dollars=0, notional=abs(eq["qty"]) * underlying_price)

        pick = _pick_atm_put(symbol, underlying_price)
        if pick is not None:
            occ_symbol, parsed = pick
            selected[occ_symbol] = (symbol, parsed)

    # global fill reconciliation + cancel everything resting, BEFORE rebalancing hedges or requoting
    _reconcile_all_open_orders()

    for symbol, underlying_price in underlying_prices.items():
        _rebalance_hedge(symbol, underlying_price)

    if halt_new_entries:
        return  # fills above are reconciled and hedges rebalanced; just don't post new resting quotes

    for occ_symbol, (symbol, _parsed) in selected.items():
        spread_bps = approved_plan["target_spread_bps"].get(symbol, RISK.target_spread_bps)
        _quote_put(occ_symbol, symbol, underlying_prices[symbol], spread_bps)
