"""Rendering: Jinja templates, section pre-rendering, and PDF assembly."""

import json
from pathlib import Path

TEMPLATE_DIR = Path(__file__).parent / "templates"

# Neutral colours and email-safe font stacks, generated from the website's
# design tokens (frontend/design/tokens.json) so the site, email, archive and
# PDF read as one publication. Genre accents live in config/genres.yaml.
PALETTE: dict[str, str] = json.loads(
    (Path(__file__).parent / "palette.json").read_text(encoding="utf-8")
)
PALETTE.pop("_comment", None)

__all__ = ["PALETTE", "TEMPLATE_DIR"]
