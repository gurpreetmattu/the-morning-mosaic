"""Every scheduled job must actually run when invoked the way Terraform
invokes it: `python -m app.jobs.<module>` (see infra/cloud_run_jobs.tf).

That only executes code inside `if __name__ == "__main__":` — a job whose
file is missing that guard defines `main()` but never calls it, so the
Cloud Run job fires on schedule, exits 0 immediately, and does nothing,
silently. Five of the six jobs had exactly this bug until it was caught
here: `main()` was tested directly in every job's own test file, which
never exercises the module-as-script path at all.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

JOB_MODULES = [
    "app.jobs.feedback",
    "app.jobs.build",
    "app.jobs.late_update",
    "app.jobs.delivery",
    "app.jobs.failure_notice",
    "app.jobs.bounces",
]


@pytest.mark.parametrize("module", JOB_MODULES)
def test_the_job_module_actually_runs_as_a_script(module: str) -> None:
    """`--help` needs no database or credentials, but it does need
    `main()` to have been called at all: argparse prints usage and exits 0
    only from inside `main()`, never as a side effect of merely importing
    the module.
    """
    result = subprocess.run(
        [sys.executable, "-m", module, "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "usage:" in result.stdout
