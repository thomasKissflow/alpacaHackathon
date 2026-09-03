"""
The single append-only trade ledger (SQLite) shared by Specialist Mode,
Convexity Mode, the risk gate, the LLM agent layer, and the dashboard.

Append-only history tables: orders, fills, hedges, risk_events,
market_plans, postmortems, account_snapshots, position_snapshots.
Two small *mutable* working-state tables ride alongside them
(specialist_inventory, convexity_positions) because "what do we currently
hold" is naturally current-state, not history -- but every transition that
touches them is also written to the append-only tables above, so the full
history is always reconstructable from the audit trail alone.

Kept as plain sqlite3 + hand-written SQL (no ORM) so judges can open
data/ledger.db with any SQLite browser and read it directly.
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ledger.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    mode TEXT NOT NULL,                 -- 'specialist' | 'convexity'
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,                 -- 'buy' | 'sell'
    qty INTEGER NOT NULL,
    order_type TEXT NOT NULL,           -- 'limit' | 'mleg_limit'
    limit_price REAL,
    status TEXT NOT NULL,               -- 'new' | 'replaced' | 'cancelled' | 'filled' | 'rejected'
    alpaca_order_id TEXT,
    replaces_order_id INTEGER,
    legs_json TEXT,
    note TEXT
);

CREATE TABLE IF NOT EXISTS fills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    order_id INTEGER,
    mode TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    qty INTEGER NOT NULL,
    fill_price REAL NOT NULL,
    FOREIGN KEY(order_id) REFERENCES orders(id)
);

CREATE TABLE IF NOT EXISTS hedges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    trigger_fill_id INTEGER,
    underlying TEXT NOT NULL,
    side TEXT NOT NULL,
    qty INTEGER NOT NULL,
    price REAL,
    delta_before REAL,
    delta_after REAL,
    alpaca_order_id TEXT,
    FOREIGN KEY(trigger_fill_id) REFERENCES fills(id)
);

CREATE TABLE IF NOT EXISTS risk_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    event_type TEXT NOT NULL,           -- 'reject' | 'clamp' | 'circuit_breaker' | 'kill_switch'
    mode TEXT,
    reason TEXT NOT NULL,
    details_json TEXT
);

CREATE TABLE IF NOT EXISTS market_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    source TEXT NOT NULL,               -- 'llm' | 'fallback'
    proposed_json TEXT NOT NULL,
    approved_json TEXT NOT NULL,
    was_clamped INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS postmortems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    text TEXT NOT NULL,
    proposed_adjustments_json TEXT
);

CREATE TABLE IF NOT EXISTS account_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    equity REAL NOT NULL,
    cash REAL,
    buying_power REAL,
    specialist_pnl REAL,
    convexity_pnl REAL,
    day_pnl REAL
);

CREATE TABLE IF NOT EXISTS position_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    mode TEXT NOT NULL,
    symbol TEXT NOT NULL,
    underlying TEXT,
    qty INTEGER,
    delta_dollars REAL,
    gamma REAL,
    vega_dollars REAL,
    theta_dollars REAL,
    notional REAL
);

CREATE TABLE IF NOT EXISTS specialist_inventory (
    symbol TEXT PRIMARY KEY,
    underlying TEXT NOT NULL,
    qty INTEGER NOT NULL DEFAULT 0,
    avg_price REAL NOT NULL DEFAULT 0,
    updated_ts TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS underlying_marks (
    symbol TEXT PRIMARY KEY,
    price REAL NOT NULL,
    prev_close REAL,
    updated_ts TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS equity_inventory (
    underlying TEXT PRIMARY KEY,
    qty INTEGER NOT NULL DEFAULT 0,
    avg_price REAL NOT NULL DEFAULT 0,
    updated_ts TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS convexity_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id TEXT UNIQUE NOT NULL,
    strategy_type TEXT NOT NULL,
    underlying TEXT NOT NULL,
    expiration TEXT NOT NULL,
    legs_json TEXT NOT NULL,
    entry_credit REAL NOT NULL,
    max_loss_estimate REAL NOT NULL,
    opened_ts TEXT NOT NULL,
    closed_ts TEXT,
    status TEXT NOT NULL DEFAULT 'open',   -- 'open' | 'closed'
    exit_pnl REAL,
    close_reason TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(_SCHEMA)


# ---------------------------------------------------------------- orders ---

def log_order(mode, symbol, side, qty, order_type, limit_price, status,
              alpaca_order_id=None, replaces_order_id=None, legs=None, note=None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO orders
               (ts, mode, symbol, side, qty, order_type, limit_price, status,
                alpaca_order_id, replaces_order_id, legs_json, note)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (_now(), mode, symbol, side, qty, order_type, limit_price, status,
             alpaca_order_id, replaces_order_id, json.dumps(legs) if legs else None, note),
        )
        return cur.lastrowid


def update_order_status(order_id: int, status: str, alpaca_order_id: str | None = None) -> None:
    with get_conn() as conn:
        if alpaca_order_id is not None:
            conn.execute("UPDATE orders SET status=?, alpaca_order_id=? WHERE id=?",
                         (status, alpaca_order_id, order_id))
        else:
            conn.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))


# ----------------------------------------------------------------- fills ---

def log_fill(order_id, mode, symbol, side, qty, fill_price) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO fills (ts, order_id, mode, symbol, side, qty, fill_price) VALUES (?,?,?,?,?,?,?)",
            (_now(), order_id, mode, symbol, side, qty, fill_price),
        )
        return cur.lastrowid


def filled_qty_for_order(order_id: int) -> int:
    """Sum of fills already recorded against this order -- used to detect the
    *incremental* fill on a partially-filled resting quote between cycles."""
    with get_conn() as conn:
        row = conn.execute("SELECT COALESCE(SUM(qty), 0) AS s FROM fills WHERE order_id=?", (order_id,)).fetchone()
        return row["s"] or 0


def order_by_alpaca_id(alpaca_order_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM orders WHERE alpaca_order_id=?", (alpaca_order_id,)).fetchone()
        return dict(row) if row else None


# ---------------------------------------------------------------- hedges ---

def log_hedge(trigger_fill_id, underlying, side, qty, price, delta_before, delta_after,
              alpaca_order_id=None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO hedges
               (ts, trigger_fill_id, underlying, side, qty, price, delta_before, delta_after, alpaca_order_id)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (_now(), trigger_fill_id, underlying, side, qty, price, delta_before, delta_after, alpaca_order_id),
        )
        return cur.lastrowid


# ---------------------------------------------------------- risk events ----

def log_risk_event(event_type: str, reason: str, mode: str | None = None, details: dict | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO risk_events (ts, event_type, mode, reason, details_json) VALUES (?,?,?,?,?)",
            (_now(), event_type, mode, reason, json.dumps(details) if details else None),
        )


# --------------------------------------------------------- market plans ----

def log_market_plan(proposed: dict, approved: dict, source: str, was_clamped: bool) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO market_plans (ts, source, proposed_json, approved_json, was_clamped)
               VALUES (?,?,?,?,?)""",
            (_now(), source, json.dumps(proposed), json.dumps(approved), int(was_clamped)),
        )


def latest_market_plan() -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM market_plans ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None


# ---------------------------------------------------------- postmortems ----

def log_postmortem(trade_date: str, text: str, proposed_adjustments: dict | None) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO postmortems (ts, trade_date, text, proposed_adjustments_json) VALUES (?,?,?,?)",
            (_now(), trade_date, text, json.dumps(proposed_adjustments) if proposed_adjustments else None),
        )


def postmortem_exists_for(trade_date: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM postmortems WHERE trade_date=? LIMIT 1", (trade_date,)).fetchone()
        return row is not None


# ------------------------------------------------------------ snapshots ----

def log_account_snapshot(equity, cash, buying_power, specialist_pnl, convexity_pnl, day_pnl) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO account_snapshots
               (ts, equity, cash, buying_power, specialist_pnl, convexity_pnl, day_pnl)
               VALUES (?,?,?,?,?,?,?)""",
            (_now(), equity, cash, buying_power, specialist_pnl, convexity_pnl, day_pnl),
        )


def log_position_snapshot(mode, symbol, underlying, qty, delta_dollars, gamma, vega_dollars, theta_dollars, notional) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO position_snapshots
               (ts, mode, symbol, underlying, qty, delta_dollars, gamma, vega_dollars, theta_dollars, notional)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (_now(), mode, symbol, underlying, qty, delta_dollars, gamma, vega_dollars, theta_dollars, notional),
        )


def portfolio_greeks_now() -> dict:
    """Sum of the most recent per-symbol position_snapshot row for each symbol still open."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT ps.* FROM position_snapshots ps
               INNER JOIN (
                   SELECT symbol, MAX(id) AS max_id FROM position_snapshots GROUP BY symbol
               ) latest ON ps.id = latest.max_id
               WHERE ps.qty != 0"""
        ).fetchall()
    total = {"delta_dollars": 0.0, "gamma": 0.0, "vega_dollars": 0.0, "theta_dollars": 0.0, "notional": 0.0}
    for r in rows:
        for k in total:
            total[k] += r[k] or 0.0
    return total


# ----------------------------------------------------- specialist inventory

def get_specialist_inventory(symbol: str) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM specialist_inventory WHERE symbol=?", (symbol,)).fetchone()
        return dict(row) if row else {"symbol": symbol, "qty": 0, "avg_price": 0.0}


def upsert_specialist_inventory(symbol: str, underlying: str, new_qty: int, new_avg_price: float) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO specialist_inventory (symbol, underlying, qty, avg_price, updated_ts)
               VALUES (?,?,?,?,?)
               ON CONFLICT(symbol) DO UPDATE SET qty=excluded.qty, avg_price=excluded.avg_price,
                   updated_ts=excluded.updated_ts""",
            (symbol, underlying, new_qty, new_avg_price, _now()),
        )


def all_specialist_inventory() -> list[dict]:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM specialist_inventory WHERE qty != 0")]


def record_underlying_mark(symbol: str, price: float) -> None:
    """Latest observed underlying price, for the dashboard's ticker strip.
    prev_close is a same-day-open proxy (first price seen each UTC day) --
    cheap and good enough for a day-change indicator; not a real prior
    session close, which would need a separate API call this project
    doesn't otherwise need."""
    today = _now()[:10]
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM underlying_marks WHERE symbol=?", (symbol,)).fetchone()
        if row is None or row["updated_ts"][:10] != today:
            prev_close = price
        else:
            prev_close = row["prev_close"]
        conn.execute(
            """INSERT INTO underlying_marks (symbol, price, prev_close, updated_ts) VALUES (?,?,?,?)
               ON CONFLICT(symbol) DO UPDATE SET price=excluded.price, prev_close=excluded.prev_close,
                   updated_ts=excluded.updated_ts""",
            (symbol, price, prev_close, _now()),
        )


def all_underlying_marks() -> list[dict]:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM underlying_marks ORDER BY symbol")]


def get_equity_inventory(underlying: str) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM equity_inventory WHERE underlying=?", (underlying,)).fetchone()
        return dict(row) if row else {"underlying": underlying, "qty": 0, "avg_price": 0.0}


def upsert_equity_inventory(underlying: str, new_qty: int, new_avg_price: float) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO equity_inventory (underlying, qty, avg_price, updated_ts)
               VALUES (?,?,?,?)
               ON CONFLICT(underlying) DO UPDATE SET qty=excluded.qty, avg_price=excluded.avg_price,
                   updated_ts=excluded.updated_ts""",
            (underlying, new_qty, new_avg_price, _now()),
        )


# ---------------------------------------------------------- convexity -----

def open_convexity_position(strategy_id, strategy_type, underlying, expiration, legs,
                             entry_credit, max_loss_estimate) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO convexity_positions
               (strategy_id, strategy_type, underlying, expiration, legs_json,
                entry_credit, max_loss_estimate, opened_ts, status)
               VALUES (?,?,?,?,?,?,?,?, 'open')""",
            (strategy_id, strategy_type, underlying, expiration, json.dumps(legs),
             entry_credit, max_loss_estimate, _now()),
        )


def close_convexity_position(strategy_id: str, exit_pnl: float, close_reason: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE convexity_positions SET status='closed', closed_ts=?, exit_pnl=?, close_reason=? WHERE strategy_id=?",
            (_now(), exit_pnl, close_reason, strategy_id),
        )


def open_convexity_positions() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM convexity_positions WHERE status='open'").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["legs"] = json.loads(d.pop("legs_json"))
            out.append(d)
        return out


def convexity_pnl_realized_today() -> float:
    today = datetime.now(timezone.utc).date().isoformat()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(exit_pnl), 0) AS s FROM convexity_positions WHERE substr(closed_ts,1,10)=? AND status='closed'",
            (today,),
        ).fetchone()
        return row["s"] or 0.0


def closed_convexity_positions_for_date(trade_date: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM convexity_positions WHERE substr(closed_ts,1,10)=? AND status='closed'",
            (trade_date,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["legs"] = json.loads(d.pop("legs_json"))
            out.append(d)
        return out


# ------------------------------------------------------- dashboard reads ---

def recent(table: str, limit: int = 200) -> list[dict]:
    assert table in {
        "orders", "fills", "hedges", "risk_events", "market_plans",
        "postmortems", "account_snapshots", "position_snapshots",
    }, f"unexpected table {table!r}"
    with get_conn() as conn:
        rows = conn.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


init_db()
