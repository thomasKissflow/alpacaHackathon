# Learning scripts

If you're new to options trading, automated agents, or this codebase, start
here rather than jumping straight into `agent/`. Run them in order:

```bash
source .venv/bin/activate           # from the project root
python examples/01_pricing_demo.py       # what is an option worth, and what are "the Greeks"?
python examples/02_risk_gate_demo.py     # how does the safety layer decide what's allowed?
python examples/03_check_account.py      # a safe, READ-ONLY look at your live Alpaca account
python examples/seed_demo_dashboard.py   # fill the dashboard with sample data so you can see it
```

Each script is heavily commented — open the `.py` file itself and read
along as you run it, then try tweaking the numbers near the top of each one
(stock price, strike, volatility, trade size, etc.) and re-running to build
intuition for how they interact.

**None of these place, cancel, or modify a real order or position.**
Scripts 1, 2, and 4 don't even talk to the internet — they use pure math or
a disposable, temporary database. Script 3 is the only one that talks to
Alpaca, and it only *reads* data (account info, quotes, option chains).

## The real test suite

The scripts above are for learning. The project's actual automated tests —
the ones that would catch a real bug — live in `tests/` and use `pytest`:

```bash
python -m pytest tests/ -v
```

- `-v` means "verbose" — it prints one line per test instead of just a
  summary, which is easier to follow while you're learning.
- Every test in there uses a throwaway database and mocked Alpaca responses
  (see `tests/conftest.py`) — **none of them make live API calls or place
  real orders**, so it's always safe to run.
- Reading `tests/test_risk_gate.py` and `tests/test_pricing.py` is itself a
  good way to learn: each test is a small, named example of "given this
  input, the system should do exactly this" — e.g.
  `test_convexity_plan_rejected_when_max_loss_exceeds_per_trade_cap` is a
  one-line description of a real safety rule.

If a test ever fails after you change something in `agent/`, the test
output will show you exactly which check failed and why — that's the
system telling you "this change broke a safety guarantee," which is the
whole point of having them.

## Seeing the dashboard

`examples/seed_demo_dashboard.py` fills a **separate, throwaway** database
(`data/demo_ledger.db` — never `data/ledger.db`, the real one the live agent
uses) with clearly-fake example data, and exports it to
`data/demo_dashboard.json`. To actually look at it:

```bash
python examples/seed_demo_dashboard.py
cp data/demo_dashboard.json data/dashboard.json   # ONLY for a one-off look
python3 -m http.server 8934                        # from the project root
# open http://localhost:8934/dashboard/index.html in a browser
```

**Don't do that `cp` step once the real agent is trading** — the next real
cycle will overwrite `data/dashboard.json` from the real ledger anyway, but
in the meantime you'd be looking at fake data thinking it's real. (An
earlier version of this script wrote demo data directly into the real
`data/ledger.db` and it silently corrupted real risk-gate calculations once
real trading started — fake positions counted toward real Greeks caps. If
you're reading this after that happened to you: sorry, and it's fixed now.)
