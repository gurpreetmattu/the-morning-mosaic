"""Whether the LLM gateway is actually reachable right now.

Several evals genuinely need a live model (groundedness, the harder planted
errors, full clustering) and CLAUDE.md's own non-negotiable principle is
"the LLM rephrases sources; it never supplies facts" — so those evals must
call the real thing, not a fixture, or they would not be measuring what
CLAUDE.md means by "any prompt or model change requires rerunning evals."

The configured gateway (`LLM_GATEWAY_URL`) is a real, publicly reachable
endpoint (Groq, as of this writing — see docs/BACKLOG.md's now-closed
gateway-reachability blocker), unlike the local `freellmpool` aggregator it
replaced. It can still be down, rate-limited, or between free-tier quota and
a real key, so rather than let every LLM-dependent eval fail with a
confusing connection error (or, worse, silently score a fail-closed result
as "caught" — see `FactChecker`'s fail-closed behaviour when the model is
unavailable), each one probes first and reports SKIPPED with a clear reason
when it can't run.
"""

from __future__ import annotations

import httpx

from app.config.settings import Settings

PROBE_TIMEOUT_SECONDS = 3.0


def llm_gateway_reachable(settings: Settings) -> bool:
    url = f"{str(settings.llm_gateway_url).rstrip('/')}/models"
    try:
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {settings.llm_gateway_api_key.get_secret_value()}"},
            timeout=PROBE_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError:
        return False
    # Even a 401/404 means something is listening and answering HTTP;
    # only a transport-level failure (above) means the gateway is down.
    return response.status_code < 500
