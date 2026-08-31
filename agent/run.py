"""
Single-cycle entry point -- what GitHub Actions' cron job runs. Good enough
for Convexity Mode (which only needs to act every few hours) and for LLM
MarketPlan/postmortem refreshes, but Specialist Mode's quote maintenance
really wants agent/daemon.py's tighter loop running somewhere long-lived
during market hours (see README for the tradeoff and both options).
"""
import sys

from agent.cycle import run_cycle


def main() -> int:
    try:
        run_cycle()
    except Exception as exc:  # noqa: BLE001
        print(f"[run] FATAL: cycle failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
