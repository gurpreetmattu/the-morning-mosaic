# Secret Manager holds only the values from backend/app/config/settings.py
# that are SecretStr. Terraform creates the containers and grants access;
# it never writes a value into any of them, so no secret ever passes
# through a `.tf` file, `terraform plan` output, or the state file.
#
# After `terraform apply`, populate at least the four the app cannot start
# without:
#
#   echo -n "<value>" | gcloud secrets versions add database-url --project=<project> --data-file=-
#
# ...and likewise for gmail-app-password, token-signing-key, and
# freellmpool-api-key. Everything else here is optional in Settings and can
# stay empty until the corresponding provider account exists (see
# docs/BACKLOG.md's blockers) — a job that needs one and finds it unset
# fails exactly as it would locally with a missing .env entry.

locals {
  secret_ids = [
    "database-url",
    "gmail-app-password",
    "token-signing-key",
    "freellmpool-api-key",
    "llm-fallback-api-key",
    "turnstile-secret-key",
    "newsdata-api-key",
    "gnews-api-key",
    "newsapi-key",
    "openweathermap-api-key",
    "market-api-key",
    "sports-api-key",
    "tmdb-api-key",
    "unsplash-access-key",
    "pexels-api-key",
    "langfuse-public-key",
    "langfuse-secret-key",
  ]
}

resource "google_secret_manager_secret" "this" {
  for_each  = toset(local.secret_ids)
  project   = var.project_id
  secret_id = each.value
  labels    = local.labels

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

# Every backend workload (the api service and all six jobs) reads the same
# Settings class, so all of them can read all of these secrets.
resource "google_secret_manager_secret_iam_member" "backend_access" {
  for_each = {
    for pair in setproduct(local.secret_ids, [
      google_service_account.api.email,
      google_service_account.jobs.email,
      ]) : "${pair[0]}-${pair[1]}" => {
      secret = pair[0]
      member = pair[1]
    }
  }

  project   = var.project_id
  secret_id = google_secret_manager_secret.this[each.value.secret].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${each.value.member}"
}
