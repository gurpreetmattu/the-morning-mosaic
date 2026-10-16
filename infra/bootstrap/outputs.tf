# These two become GitHub repository variables (infra/README.md, "Deploying from GitHub").
output "workload_identity_provider" {
  description = "GCP_WORKLOAD_IDENTITY_PROVIDER"
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "deploy_service_account" {
  description = "GCP_DEPLOY_SERVICE_ACCOUNT"
  value       = google_service_account.deploy.email
}
