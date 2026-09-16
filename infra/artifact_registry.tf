resource "google_artifact_registry_repository" "images" {
  repository_id = "the-morning-mosaic"
  location      = var.region
  format        = "DOCKER"
  description   = "backend and web images, pushed by CI (not yet built — see docs/BACKLOG.md)"
  labels        = local.labels

  depends_on = [google_project_service.required]
}
