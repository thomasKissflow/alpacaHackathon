"""
News Agent -- the one place this system forms a *view* rather than a price.

Everything else in The Specialist is deliberately opinion-free: it quotes two
sides and hedges. This module reads gold-market headlines from Alpaca's news
API, asks an open-weights model (Featherless) how much uncertainty they imply,
and returns a single compact label.

That label does NOT pick a direction and does NOT place an order. It feeds the
MarketPlan as one more input, where its only power is to make the agent quote
*wider* (charge more for providing liquidity when the news flow is turbulent)
or *narrower* when it is quiet. A market maker does not need to know which way
gold goes -- only how nervous to be about being on the other side of a trade.

Kept to a handful of headlines and a tight prompt because Featherless drops
the connection above ~1,200 prompt characters (see llm_agent).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone

import httpx

from agent.config import ALPACA_API_KEY, ALPACA_SECRET_KEY, DATA_DIR

NEWS_URL = "https://data.alpaca.markets/v1beta1/news"
GOLD_SYMBOLS = ("GLD", "IAU", "GDX")
CACHE_PATH = DATA_DIR / "news_sentiment.json"
CACHE_MINUTES = 30
MAX_HEADLINES = 5
HEADLINE_CHARS = 85

VALID_REGIMES = ("calm", "mixed", "turbulent")
# How much to widen quotes for each regime. Wider = charging more to make a
# market when headlines suggest the ground is moving under us.
REGIME_SPREAD_MULTIPLIER = {"calm": 0.9, "mixed": 1.0, "turbulent": 1.35}


@dataclass(frozen=True)
class NewsRead:
    regime: str
    spread_multiplier: float
    headline_count: int
    summary: str
    source: str          # 'llm' | 'fallback' | 'cache'
    generated_at: str

    def as_context(self) -> str:
        """Ultra-compact form for the MarketPlan prompt (prompt budget is tight)."""
        return f"gold news: {self.regime} ({self.headline_count} headlines)."


NEUTRAL = NewsRead(
    regime="mixed", spread_multiplier=1.0, headline_count=0,
    summary="no news read available", source="fallback",
    generated_at=datetime.now(timezone.utc).isoformat(),
)


def fetch_headlines(limit: int = MAX_HEADLINES) -> list[str]:
    """Recent gold-market headlines from Alpaca's news API."""
    try:
        resp = httpx.get(
            NEWS_URL,
            params={"symbols": ",".join(GOLD_SYMBOLS), "limit": limit},
            headers={"APCA-API-KEY-ID": ALPACA_API_KEY,
                     "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY},
            timeout=20.0,
        )
        if resp.status_code != 200:
            print(f"[news] Alpaca news HTTP {resp.status_code}")
            return []
        return [n["headline"][:HEADLINE_CHARS]
                for n in (resp.json().get("news") or []) if n.get("headline")]
    except Exception as exc:  # noqa: BLE001
        print(f"[news] headline fetch failed: {type(exc).__name__}: {exc}")
        return []


def _read_cache() -> NewsRead | None:
    if not CACHE_PATH.exists():
        return None
    try:
        raw = json.loads(CACHE_PATH.read_text())
        age = datetime.now(timezone.utc) - datetime.fromisoformat(raw["generated_at"])
        if age < timedelta(minutes=CACHE_MINUTES):
            return NewsRead(**{**raw, "source": "cache"})
    except Exception:  # noqa: BLE001
        pass
    return None


def _write_cache(read: NewsRead) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(asdict(read), indent=2))


def classify(headlines: list[str]) -> NewsRead:
    """Ask the LLM for an uncertainty regime. Never returns a direction."""
    from agent import llm_agent

    if not headlines:
        return NEUTRAL

    system = ('Classify gold-market news uncertainty. JSON only: '
              '{"regime":"calm|mixed|turbulent","summary":"one short sentence"}')
    user = "Headlines:\n" + "\n".join(f"- {h}" for h in headlines[:MAX_HEADLINES])

    raw = llm_agent._call_llm(system, user, max_tokens=150)
    if not raw:
        return NEUTRAL
    try:
        parsed = llm_agent._extract_json(raw) if hasattr(llm_agent, "_extract_json") else json.loads(raw)
        regime = str(parsed.get("regime", "mixed")).strip().lower()
        if regime not in VALID_REGIMES:
            regime = "mixed"
        return NewsRead(
            regime=regime,
            spread_multiplier=REGIME_SPREAD_MULTIPLIER[regime],
            headline_count=len(headlines),
            summary=str(parsed.get("summary", ""))[:200],
            source="llm",
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[news] could not parse LLM reply: {exc}")
        return NEUTRAL


def current_read(force: bool = False) -> NewsRead:
    """Cached gold-news read. Cheap to call every cycle."""
    if not force:
        cached = _read_cache()
        if cached:
            return cached
    read = classify(fetch_headlines())
    if read.source == "llm":
        _write_cache(read)
    return read
