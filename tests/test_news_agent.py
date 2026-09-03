"""News Agent: gold headlines -> uncertainty regime -> quote width.

No network. The one invariant that matters: the news read may change how WIDE
we quote, never WHICH WAY we lean.
"""
import json

import pytest

from agent import news_agent as na


def test_regimes_map_to_sane_spread_multipliers():
    assert na.REGIME_SPREAD_MULTIPLIER["calm"] < 1.0
    assert na.REGIME_SPREAD_MULTIPLIER["mixed"] == 1.0
    assert na.REGIME_SPREAD_MULTIPLIER["turbulent"] > 1.0, "turbulent news must widen quotes"


def test_no_headlines_is_neutral_not_a_guess():
    assert na.classify([]).regime == "mixed"
    assert na.classify([]).spread_multiplier == 1.0


def test_classify_uses_llm_reply(monkeypatch):
    from agent import llm_agent
    monkeypatch.setattr(llm_agent, "_call_llm",
                        lambda s, u, max_tokens=150: json.dumps(
                            {"regime": "turbulent", "summary": "sharp repricing"}))
    read = na.classify(["Gold spikes on inflation shock"])
    assert read.regime == "turbulent"
    assert read.spread_multiplier == na.REGIME_SPREAD_MULTIPLIER["turbulent"]
    assert read.source == "llm"


def test_unknown_regime_falls_back_to_mixed(monkeypatch):
    from agent import llm_agent
    monkeypatch.setattr(llm_agent, "_call_llm",
                        lambda s, u, max_tokens=150: json.dumps({"regime": "MOON", "summary": "?"}))
    assert na.classify(["x"]).regime == "mixed"


def test_llm_failure_is_neutral(monkeypatch):
    from agent import llm_agent
    monkeypatch.setattr(llm_agent, "_call_llm",
                        lambda s, u, max_tokens=150: None)
    read = na.classify(["Gold falls"])
    assert read.regime == "mixed" and read.source == "fallback"


def test_read_never_expresses_direction():
    """Guard the design rule: this module must not emit a directional view.
    A market maker needs to know how nervous to be, not which way to lean."""
    fields = na.NewsRead.__dataclass_fields__.keys()
    for banned in ("direction", "side", "bias", "signal", "long", "short"):
        assert banned not in fields, f"NewsRead must not carry a '{banned}' field"


def test_context_form_is_tiny():
    """The MarketPlan prompt budget is ~650 chars total (Featherless drops the
    connection above ~1,200), so this clause has to stay small."""
    assert len(na.NEUTRAL.as_context()) < 60
