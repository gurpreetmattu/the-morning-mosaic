# CLAUDE.md: assembled PDFs are "cached in Cloud Storage (30-day lifecycle
# rule)". Matches app/storage.py's GcsObjectStorage and the two-tier key
# layout the PDF route writes: pdf/readers/{revision}/{user}.pdf (one
# finished document per reader). Private:
# the api service streams bytes to the browser itself (see
# app/api/routes/pdf.py), nothing here is ever public.

resource "google_storage_bucket" "pdf_cache" {
  name                        = "${var.project_id}-pdf-cache"
  location                    = var.region
  uniform_bucket_level_access = true
  labels                      = local.labels

  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.required]
}
