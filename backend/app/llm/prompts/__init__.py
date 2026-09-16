"""Versioned prompts.

One module per agent per version, never edited in place. Changing a prompt
means adding `<agent>_v<n>.py` and pointing the agent at it, because
`prompt_version` is persisted with every story and every fact check, and
CLAUDE.md requires an eval run for any prompt change. Editing an existing
version would silently invalidate that record.

Prompts are Python modules rather than data files so they are importable
without packaging concerns and diff cleanly in review.
"""
