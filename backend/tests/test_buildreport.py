"""The morning build report must price tokens right and sort failures into
the reasons that matter when reading a build."""

from __future__ import annotations

import pytest

from app.buildreport import PRICES, classify_error, cost_usd


def test_cost_uses_per_million_prices() -> None:
    # 1M in + 1M out on gpt-oss-20b is 0.075 + 0.30
    assert cost_usd("openai/gpt-oss-20b", 1_000_000, 1_000_000) == pytest.approx(0.375)


def test_an_unpriced_model_costs_nothing_rather_than_raising() -> None:
    assert cost_usd("some/new-model", 5_000, 5_000) == 0.0


def test_every_priced_model_has_a_positive_price() -> None:
    assert all(i > 0 and o > 0 for i, o in PRICES.values())


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (None, "ok"),
        (
            "HTTP 429: you have used up your daily free allocation of 10,000 neurons",
            "quota: Cloudflare daily neurons",
        ),
        (
            "HTTP 429: You exceeded your current quota, please check your plan",
            "quota: daily/billing limit (HTTP 429)",
        ),
        (
            "HTTP 429: Rate limit reached for model x ... tokens per day (TPD)",
            "rate limit: per-minute/day tokens (HTTP 429)",
        ),
        ("HTTP 413: Request too large for model", "request too large (HTTP 413)"),
        ("HTTP 503: upstream unavailable", "provider error (HTTP 5xx)"),
        ("json_object requested but response was not valid JSON", "model returned invalid JSON"),
        ("something unexpected", "other"),
    ],
)
def test_errors_are_bucketed_by_cause(error: str | None, expected: str) -> None:
    assert classify_error(error) == expected
