"""
Narrative decision feed for the dashboard (every scan/reject/enter/hold/close,
with reasoning) -- supplementary color alongside the ledger's structured
audit tables (agent/ledger.py), which are the actual source of truth for
orders/fills/hedges/risk-events/plans/postmortems.
"""
import json
from datetime import datetime, timezone

from agent.config import DECISIONS_LOG


def log_decision(entry: dict) -> None:
    DECISIONS_LOG.parent.mkdir(parents=True, exist_ok=True)
    entries = json.loads(DECISIONS_LOG.read_text()) if DECISIONS_LOG.exists() else []
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), **entry}
    entries.append(entry)
    DECISIONS_LOG.write_text(json.dumps(entries[-500:], indent=2))
