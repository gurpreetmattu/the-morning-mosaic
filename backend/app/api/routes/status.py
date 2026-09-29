"""The public site-status page reads, `admin.py` writes.

CLAUDE.md: "Website downtime is shown as a status message on the site, not
emailed, unless it stops the newsletter." No automated detection drives this
yet (see `SiteStatus`'s own docstring) — an admin flips it manually during a
real incident.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.models.operations import SiteStatus

router = APIRouter()


class StatusResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    degraded: bool
    message: str | None
    updated_at: datetime | None


@router.get("/api/status", response_model=StatusResponse)
def read_status(session: Annotated[Session, Depends(db_session)]) -> StatusResponse:
    row = session.get(SiteStatus, 1)
    if row is None:
        # No incident has ever been recorded — operational by default.
        return StatusResponse(degraded=False, message=None, updated_at=None)
    return StatusResponse(degraded=row.degraded, message=row.message, updated_at=row.updated_at)
