"""
Execution Agent: turns an approved StrategyPlan into a single atomic
multi-leg (MLEG) order via the alpaca-py SDK, and records the open position
in the ledger's convexity_positions table so monitor.py can manage it later.

We use a LIMIT order at the net credit we estimated from quote midpoints,
not a market order -- a multi-leg market order on a spread can fill at a much
worse net price than intended. Confirm the net-credit sign convention against
docs.alpaca.markets/docs/options-level-3-trading before running this live;
adjust `limit_price` below if Alpaca expects the opposite sign for a
credit vs. debit multi-leg order.
"""
from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
from alpaca.trading.requests import LimitOrderRequest, OptionLegRequest

from agent import ledger
from agent.clients import trading_client
from agent.strategy import StrategyPlan


def execute(plan: StrategyPlan) -> dict:
    legs = [
        OptionLegRequest(
            symbol=leg.symbol,
            side=OrderSide.SELL if leg.side == "sell" else OrderSide.BUY,
            ratio_qty=leg.ratio_qty,
        )
        for leg in plan.legs
    ]
    legs_for_ledger = [{"symbol": l.symbol, "side": l.side, "ratio_qty": l.ratio_qty} for l in plan.legs]

    order_id = ledger.log_order(
        "convexity", plan.underlying, "mleg", 1, "mleg_limit", round(plan.net_credit_estimate, 2),
        "new", legs=legs_for_ledger, note=plan.strategy_type,
    )

    order_req = LimitOrderRequest(
        qty=1,
        order_class=OrderClass.MLEG,
        time_in_force=TimeInForce.DAY,
        legs=legs,
        limit_price=round(plan.net_credit_estimate, 2),
    )
    order = trading_client.submit_order(order_req)
    ledger.update_order_status(order_id, "new", alpaca_order_id=str(order.id))

    ledger.open_convexity_position(
        strategy_id=str(order.id),
        strategy_type=plan.strategy_type,
        underlying=plan.underlying,
        expiration=plan.expiration.isoformat(),
        legs=legs_for_ledger,
        entry_credit=plan.net_credit_estimate,
        max_loss_estimate=plan.max_loss_estimate,
    )

    return {
        "strategy_id": str(order.id),
        "strategy_type": plan.strategy_type,
        "underlying": plan.underlying,
        "expiration": plan.expiration.isoformat(),
        "legs": legs_for_ledger,
        "entry_credit": plan.net_credit_estimate,
        "max_loss": plan.max_loss_estimate,
    }
