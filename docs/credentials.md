# Credentials

> Account **IDs** only, ever. Never API keys or secrets — those live only in
> each person's local `.env` (gitignored) or in GitHub Actions Secrets. See
> `docs/setup-guide.md` §4 and `docs/decisions.md` D-010.

## Competition account (the judged one)

- **Account ID:** `8e94f0d6-2042-4927-bc2b-8d36a00eb6f8`
- **Created:** 2026-08-31
- **Starting balance:** $100,000 (verified via API — equity, cash, and
  last_equity all exactly 100000)
- **Options level:** 3 (spreads enabled)
- **Trade history at time of verification (2026-09-03):** zero orders ever
  placed, zero positions, zero activity — confirmed via `get_orders(status=ALL)`
  before this account was wired in as the competition account.
- **Rule:** no manual or test trades, ever. Only the automated agent
  (`agent/daemon.py` / `agent/run.py`) should touch this account from here on.

## Dev/sandbox account

Retired from competition use on 2026-08-31 after live-testing (Specialist
Mode's platform-constraint discovery, see `docs/decisions.md` D-013) picked
up one inorganic manual test trade. Fine to keep using for local development
and testing — just never treat its ID or history as the competition account's.
Its ID is not recorded here since it's not going in the submission.
