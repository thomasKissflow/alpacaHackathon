from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from agent import ledger, reconcile


class FakePosition:
    def __init__(self, qty, side):
        self.qty = qty
        self.side = side


class FakeTradingClient:
    def __init__(self, positions=None, order=None):
        self.positions = positions or {}
        self.order = order
        self.closed_positions = []
        self.cancelled_order_ids = []

    def get_open_position(self, symbol):
        if symbol not in self.positions:
            raise Exception("position does not exist")
        qty, side = self.positions[symbol]
        return FakePosition(qty, side)

    def close_position(self, symbol):
        self.closed_positions.append(symbol)
        return SimpleNamespace(id="closed-order-id")

    def get_order_by_id(self, order_id):
        return self.order

    def cancel_order_by_id(self, order_id):
        self.cancelled_order_ids.append(order_id)


def _open_iron_condor(strategy_id="mleg-1"):
    ledger.open_convexity_position(
        strategy_id, "iron_condor", "SPY", "2026-10-16",
        legs=[
            {"symbol": "SPY261016P00440000", "side": "sell", "ratio_qty": 1},
            {"symbol": "SPY261016P00435000", "side": "buy", "ratio_qty": 1},
        ],
        entry_credit=1.5, max_loss_estimate=350.0,
    )


def test_reconcile_does_nothing_when_all_legs_present(monkeypatch):
    _open_iron_condor()
    fake = FakeTradingClient(positions={
        "SPY261016P00440000": (1, "short"),
        "SPY261016P00435000": (1, "long"),
    })
    monkeypatch.setattr(reconcile, "trading_client", fake)

    reconcile.reconcile_convexity_positions()

    assert fake.closed_positions == []
    assert ledger.open_convexity_positions() != []  # still open, untouched


def test_reconcile_flattens_naked_leg(monkeypatch):
    _open_iron_condor()
    # only the short leg is held -- the long (protective) leg never filled
    fake = FakeTradingClient(positions={"SPY261016P00440000": (1, "short")})
    monkeypatch.setattr(reconcile, "trading_client", fake)

    reconcile.reconcile_convexity_positions()

    assert fake.closed_positions == ["SPY261016P00440000"]
    assert ledger.open_convexity_positions() == []
    risk_events = ledger.recent("risk_events", limit=10)
    assert any("NAKED LEG" in e["reason"] for e in risk_events)


def test_reconcile_leaves_fresh_unfilled_entry_alone(monkeypatch):
    _open_iron_condor()
    fake_order = SimpleNamespace(status="new", submitted_at=datetime.now(timezone.utc), created_at=None)
    fake = FakeTradingClient(positions={}, order=fake_order)
    monkeypatch.setattr(reconcile, "trading_client", fake)

    reconcile.reconcile_convexity_positions()

    assert fake.cancelled_order_ids == []
    assert len(ledger.open_convexity_positions()) == 1


def test_reconcile_cancels_stale_unfilled_entry(monkeypatch):
    _open_iron_condor()
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=reconcile.STALE_UNFILLED_MINUTES + 5)
    fake_order = SimpleNamespace(status="new", submitted_at=stale_time, created_at=None)
    fake = FakeTradingClient(positions={}, order=fake_order)
    monkeypatch.setattr(reconcile, "trading_client", fake)

    reconcile.reconcile_convexity_positions()

    assert fake.cancelled_order_ids == ["mleg-1"]
    assert ledger.open_convexity_positions() == []
    closed = ledger.closed_convexity_positions_for_date(datetime.now(timezone.utc).date().isoformat())
    assert closed[0]["close_reason"] == "entry_never_filled_cancelled"
