import pytest

from agent import ledger


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path, monkeypatch):
    """Every test gets its own throwaway SQLite file -- never touches the
    real data/ledger.db, and tests never make live Alpaca API calls."""
    test_db = tmp_path / "test_ledger.db"
    monkeypatch.setattr(ledger, "DB_PATH", test_db)
    ledger.init_db()
    yield
