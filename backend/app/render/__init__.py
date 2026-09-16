"""Rendering: Jinja templates, section pre-rendering, and PDF assembly."""

from pathlib import Path

TEMPLATE_DIR = Path(__file__).parent / "templates"

__all__ = ["TEMPLATE_DIR"]
