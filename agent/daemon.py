"""
Long-running local/VM daemon: the "CLI-driven scheduled loop" from the build
brief that runs far more frequently than the LLM should be called, doing
quote maintenance, fill handling, and hedging. This is what you actually
want running during market hours for Specialist Mode to generate real fills;
GitHub Actions' 3x/day cron (agent/run.py) is comfortable for Convexity Mode
and for the LLM layer, but far too sparse for two-sided quoting.

    python -m agent.daemon                  # loop every RISK.daemon_poll_seconds
    python -m agent.daemon --once           # single cycle, for a quick sanity check
    DAEMON_IGNORE_MARKET_HOURS=true python -m agent.daemon   # skip the clock check (paper demo off-hours)
"""
import os
import sys
import time
from datetime import datetime, timezone

from agent.clients import trading_client
from agent.config import RISK
from agent.cycle import run_cycle

_IGNORE_MARKET_HOURS = os.environ.get("DAEMON_IGNORE_MARKET_HOURS", "false").lower() == "true"


def _market_is_open() -> bool:
    if _IGNORE_MARKET_HOURS:
        return True
    try:
        return bool(trading_client.get_clock().is_open)
    except Exception as exc:  # noqa: BLE001 - if the clock call fails, don't block the whole daemon on it
        print(f"[daemon] could not check market clock ({exc}); proceeding anyway")
        return True


def run_forever(poll_seconds: int = RISK.daemon_poll_seconds) -> None:
    print(f"[daemon] starting, poll interval {poll_seconds}s (Ctrl+C to stop)")
    while True:
        now = datetime.now(timezone.utc).isoformat()
        if _market_is_open():
            print(f"[daemon] {now} running cycle")
            try:
                run_cycle()
            except Exception as exc:  # noqa: BLE001 - never let one bad cycle kill the daemon
                print(f"[daemon] cycle raised: {exc}")
        else:
            print(f"[daemon] {now} market closed, skipping cycle")
        time.sleep(poll_seconds)


def main() -> int:
    if "--once" in sys.argv:
        run_cycle()
        return 0
    try:
        run_forever()
    except KeyboardInterrupt:
        print("\n[daemon] stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
