# CLAUDE.md's "Jobs" section, verbatim, in IST (Cloud Scheduler's own
# `time_zone` field, so the cron expressions below don't need UTC math and
# don't drift across DST — India has none, but this still reads as IST).
#
# Cloud Scheduler can't call a Cloud Run *Job* the way it calls a Service:
# there's no URL to hit. Instead each schedule POSTs to the Cloud Run Admin
# API's `:run` endpoint, authenticated as a dedicated service account that
# holds nothing but run.invoker on that one job.

locals {
  # job key -> {schedule, run_object} where run_object is the Cloud Run job
  # resource this schedule triggers. Delivery gets seven schedules (every
  # 30 minutes from 06:00 to 09:00 inclusive) instead of one cron
  # expression, because plain cron can't express "this exact set of times."
  single_schedules = {
    "purge"          = { cron = "0 3 * * *", job = "purge" }
    "feedback"       = { cron = "0 4 * * *", job = "feedback" }
    "build"          = { cron = "15 4 * * *", job = "build" }
    "late-update-1"  = { cron = "35 5 * * *", job = "late-update" }
    "late-update-2"  = { cron = "5 7 * * *", job = "late-update" }
    "bounces"        = { cron = "0 5 * * *", job = "bounces" }
    "failure-notice" = { cron = "5 9 * * *", job = "failure-notice" }
  }

  delivery_times = ["0 6", "30 6", "0 7", "30 7", "0 8", "30 8", "0 9"]
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_invoker" {
  for_each = google_cloud_run_v2_job.jobs

  name     = each.value.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloud_scheduler_job" "single" {
  for_each = local.single_schedules

  name      = "mosaic-${each.key}"
  region    = var.region
  schedule  = each.value.cron
  time_zone = "Asia/Kolkata"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/v2/${google_cloud_run_v2_job.jobs[each.value.job].id}:run"

    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }

  depends_on = [google_cloud_run_v2_job_iam_member.scheduler_invoker, google_project_service.required]
}

resource "google_cloud_scheduler_job" "delivery" {
  for_each = toset(local.delivery_times)

  name      = "mosaic-delivery-${replace(each.value, " ", "-")}"
  region    = var.region
  schedule  = "${each.value} * * *"
  time_zone = "Asia/Kolkata"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/v2/${google_cloud_run_v2_job.jobs["delivery"].id}:run"

    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }

  depends_on = [google_cloud_run_v2_job_iam_member.scheduler_invoker, google_project_service.required]
}
