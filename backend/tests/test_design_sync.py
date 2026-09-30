"""The backend's theme must match the website's design tokens.

`frontend/design/tokens.json` is the single source. `npm run tokens:backend`
pushes it into `backend/app/render/palette.json` and `config/genres.yaml`;
this fails loudly if someone edits one side without the other.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config.loader import load_genres
from app.render import PALETTE

TOKENS = Path(__file__).resolve().parents[2] / "frontend" / "design" / "tokens.json"


def tokens() -> dict[str, Any]:
    tokens_json: dict[str, Any] = json.loads(TOKENS.read_text(encoding="utf-8"))
    return tokens_json


def test_the_palette_matches_the_design_tokens() -> None:
    light = tokens()["colors"]["light"]

    assert PALETTE["paper"] == light["paper"]
    assert PALETTE["paper_raised"] == light["paper-raised"]
    assert PALETTE["ink"] == light["ink"]
    assert PALETTE["ink_muted"] == light["ink-muted"]
    assert PALETTE["press_red"] == light["press-red"]


def test_every_genre_theme_matches_the_design_tokens() -> None:
    genres = tokens()["genres"]

    by_key = load_genres().by_key()
    assert set(by_key) == set(genres)
    for key, genre in by_key.items():
        assert genre.theme.accent == genres[key]["accent"], key
        assert genre.theme.accent_soft == genres[key]["tint"], key
