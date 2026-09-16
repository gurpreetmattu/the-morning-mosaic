# The Next.js frontend. This is the single public origin: every emailed
# link and every browser request goes through here, and `frontend/src/proxy.ts`
# forwards what FastAPI needs to serve directly to the api service (see the
# comment in next.config.ts for why, and infra/README.md for the two-step
# apply this implies for BASE_URL).

resource "google_cloud_run_v2_service" "web" {
  name                = "mosaic-web"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false
  labels              = local.labels

  template {
    service_account = google_service_account.web.email

    scaling {
      min_instance_count = var.web_min_instances
      max_instance_count = var.web_max_instances
    }

    containers {
      image = local.web_image

      env {
        name  = "BACKEND_ORIGIN"
        value = google_cloud_run_v2_service.api.uri
      }

      ports {
        container_port = 8080
      }

      startup_probe {
        http_get {
          path = "/"
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

resource "google_cloud_run_v2_service_iam_member" "web_public" {
  name     = google_cloud_run_v2_service.web.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}
