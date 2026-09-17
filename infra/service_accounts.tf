# One service account per workload kind rather than the default compute
# service account, so a compromised container can't reach anything beyond
# what its own job actually needs.

resource "google_service_account" "web" {
  account_id   = "mosaic-web"
  display_name = "The Morning Mosaic — web (Next.js)"
  description  = "Runs the frontend. Proxies to the api service over HTTPS; holds no GCP permissions of its own."
  depends_on   = [google_project_service.required]
}

resource "google_service_account" "api" {
  account_id   = "mosaic-api"
  display_name = "The Morning Mosaic — api (FastAPI)"
  description  = "Runs the api service: Secret Manager access for its own config, and read/write on the PDF cache bucket."
  depends_on   = [google_project_service.required]
}

resource "google_service_account" "jobs" {
  account_id   = "mosaic-jobs"
  display_name = "The Morning Mosaic — scheduled jobs"
  # Shared by all seven jobs rather than one account each: they need
  # identical permissions, so per-job accounts would just be seven copies of
  # the same policy to keep in sync (see secrets.tf).
  description = "Runs the seven scheduled jobs: purge, feedback, build, late_update, delivery, failure_notice, bounces."
  depends_on  = [google_project_service.required]
}

resource "google_service_account" "scheduler" {
  account_id   = "mosaic-scheduler"
  display_name = "The Morning Mosaic — Cloud Scheduler invoker"
  description  = "Cloud Scheduler authenticates as this account to call each job's :run endpoint. Holds no permission beyond run.invoker on those seven jobs (see cloud_scheduler.tf)."
  depends_on   = [google_project_service.required]
}

# The PDF cache bucket is the api service's alone (per-user PDFs are
# assembled and cached there on first download); jobs never touch it.
resource "google_storage_bucket_iam_member" "api_pdf_cache" {
  bucket = google_storage_bucket.pdf_cache.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.api.email}"
}
