# The seven scheduled jobs (CLAUDE.md "Jobs" section). One resource per job
# via for_each rather than seven near-identical blocks — they differ only in
# name and which module Cloud Scheduler tells them to run (cloud_scheduler.tf
# sets the actual cadence; none of these need CLI flags, since every job's
# `main()` defaults --edition-date/--slot/--deadline-minutes/--older-than-days
# from the current time when Scheduler invokes it).

locals {
  # Cloud Run job name -> Python module. Matches app/models/enums.py:JobName.
  job_modules = {
    "purge"          = "app.jobs.purge"
    "feedback"       = "app.jobs.feedback"
    "build"          = "app.jobs.build"
    "late-update"    = "app.jobs.late_update"
    "delivery"       = "app.jobs.delivery"
    "failure-notice" = "app.jobs.failure_notice"
    "bounces"        = "app.jobs.bounces"
  }

  # Per-job timeouts in seconds; any job not listed uses var.job_timeout_seconds.
  # build: CLAUDE.md gives it 04:15 -> 05:30 (75 min), and a manual rerun may run
  # to 07:30 with an 08:45 deadline, so 90 min. The 600 s default killed the first
  # real 10-genre build mid-run (2026-10-01). late-update: 20 min deadline + slack.
  # delivery / failure-notice: sized to the 30-minute delivery cadence.
  job_timeout_overrides = {
    "build"          = 5400
    "late-update"    = 1500
    "delivery"       = 1800
    "failure-notice" = 1800
  }
}

resource "google_cloud_run_v2_job" "jobs" {
  for_each = local.job_modules

  name     = "mosaic-${each.key}"
  location = var.region
  labels   = local.labels

  template {
    template {
      service_account = google_service_account.jobs.email
      timeout         = "${lookup(local.job_timeout_overrides, each.key, var.job_timeout_seconds)}s"
      max_retries     = 0 # a job that fails partway shouldn't blindly rerun; see each job's own idempotency notes

      containers {
        image   = local.backend_image
        command = ["python"]
        args    = ["-m", each.value]

        dynamic "env" {
          for_each = local.common_env
          content {
            name  = env.key
            value = env.value
          }
        }

        dynamic "env" {
          for_each = local.secret_env
          content {
            name = env.key
            value_source {
              secret_key_ref {
                secret  = env.value
                version = "latest"
              }
            }
          }
        }
      }
    }
  }

  depends_on = [google_project_service.required]
}
