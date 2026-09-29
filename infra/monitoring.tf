# CLAUDE.md: "Admin alerts go through Cloud Monitoring notification
# channels ... never through the app's own Gmail sender, so alerts still
# arrive when sending is broken."
#
# Two of CLAUDE.md's four alert conditions (job-execution failure, api 5xx
# rate) use Cloud Run's own built-in metrics directly, below. The other two
# (a build's deadline miss, a sharp drop in verified story counts) have no
# Cloud Run metric to read — they are properties of a job's own outcome,
# recorded in `pipeline_runs` (Postgres/Neon, outside GCP, so Cloud
# Monitoring cannot query it directly). Structured JSON logging to stdout
# (app/logging_config.py) is the bridge: app/jobs/build.py and
# app/jobs/late_update.py log a specific, greppable message for each
# condition, a `google_logging_metric` below counts matching log lines as a
# metric, and an alert policy fires on it exactly like the two direct ones.

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

# ------------------------------------------------------- log-based signals
#
# Both jobs log the exact same message text ("build_deadline_missed ...") on
# a missed deadline — app/jobs/build.py's own comment explains why a shared,
# greppable literal beats matching on log level alone (WARNING covers other
# things too). One metric and one alert policy covers both jobs' log
# streams, since the filter below has no job_name restriction.

resource "google_logging_metric" "build_deadline_missed" {
  name   = "build_deadline_missed"
  filter = <<-EOT
    resource.type="cloud_run_job"
    jsonPayload.event:"build_deadline_missed"
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }

  depends_on = [google_project_service.required]
}

resource "google_monitoring_alert_policy" "build_deadline_missed" {
  display_name = "A build or late update missed its publish deadline"
  combiner     = "OR"

  conditions {
    display_name = "build_deadline_missed log entries"

    condition_threshold {
      filter = <<-EOT
        resource.type="cloud_run_job"
        AND metric.type="logging.googleapis.com/user/${google_logging_metric.build_deadline_missed.name}"
      EOT

      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_COUNT"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.admin_email.id]

  documentation {
    content   = "A build or late-update run logged a missed publish deadline. Check `GET /admin/api/runs` in the admin dashboard for which run and its detail."
    mime_type = "text/markdown"
  }
}

resource "google_logging_metric" "verified_story_count_drop" {
  name   = "verified_story_count_drop"
  filter = <<-EOT
    resource.type="cloud_run_job"
    resource.labels.job_name="${google_cloud_run_v2_job.jobs["build"].name}"
    jsonPayload.event:"verified_story_count_drop"
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }

  depends_on = [google_project_service.required]
}

resource "google_monitoring_alert_policy" "verified_story_count_drop" {
  display_name = "Sharp drop in verified story counts"
  combiner     = "OR"

  conditions {
    display_name = "verified_story_count_drop log entries"

    condition_threshold {
      filter = <<-EOT
        resource.type="cloud_run_job"
        AND metric.type="logging.googleapis.com/user/${google_logging_metric.verified_story_count_drop.name}"
      EOT

      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_COUNT"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.admin_email.id]

  documentation {
    content   = "The build job's verified story count dropped sharply against its own rolling baseline (app/jobs/build.py: STORY_COUNT_DROP_THRESHOLD). Check `GET /admin/api/runs` for today's per-genre outcome."
    mime_type = "text/markdown"
  }
}
