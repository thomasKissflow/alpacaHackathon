# Submission Checklist

> **Deadline: Fri 4 Sep 2026, 20:30 IST** (15:00 UTC / 11:00 ET)
> **Target: submit by 18:00 IST Fri** — leave 2.5h of buffer. Platforms get slow at the deadline.
> **Last updated:** 2026-08-30

Tick items here as they are completed. This is the file we read out loud on Friday afternoon.

---

## 🚨 Eligibility gates — fail any of these and we are not judged

| ✔ | Gate | Owner | Status |
|---|---|---|---|
| ☐ | Agent is **autonomous** (runs and decides unattended) | A | Not started |
| ☐ | Project uses Alpaca's **MCP server or CLI** | A | Not started |
| ☐ | Strategy **incorporates options trading** | A | Not started |
| ☐ | **Brand-new** paper account, created for this hackathon only | T | **Not created** |
| ☐ | Account starting balance set to **$100,000** | T | **Not set** |
| ☐ | Zero prototype/test trades ever placed on the competition account | A + T | — |

> The last one is not on the official list but it is how the fourth gate gets failed in practice. Dev and competition accounts must be separate (D-010).

---

## 📝 Submission form fields

### Basic information
| ✔ | Field | Owner | Notes |
|---|---|---|---|
| ☐ | Project title | Team | Naming still open (P-6) |
| ☐ | Short description | C | One or two sentences |
| ☐ | Long description | C | Lift from `project-overview.md` + `architecture.md` |
| ☐ | Technology tags | C | Alpaca, MCP, Featherless, + stack |
| ☐ | Category tags | C | |

### Media
| ✔ | Field | Owner | Notes |
|---|---|---|---|
| ☐ | Cover image | B | |
| ☐ | **Video presentation** | B | ⚠️ **Length limit not stated on the page — confirm on Discord.** Budget 3h; it always overruns |
| ☐ | Slide presentation | B | |

### Code & hosting
| ✔ | Field | Owner | Notes |
|---|---|---|---|
| ☑ | Public GitHub repository | T | https://github.com/thomasKissflow/alpacaHackathon |
| ☐ | Demo application platform | B | Vercel (proposed) |
| ☐ | **Application URL** | B | Must be live and clickable — a repo alone is not enough |
| ☐ | **Alpaca paper trading account ID** | T | How judges pull our P&L. Account **ID** only — never keys |

### Written
| ✔ | Field | Owner | Notes |
|---|---|---|---|
| ☐ | **One-page write-up** | C + T | Must cover all three named topics ↓ |
| ☐ | → AI logic | | What the LLM does and does not decide (D-008) |
| ☐ | → Risk gates | | Per-trade caps, book caps, kill switch, event rule |
| ☐ | → Alpaca infrastructure implementation | | CLI for execution, MCP for research (D-007) |

### Social (optional, separately prized)
| ✔ | Field | Owner | Notes |
|---|---|---|---|
| ☐ | Post 1 — kickoff / what we're building | B | Day-1 slot has the highest engagement |
| ☐ | Post 2 — a setback or a technical finding | B | e.g. the 0DTE no-greeks discovery |
| ☐ | Post 3 — agent live / first trades | B | |
| ☐ | Post 4 — the NFP event rule | B | Timely and unclaimed by competitors |
| ☐ | Post 5 — results | B | |

> Every post must tag **@lablabai** and **@AlpacaHQ** on X, and lablab.ai + Alpaca on LinkedIn.
> Max 5 links submitted. Prize: 2 × $500 + 1-month Algo Trader Plus per team member (D-009).

---

## 🎯 Judged on (5 criteria, no published weights)

| Criterion | What moves it | Primary owner |
|---|---|---|
| **P&L Performance** | Positive, explainable P&L *and visible trading activity* | A |
| **Technology Implementation** | Idiomatic CLI + MCP use — 3 of 5 judges are Alpaca staff | A |
| **Creativity & Originality** | Book-level greeks, event awareness, git-as-audit-trail | A |
| **Presentation & Execution** | Video, slides, the glass-box replay UI | B |
| **Social Engagement** | Content quality **and** engagement generated | B |

---

## ⏰ Friday 4 Sep run sheet

| Time (IST) | Action | Owner |
|---|---|---|
| 18:00 | NFP released (08:30 ET). Verify the agent's event handling behaved | A |
| 18:30 | Final equity/P&L snapshot captured and committed | A |
| 19:00 | US market opens. Agent's final session begins | — |
| 19:00 | Final social post (results) | B |
| 19:30 | Dashboard redeployed with final state; verify the Application URL loads | B |
| 19:45 | **Submit** — every field above | T |
| 20:30 | 🔴 **DEADLINE** | — |

> Do not leave submission to 20:00. If the platform is slow or a field rejects, there is no recovery.
