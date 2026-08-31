# Setup Guide — Alpaca accounts & API keys

> For both developers. Follow this in order.
> **Last updated:** 2026-08-30

---

## 1. What Alpaca is

Alpaca is a **programmable brokerage**. Where a normal broker gives you a website to click "buy", Alpaca gives you an API: your code sends an HTTP request and a real order goes to the market. It handles the brokerage side — order routing, execution, position tracking, margin, market data — and you build the application on top.

For this hackathon that matters in three ways:

- **It trades options, not just stocks.** Options are a hard requirement (R3), and Alpaca supports single-leg *and* multi-leg (Level 3) option orders — verticals, condors, straddles — which is what lets us build defined-risk structures.
- **It has a paper environment**: a full simulation with real market data and virtual money. Same API, same endpoints, no real capital. Everything we build runs here.
- **It ships agent-oriented tooling**: an official MCP server and a CLI, one of which we are required to use (R2).

Two environments exist. We only ever touch the first:

| | Paper | Live |
|---|---|---|
| Money | Virtual | Real |
| Market data | Real | Real |
| Signup | Email only, **anyone globally** | Full KYC, identity documents, country restrictions |
| Base URL | `https://paper-api.alpaca.markets` | `https://api.alpaca.markets` |

**No KYC, no funding, no card, and no US residency needed.** Paper accounts are open to anyone worldwide with an email address. Being in India is not a blocker.

---

## 2. Accounts we need — three, not one

This is the part that is easy to get wrong, and getting it wrong costs us eligibility.

| Account | Purpose | Who holds the keys |
|---|---|---|
| 🏆 **Competition** | The judged account. Brand-new, $100,000. **Zero test trades, ever.** | GitHub Actions Secrets **only** |
| 🔧 **Dev A sandbox** | Dev A's local testing | Dev A's local `.env` |
| 🔧 **Dev B sandbox** | Dev B's local testing | Dev B's local `.env` |

**Why three:** requirement R4 disqualifies reused accounts, and the judges evaluate our P&L from the competition account's *entire* trading history. One accidental test order at 01:00 IST contaminates it permanently. Separate accounts make that mistake structurally impossible rather than a matter of discipline.

Alpaca supports multiple simultaneous paper accounts under one login, so this costs nothing.

---

## 3. Creating the accounts

**Each developer does steps 1–2 for themselves. Thomas does step 3 once.**

### Step 1 — Sign up
1. Go to **https://alpaca.markets/** and sign up, or log in at **https://app.alpaca.markets/**.
2. Email + password. Choose **paper trading** — do not start a live account application; it needs identity documents we do not need and will not use.
3. You land on the dashboard with a paper account already created.

> ⚠️ Claude cannot create accounts or enter passwords on your behalf. Each of you must do this yourself.

### Step 2 — Your personal sandbox account
The account you get on signup *is* your sandbox. Use it for all development and testing. Nothing about it is precious — if you corrupt its state, delete it and open another.

### Step 3 — The competition account (Thomas only, once)
1. In the dashboard, click the **paper account number in the upper-left corner**.
2. Select **"Open New Paper Account."**
3. Set the starting balance to **$100,000**. New paper accounts default to exactly this, which is what requirement R5 demands — but **check it in the dialog before confirming**.
   > ⚠️ **The balance cannot be changed after creation.** Alpaca's only supported way to change it is to delete the account and create a new one. If we get this wrong we must delete and recreate — which is fine on day one, and a disaster on day four once the account has trading history we are judged on.
4. Name it something unmistakable, e.g. `HACKATHON-COMPETITION-DO-NOT-TOUCH`.
5. **Record the account ID** in this repo (`docs/credentials.md`, ID only). It is a required submission field — judges use it to pull our P&L — so it is not a secret.
6. **Never place a manual or test order on it.** The first order it ever sees should be the agent's, in production.

---

## 4. API keys — yes, you need them

The API key is how your code authenticates. Without one, nothing can read the market or place an order.

**Keys are per paper account.** Switching accounts in the dashboard and generating keys gives you keys for *that* account.

### How authentication actually works

Two headers on every request — that is the whole mechanism:

```
APCA-API-KEY-ID: <your key id>
APCA-API-SECRET-KEY: <your secret>
```

(HTTP Basic auth with key-as-username also works.) The SDKs and the CLI set these for you from `ALPACA_API_KEY` / `ALPACA_SECRET_KEY`.

- Paper key IDs start `PK…`, live key IDs start `AK…`.
- **Paper and live credentials are not interchangeable**, and each account has its own.
- ⚠️ **Ignore `POST /oauth2/token` (the "issue tokens" reference page).** That is an OAuth2 endpoint for **Broker API partners and Alpaca-internal systems** (Keycloak/Google JWT-bearer grants). Alpaca's docs state the Client Credentials flow **is not yet available for the Trading API**. It is not our path and will waste an hour if someone tries it.

### To generate
1. Select the account you want keys for (upper-left account switcher — **check this twice**).
2. Open the **API Keys** panel in the dashboard.
3. Generate. You get a **Key ID** (starts `PK…` for paper) and a **Secret Key**.
4. **The secret is shown exactly once.** Copy it immediately into your password manager. If you lose it you must regenerate.

### ⚠️ Three gotchas that will bite us

1. **Regenerating invalidates the old secret.** If one of us regenerates the competition account's keys, the live agent stops trading mid-competition and nobody notices until morning. **Generate the competition keys once, and then nobody touches that panel again.**
2. **Generate keys while the correct account is selected.** Keys generated against the wrong account will happily trade the wrong account. This is the most common way the competition account gets contaminated.
3. **The market-data plan is per-login, not per-account.** All paper accounts under one login share the same free Basic data tier — indicative options feed, IEX equities, 200 req/min. Creating more accounts does not get us more data.

### Where each key lives

| Key | Lives in | Never |
|---|---|---|
| Competition | **GitHub Actions Secrets** (`ALPACA_API_KEY`, `ALPACA_SECRET_KEY`) | On a laptop, in `.env`, in the repo, in chat |
| Dev sandbox | Your local `.env` (gitignored) | Committed |

`.gitignore` already covers `.env`, `.env.*` and `.venv/`. **Never paste a secret key into a commit, a doc, an issue, or a chat message** — treat a leaked key as a leaked account and regenerate immediately.

---

## 5. Verify your setup

Once you have keys, install the CLI and confirm everything works **against your sandbox account**:

```bash
brew install alpacahq/tap/cli
```

```bash
export ALPACA_API_KEY=PK_your_sandbox_key
export ALPACA_SECRET_KEY=your_sandbox_secret
alpaca account get
```

Check the response shows roughly $100,000 equity and that paper mode is active. Paper is the CLI's default — live requires an explicit `ALPACA_LIVE_TRADE=true`, so there is no way to accidentally trade real money.

Then confirm the things this project actually depends on:

```bash
alpaca clock
```

```bash
alpaca account get --jq '{options_approved_level, options_trading_level, options_buying_power}'
```

Options are enabled by default in paper, and multi-leg (Level 3) is available — but confirm the level is what we expect before building on it.

```bash
alpaca data option chain --underlying-symbol SPY
```

This is the important one. Confirm we get contracts back **with greeks and implied volatility populated** on the free indicative feed. Remember: greeks require non-zero bid *and* ask, and 0DTE contracts never have them. See [research.md](research.md) §1.4.

---

## 6. Checklist

| ✔ | Item | Owner |
|---|---|---|
| ☐ | Dev A signed up, has a sandbox account + keys | A |
| ☐ | Dev B signed up, has a sandbox account + keys | B |
| ☐ | Competition account created, balance $100,000, clearly named | T |
| ☐ | Competition account ID recorded in `docs/credentials.md` | T |
| ☐ | Competition keys generated **once**, stored in GitHub Actions Secrets only | T |
| ☐ | Featherless credits claimed (code `ALPACA26`) | T |
| ☐ | CLI installed and `alpaca account get` verified by both devs | A + B |
| ☐ | Option chain returns greeks on the free feed | A |
| ☐ | Multi-leg `mleg` order validated with `--dry-run` on a **sandbox** account | A |
