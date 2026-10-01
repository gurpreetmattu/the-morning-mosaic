"""The landing page is static, so it keeps its own list of live genres
(frontend/src/content/genres.ts). It must match config/genres.yaml."""

from __future__ import annotations

import re
from pathlib import Path

from app.config.loader import load_genres

GENRES_TS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "content" / "genres.ts"


def test_the_landing_page_lists_exactly_the_enabled_genres() -> None:
    text = GENRES_TS.read_text(encoding="utf-8")
    match = re.search(r"LIVE_GENRE_SLUGS[^=]*=\s*\[(.*?)\]", text, flags=re.DOTALL)
    assert match, "LIVE_GENRE_SLUGS not found in frontend/src/content/genres.ts"
    live = re.findall(r'"([a-z]+)"', match.group(1))

    assert live == load_genres().active_keys
