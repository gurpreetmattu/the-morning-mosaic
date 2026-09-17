locals {
  labels = {
    app = "the-morning-mosaic"
  }

  artifact_registry_host = "${var.region}-docker.pkg.dev"
  repo_path              = "${local.artifact_registry_host}/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"

  # Placeholders so `terraform plan`/`apply` work before CI has pushed a
  # real image (there is no CI yet — see docs/BACKLOG.md). Cloud Run will
  # accept the resource but the revision won't become ready until a real
  # image replaces this; that's a deploy-time problem, not a plan-time one.
  backend_image = coalesce(var.backend_image, "${local.repo_path}/backend:unset")
  web_image     = coalesce(var.web_image, "${local.repo_path}/web:unset")

  # Every Cloud Run workload (the api service and all seven jobs) shares this
  # non-secret configuration. Job-specific and service-specific values
  # (BASE_URL, BACKEND_ORIGIN, the job's own module) are added where each
  # is defined.
  common_env = {
    APP_ENV                   = "prod"
    BASE_URL                  = var.base_url
    TIMEZONE                  = var.timezone
    LOG_LEVEL                 = var.log_level
    GCP_PROJECT_ID            = var.project_id
    GCP_REGION                = var.region
    SMTP_HOST                 = var.smtp_host
    SMTP_PORT                 = tostring(var.smtp_port)
    SENDER_EMAIL              = var.sender_email
    SENDER_NAME               = var.sender_name
    IMAP_HOST                 = var.imap_host
    IMAP_PORT                 = tostring(var.imap_port)
    ADMIN_EMAIL               = var.admin_email
    TEST_EMAIL_ALLOWLIST      = var.test_email_allowlist
    MAX_ACTIVE_SUBSCRIBERS    = tostring(var.max_active_subscribers)
    FAILURE_NOTICE_AUTO_LIMIT = tostring(var.failure_notice_auto_limit)
    LLM_GATEWAY_URL           = var.llm_gateway_url
    LLM_FALLBACK_URL          = var.llm_fallback_url
    TURNSTILE_SITE_KEY        = var.turnstile_site_key
    GCS_PDF_BUCKET            = google_storage_bucket.pdf_cache.name
  }

  # name -> Secret Manager secret id. Values are never set by Terraform
  # (see secrets.tf) — only the containers are declared here, so a secret
  # can be referenced by every workload uniformly whether or not a human
  # has populated it yet.
  secret_env = {
    DATABASE_URL           = google_secret_manager_secret.this["database-url"].secret_id
    GMAIL_APP_PASSWORD     = google_secret_manager_secret.this["gmail-app-password"].secret_id
    TOKEN_SIGNING_KEY      = google_secret_manager_secret.this["token-signing-key"].secret_id
    LLM_GATEWAY_API_KEY    = google_secret_manager_secret.this["llm-gateway-api-key"].secret_id
    LLM_FALLBACK_API_KEY   = google_secret_manager_secret.this["llm-fallback-api-key"].secret_id
    TURNSTILE_SECRET_KEY   = google_secret_manager_secret.this["turnstile-secret-key"].secret_id
    NEWSDATA_API_KEY       = google_secret_manager_secret.this["newsdata-api-key"].secret_id
    GNEWS_API_KEY          = google_secret_manager_secret.this["gnews-api-key"].secret_id
    NEWSAPI_KEY            = google_secret_manager_secret.this["newsapi-key"].secret_id
    OPENWEATHERMAP_API_KEY = google_secret_manager_secret.this["openweathermap-api-key"].secret_id
    MARKET_API_KEY         = google_secret_manager_secret.this["market-api-key"].secret_id
    SPORTS_API_KEY         = google_secret_manager_secret.this["sports-api-key"].secret_id
    TMDB_API_KEY           = google_secret_manager_secret.this["tmdb-api-key"].secret_id
    UNSPLASH_ACCESS_KEY    = google_secret_manager_secret.this["unsplash-access-key"].secret_id
    PEXELS_API_KEY         = google_secret_manager_secret.this["pexels-api-key"].secret_id
    LANGFUSE_PUBLIC_KEY    = google_secret_manager_secret.this["langfuse-public-key"].secret_id
    LANGFUSE_SECRET_KEY    = google_secret_manager_secret.this["langfuse-secret-key"].secret_id
  }
}
