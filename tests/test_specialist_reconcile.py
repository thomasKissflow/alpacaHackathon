from types import SimpleNamespace

from agent import ledger, specialist_mode


class FakeOrder:
    def __init__(self, status, filled_qty, filled_avg_price):
        self.status = status
        self.filled_qty = filled_qty
        self.filled_avg_price = filled_avg_price


class FakeTradingClientForOrders:
    def __init__(self, orders_by_id):
        self.orders_by_id = orders_by_id
        self.cancelled = []

    def get_order_by_id(self, order_id):
        return self.orders_by_id[order_id]


def test_reconcile_records_fill_and_updates_inventory_even_for_deselected_contract(monkeypatch):
    # Reproduces the exact live bug: a contract fills, then falls out of this
    # cycle's nearest-ATM selection -- global reconciliation must still catch it.
    order_id = ledger.log_order("specialist", "AAPL260909P00315000", "buy", 1, "limit", 5.15, "new")
    ledger.update_order_status(order_id, "new", alpaca_order_id="alpaca-1")

    fake = FakeTradingClientForOrders({"alpaca-1": FakeOrder("filled", "1", "5.15")})
    monkeypatch.setattr(specialist_mode.clients, "trading_client", fake)
    monkeypatch.setattr(specialist_mode.clients, "cancel_order", lambda oid: None)

    specialist_mode._reconcile_all_open_orders()

    inv = ledger.get_specialist_inventory("AAPL260909P00315000")
    assert inv["qty"] == 1
    fills = ledger.recent("fills", limit=10)
    assert len(fills) == 1 and fills[0]["fill_price"] == 5.15


def test_reconcile_cancels_still_resting_orders(monkeypatch):
    order_id = ledger.log_order("specialist", "SPY260909P00450000", "sell", 1, "limit", 3.00, "new")
    ledger.update_order_status(order_id, "new", alpaca_order_id="alpaca-2")

    fake = FakeTradingClientForOrders({"alpaca-2": FakeOrder("new", "0", None)})
    cancelled = []
    monkeypatch.setattr(specialist_mode.clients, "trading_client", fake)
    monkeypatch.setattr(specialist_mode.clients, "cancel_order", lambda oid: cancelled.append(oid))

    specialist_mode._reconcile_all_open_orders()

    assert cancelled == ["alpaca-2"]


def test_pick_quote_side_sells_when_long():
    assert specialist_mode._pick_quote_side("AAPL260909P00315000", current_qty=1) == "sell"


def test_pick_quote_side_buys_when_short():
    assert specialist_mode._pick_quote_side("AAPL260909P00315000", current_qty=-1) == "buy"


def test_pick_quote_side_alternates_when_flat():
    occ = "AAPL260909P00315000"
    ledger.log_order("specialist", occ, "buy", 1, "limit", 5.00, "cancelled")
    assert specialist_mode._pick_quote_side(occ, current_qty=0) == "sell"

    ledger.log_order("specialist", occ, "sell", 1, "limit", 5.20, "cancelled")
    assert specialist_mode._pick_quote_side(occ, current_qty=0) == "buy"


def test_pick_quote_side_defaults_to_buy_with_no_history():
    assert specialist_mode._pick_quote_side("SPY260909P00450000", current_qty=0) == "buy"


def test_rebalance_hedge_unwinds_when_option_position_closes(monkeypatch):
    # The exact live bug: a put position gets closed by the book's own
    # opposite-side fill, but the equity hedge for it must still unwind.
    ledger.upsert_equity_inventory("AAPL", 47, 315.0)  # stale hedge, no matching option position anymore

    monkeypatch.setattr(specialist_mode.ledger, "all_specialist_inventory", lambda: [])  # flat -- nothing held

    sold = {}

    def fake_place_equity_market_order(underlying, side, qty):
        sold["underlying"], sold["side"], sold["qty"] = underlying, side, qty
        return SimpleNamespace(id="close-hedge", filled_avg_price="315.00")

    monkeypatch.setattr(specialist_mode.clients, "place_equity_market_order", fake_place_equity_market_order)

    specialist_mode._rebalance_hedge("AAPL", underlying_price=315.0)

    assert sold == {"underlying": "AAPL", "side": "sell", "qty": 47}
    assert ledger.get_equity_inventory("AAPL")["qty"] == 0
