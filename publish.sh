#!/usr/bin/env bash
# Publishes the live dashboard snapshot to GitHub Pages.
#
# The trading daemon writes data/dashboard.json to local disk every cycle,
# but nothing pushes it -- so the Pages site 404s. This loop commits and
# pushes it on an interval. Run it in its OWN terminal, alongside the daemon:
#
#     ./publish.sh
#
# Ctrl+C to stop. Safe to start/stop at any time; it never touches the agent.

set -uo pipefail
cd "$(dirname "$0")"
INTERVAL="${PUBLISH_INTERVAL:-120}"

echo "[publish] pushing data/dashboard.json every ${INTERVAL}s (Ctrl+C to stop)"
echo "[publish] -> https://thomaskissflow.github.io/alpacaHackathon/dashboard/"

while true; do
  if [ -f data/dashboard.json ]; then
    git add data/dashboard.json data/decisions.json data/iv_history.json 2>/dev/null

    if git diff --cached --quiet; then
      echo "[publish] $(date '+%H:%M:%S') no change"
    else
      EQ=$(python3 -c "
import json
try:
    h=json.load(open('data/dashboard.json'))['account_history']
    print(f\"equity {h[-1]['equity']:.2f}\" if h else 'no snapshots')
except Exception: print('unreadable')
" 2>/dev/null)

      if git commit -q -m "agent: dashboard snapshot $(date -u +%Y-%m-%dT%H:%M:%SZ) — ${EQ}"; then
        # rebase on anything pushed from the other machine before publishing
        git pull --rebase --autostash -q origin main 2>/dev/null
        if git push -q origin main 2>/dev/null; then
          echo "[publish] $(date '+%H:%M:%S') pushed — ${EQ}"
        else
          echo "[publish] $(date '+%H:%M:%S') PUSH FAILED (will retry next cycle)"
        fi
      fi
    fi
  else
    echo "[publish] $(date '+%H:%M:%S') waiting for data/dashboard.json..."
  fi
  sleep "$INTERVAL"
done
