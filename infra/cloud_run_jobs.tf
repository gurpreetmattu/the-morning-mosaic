# The six scheduled jobs (CLAUDE.md "Jobs" section). One resource per job
# via for_each rather than six near-identical blocks — they differ only in
# name and which module Cloud Scheduler tells them to run (cloud_scheduler.tf
# sets the actual cadence; none of these need CLI flags, since every job's
# `main()` defaults --edition-date/--slot/--deadline-minutes from the
# current time when Scheduler invokes it).

locals {
  # Cloud Run job name -> Python module. Matches app/models/enums.py:JobName.
  job_modules = {
    "feedback"       = "app.jobs.feedback"
    "build"          = "app.jobs.build"
    "late-update"    = "app.jobs.late_update"
    "delivery"       = "app.jobs.delivery"
    "failure-notice" = "app.jobs.failure_notice"
    "bounces"        = "app.jobs.bounces"
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
      timeout         = "${var.job_timeout_seconds}s"
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
