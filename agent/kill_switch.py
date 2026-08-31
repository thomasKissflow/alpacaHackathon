"""
Kill switch: a single flag file, checked by every entry point before any new
order is placed (see risk_gate.kill_switch_engaged()). `execute()` goes
further -- it actively cancels every resting order and flattens every open
position (options + equity), for the "something's wrong, stop everything now"
case. Usable as a library call or as a CLI:

    python -m agent.kill_switch engage      # block new orders only
    python -m agent.kill_switch execute     # engage + cancel + flatten now
    python -m agent.kill_switch disengage
    python -m agent.kill_switch status
"""
import sys
from datetime import datetime, timezone

from agent import ledger
from agent.clients import trading_client
from agent.config import KILL_SWITCH_FLAG


def is_engaged() -> bool:
    return KILL_SWITCH_FLAG.exists()


def engage(reason: str = "manually engaged") -> None:
    KILL_SWITCH_FLAG.parent.mkdir(parents=True, exist_ok=True)
    KILL_SWITCH_FLAG.write_text(f"{datetime.now(timezone.utc).isoformat()} {reason}\n")
    ledger.log_risk_event("kill_switch", f"kill switch engaged: {reason}")
    print("[kill_switch] engaged -- no new orders will be placed")


def disengage() -> None:
    if KILL_SWITCH_FLAG.exists():
        KILL_SWITCH_FLAG.unlink()
    ledger.log_risk_event("kill_switch", "kill switch disengaged")
    print("[kill_switch] disengaged")


def execute(reason: str = "manual kill switch execution") -> dict:
    """Engage the flag, cancel every resting order, and flatten every
    position (options + equity). Best-effort: logs and continues past any
    single API error rather than leaving the account half-flattened."""
    engage(reason)
    result = {"cancelled_orders": None, "closed_positions": None, "errors": []}

    try:
        cancelled = trading_client.cancel_orders()
        result["cancelled_orders"] = len(cancelled) if cancelled else 0
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(f"cancel_orders failed: {exc}")

    try:
        closed = trading_client.close_all_positions(cancel_orders=True)
        result["closed_positions"] = len(closed) if closed else 0
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(f"close_all_positions failed: {exc}")

    ledger.log_risk_event(
        "kill_switch",
        f"kill switch executed: cancelled {result['cancelled_orders']} orders, "
        f"closed {result['closed_positions']} positions"
        + (f"; errors: {result['errors']}" if result["errors"] else ""),
        details=result,
    )
    print(f"[kill_switch] executed: {result}")
    return result


def _main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in {"engage", "disengage", "status", "execute"}:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    if cmd == "engage":
        engage(" ".join(sys.argv[2:]) or "manually engaged via CLI")
    elif cmd == "disengage":
        disengage()
    elif cmd == "status":
        print("ENGAGED" if is_engaged() else "clear")
    elif cmd == "execute":
        execute(" ".join(sys.argv[2:]) or "manual kill switch execution via CLI")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
