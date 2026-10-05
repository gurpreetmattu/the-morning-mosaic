"""Small helpers shared by the job entry points for `pipeline_runs` rows."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.clock import now_utc
from app.models.enums import RunStatus
from app.models.operations import PipelineRun

logger = logging.getLogger(__name__)


def fail_run(session: Session, run_id: uuid.UUID, error: BaseException) -> bool:
    """Mark a run that died with an unexpected exception as FAILED.

    A crash (a dropped database connection, say) used to leave the row `running` for
    ever, so a morning's report could not tell a dead run from a slow one. Only a row
    still `running` is touched, so a run that already finished is never rewritten.
    Returns whether a row was updated. Never raises: this runs while another error is
    already propagating.
    """
    try:
        run = session.get(PipelineRun, run_id)
        if run is None or run.status is not RunStatus.RUNNING:
            return False
        run.status = RunStatus.FAILED
        run.finished_at = now_utc()
        run.detail = {**(run.detail or {}), "error": f"{type(error).__name__}: {error}"[:400]}
        session.flush()
        return True
    except Exception:
        logger.exception("could not record the failed run")
        return False
