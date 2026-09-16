# CLAUDE.md: "Admin alerts go through Cloud Monitoring notification
# channels ... never through the app's own Gmail sender, so alerts still
# arrive when sending is broken."
#
# Alert conditions use Cloud Run's own built-in execution-count metric
# rather than anything the app logs itself: app/jobs/*.py record everything
# in `pipeline_runs` (and the admin dashboard's GET /admin/api/runs surfaces
# it — see docs/BACKLOG.md), but nothing in there is exported as a Cloud
# Monitoring metric yet, and structured logging isn't wired up either (also
# in the backlog). A failed Cloud Run execution is the one signal available
# today that doesn't depend on either.

resource "google_monitoring_notification_channel" "admin_email" {
  display_name = "Admin email"
  type         = "email"

  labels = {
    email_address = var.admin_email
  }

  depends_on = [google_project_service.required]
}

resource "google_monitoring_alert_policy" "job_failed" {
  display_name = "A scheduled job failed"
  combiner     = "OR"

  conditions {
    display_name = "Cloud Run job execution failed"

    condition_threshold {
      filter = <<-EOT
        resource.type = "cloud_run_job"
        AND metric.type = "run.googleapis.com/job/completed_execution_count"
        AND metric.labels.result = "failed"
      EOT

      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_COUNT"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["resource.label.job_name"]
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.admin_email.id]

  documentation {
    content   = "A Cloud Run job execution failed. Check `GET /admin/api/runs` in the admin dashboard, or `gcloud run jobs executions list`, for which one and why."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "api_error_rate" {
  display_name = "api service is returning server errors"
  combiner     = "OR"

  conditions {
    display_name = "5xx responses from mosaic-api"

    condition_threshold {
      filter = <<-EOT
        resource.type = "cloud_run_revision"
        AND resource.labels.service_name = "${google_cloud_run_v2_service.api.name}"
        AND metric.type = "run.googleapis.com/request_count"
        AND metric.labels.response_code_class = "5xx"
      EOT

      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "60s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_COUNT"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.admin_email.id]
}
