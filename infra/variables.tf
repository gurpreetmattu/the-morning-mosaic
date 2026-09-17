variable "project_id" {
  description = "GCP project. Must already exist and be billing-enabled."
  type        = string
}

variable "region" {
  description = "CLAUDE.md pins this to Mumbai for latency to Indian readers."
  type        = string
  default     = "asia-south1"
}

variable "backend_image" {
  description = <<-EOT
    Full Artifact Registry URI, with tag, for the backend image (built from
    backend/Dockerfile). Terraform does not build or push images — that's
    CI's job (not yet built; see docs/BACKLOG.md) — it only deploys
    whatever this points at. Defaults to a placeholder tag in the registry
    this config creates, so `terraform plan` works before any image has
    been pushed; deploying anything real means overriding it.
  EOT
  type        = string
  default     = null
}

variable "web_image" {
  description = "Full Artifact Registry URI, with tag, for the frontend image (built from frontend/Dockerfile). See backend_image."
  type        = string
  default     = null
}

# --- Application configuration (non-secret; see secrets.tf for the rest) ---
# Mirrors backend/app/config/settings.py. Kept as Terraform variables rather
# than hardcoded so the same config can (eventually) serve more than one
# environment; there is only one today — CLAUDE.md's "prod" — dev is local
# and never touches this.

variable "timezone" {
  type    = string
  default = "Asia/Kolkata"
}

variable "log_level" {
  type    = string
  default = "INFO"
}

variable "smtp_host" {
  type    = string
  default = "smtp.gmail.com"
}

variable "smtp_port" {
  type    = number
  default = 587
}

variable "sender_email" {
  description = "The Gmail address the app sends from."
  type        = string
}

variable "sender_name" {
  type    = string
  default = "The Morning Mosaic"
}

variable "imap_host" {
  type    = string
  default = "imap.gmail.com"
}

variable "imap_port" {
  type    = number
  default = 993
}

variable "base_url" {
  description = <<-EOT
    The single public origin — the web service's own URL — embedded in
    every email link and used for CORS. Deliberately NOT derived from
    google_cloud_run_v2_service.web.uri: that would make the api service
    depend on web's URL while web already depends on api's (for
    BACKEND_ORIGIN), a dependency cycle Terraform can't resolve. Instead:
    apply once, read `terraform output web_url`, set this variable to it,
    apply again. See infra/README.md.
  EOT
  type        = string
  default     = "https://web-url-not-yet-known.invalid"
}

variable "admin_email" {
  description = "The one allowlisted admin-dashboard address, and where Cloud Monitoring alerts go."
  type        = string
}

variable "test_email_allowlist" {
  description = "Comma-separated addresses dev may email. Irrelevant in prod (Settings.may_send_to is unconditional there) but declared for completeness."
  type        = string
  default     = ""
}

variable "max_active_subscribers" {
  type    = number
  default = 400
}

variable "failure_notice_auto_limit" {
  type    = number
  default = 50
}

variable "llm_gateway_url" {
  description = "The LLM gateway's URL — a real, publicly reachable endpoint (Groq, as of this writing), not the local freellmpool aggregator this project used to run against 127.0.0.1. See docs/BACKLOG.md's now-closed gateway-reachability blocker."
  type        = string
}

variable "llm_fallback_url" {
  type    = string
  default = ""
}

variable "turnstile_site_key" {
  description = "Public; the matching secret key lives in Secret Manager (secrets.tf)."
  type        = string
  default     = ""
}

# --- Cloud Run sizing ---

variable "web_min_instances" {
  type    = number
  default = 0
}

variable "web_max_instances" {
  type    = number
  default = 2
}

variable "api_min_instances" {
  type    = number
  default = 0
}

variable "api_max_instances" {
  type    = number
  default = 2
}

variable "job_timeout_seconds" {
  description = "Applies to every Cloud Run job. CLAUDE.md: 'Job timeouts set explicitly.'"
  type        = number
  default     = 600
}
