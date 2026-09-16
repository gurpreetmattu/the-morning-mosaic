# The FastAPI backend. Not meant to be reached by a browser directly — the
# web service proxies everything a browser needs (see
# frontend/src/proxy.ts) — but it's left publicly invokable rather than
# locked to the web service's identity, because the app doesn't mint
# identity tokens for its own server-to-server calls yet. Tightening that
# is real work, not a Terraform flag; noted in docs/BACKLOG.md.

resource "google_cloud_run_v2_service" "api" {
  name                = "mosaic-api"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false
  labels              = local.labels

  template {
    service_account = google_service_account.api.email

    scaling {
      min_instance_count = var.api_min_instances
      max_instance_count = var.api_max_instances
    }

    containers {
      image   = local.backend_image
      command = ["uvicorn"]
      args    = ["app.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]

      ports {
        container_port = 8080
      }

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

      startup_probe {
        http_get {
          path = "/healthz"
        }
        initial_delay_seconds = 5
        period_seconds        = 5
        failure_threshold     = 6
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [google_project_service.required]
}

resource "google_cloud_run_v2_service_iam_member" "api_public" {
  name     = google_cloud_run_v2_service.api.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}
