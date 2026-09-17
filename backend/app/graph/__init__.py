"""LangGraph definitions for the build and late-update jobs.

Two graphs, one per loop the architecture diagram (docs/architecture.md)
actually draws:

- `write_and_verify`: the Writer <-> Fact-checker retry loop (agents 4-5),
  `checker -->|feedback on failure, max 2 retries| writer`.
- `build_genre`: one genre's collect -> rank -> verify-every-candidate
  pipeline (agents 2-3, invoking the loop above per candidate), supervised
  by the Orchestrator (agent 1, itself outside the graph — see its own
  module docstring).

Both are compiled once at import time and reused; LangGraph graphs are
immutable after `compile()`, and building one is not free.
"""

from __future__ import annotations
