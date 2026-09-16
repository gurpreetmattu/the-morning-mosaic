output "web_url" {
  description = "Set this as var.base_url and re-apply — see the base_url variable and infra/README.md."
  value       = google_cloud_run_v2_service.web.uri
}

output "api_url" {
  value = google_cloud_run_v2_service.api.uri
}

output "artifact_registry_repo" {
  description = "Push images here: {this}/backend:<tag>, {this}/web:<tag>."
  value       = local.repo_path
}

output "pdf_cache_bucket" {
  value = google_storage_bucket.pdf_cache.name
}

output "service_accounts" {
  value = {
    web       = google_service_account.web.email
    api       = google_service_account.api.email
    jobs      = google_service_account.jobs.email
    scheduler = google_service_account.scheduler.email
  }
}
