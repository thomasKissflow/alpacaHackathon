"""
Monitor Agent: manages every open Convexity Mode position in the ledger.
Closes a position when it hits the profit target, the stop loss, or is about
to expire (defined-risk exits, all pre-committed -- not discretionary).
"""
from datetime import datetime, timezone

from alpaca.data.requests import OptionLatestQuoteRequest
from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
from alpaca.trading.requests import LimitOrderRequest, OptionLegRequest

from agent import ledger
from agent.clients import option_data_client, trading_client
from agent.config import RISK
from agent.occ import parse_occ_symbol


def _net_debit_to_close(legs: list[dict]) -> float | None:
    symbols = [leg["symbol"] for leg in legs]
    quotes = option_data_client.get_option_latest_quote(OptionLatestQuoteRequest(symbol_or_symbols=symbols))

    total = 0.0
    for leg in legs:
        quote = quotes.get(leg["symbol"])
        if quote is None:
            return None
        if leg["side"] == "sell":  # we're short this leg -> closing = buy at ask
            price = getattr(quote, "ask_price", None)
            if price is None:
                return None
            total += price
        else:  # we're long this leg -> closing = sell at bid
            price = getattr(quote, "bid_price", None)
            if price is None:
                return None
            total -= price
    return total


def _close(record: dict, net_debit: float) -> None:
    legs = [
        OptionLegRequest(
            symbol=leg["symbol"],
            side=OrderSide.BUY if leg["side"] == "sell" else OrderSide.SELL,
            ratio_qty=leg["ratio_qty"],
        )
        for leg in record["legs"]
    ]
    order_id = ledger.log_order(
        "convexity", record["underlying"], "mleg_close", 1, "mleg_limit",
        round(max(net_debit, 0.0), 2), "new", legs=record["legs"], note=f"close {record['strategy_type']}",
    )
    order_req = LimitOrderRequest(
        qty=1,
        order_class=OrderClass.MLEG,
        time_in_force=TimeInForce.DAY,
        legs=legs,
        limit_price=round(max(net_debit, 0.0), 2),
    )
    order = trading_client.submit_order(order_req)
    ledger.update_order_status(order_id, "new", alpaca_order_id=str(order.id))


def run_monitor() -> list[dict]:
    """Returns a list of decision log entries for this cycle (closed/held/errored)."""
    positions = ledger.open_convexity_positions()
    log_entries = []
    today = datetime.now(timezone.utc).date()

    for record in positions:
        net_debit = _net_debit_to_close(record["legs"])
        expiration = parse_occ_symbol(record["underlying"], record["legs"][0]["symbol"]).expiration
        days_to_exp = (expiration - today).days

        if net_debit is None:
            log_entries.append({"action": "hold", "strategy_id": record["strategy_id"], "reason": "quote unavailable"})
            continue

        entry_credit = record["entry_credit"]
        pnl = entry_credit - net_debit
        profit_target = RISK.profit_target_pct_of_credit * entry_credit
        stop_loss_level = RISK.stop_loss_multiple_of_credit * entry_credit

        should_close, reason = False, ""
        if days_to_exp <= 1:
            should_close, reason = True, "approaching expiration"
        elif pnl >= profit_target:
            should_close, reason = True, f"profit target hit (${pnl:.2f} >= ${profit_target:.2f})"
        elif -pnl >= stop_loss_level:
            should_close, reason = True, f"stop loss hit (loss ${-pnl:.2f} >= ${stop_loss_level:.2f})"

        if should_close:
            try:
                _close(record, net_debit)
                ledger.close_convexity_position(record["strategy_id"], exit_pnl=pnl, close_reason=reason)
                log_entries.append(
                    {"action": "close", "strategy_id": record["strategy_id"], "reason": reason, "pnl": pnl}
                )
            except Exception as exc:  # noqa: BLE001 - don't let one bad close kill the whole run
                log_entries.append({"action": "close_failed", "strategy_id": record["strategy_id"], "error": str(exc)})
        else:
            log_entries.append(
                {"action": "hold", "strategy_id": record["strategy_id"], "unrealized_pnl": pnl}
            )

    return log_entries
