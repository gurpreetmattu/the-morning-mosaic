# Keyless GitHub Actions -> Google Cloud login (Workload Identity Federation).
#
# This is a SEPARATE Terraform root from ../ on purpose, and only the owner applies it by
# hand. The deploy service account it creates is what the CI deploy runs as, and that account
# can change almost everything in ../ — but not this: it has no permission over IAM, workload
# identity pools or its own roles. If this lived in the same state the CI apply would manage
# (and could rewrite) its own access.
#
# Nothing here is a secret: no key is ever created or downloaded. GitHub proves who it is with a
# short-lived token, and Google only accepts it from the repository and branch named below.

provider "google" {
  project = var.project_id
  region  = var.region
}

# The two APIs the token exchange needs, and the one Terraform's Google provider uses to read
# project details. (iam and iamcredentials are already enabled by ../apis.tf and the project.)
resource "google_project_service" "federation" {
  for_each = toset([
    "sts.googleapis.com",
    "cloudresourcemanager.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions"
  description               = "Tokens issued to GitHub Actions workflows"

  depends_on = [google_project_service.federation]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub OIDC"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  # Refuse every token that is not from this repository's main branch. A fork, another
  # repository, a pull request or a feature branch cannot get a Google credential at all.
  attribute_condition = "assertion.repository == \"${var.github_repository}\" && assertion.ref == \"refs/heads/main\""
}

resource "google_service_account" "deploy" {
  account_id   = "mosaic-deploy"
  display_name = "GitHub Actions deploy"
  description  = "Builds and pushes images and applies infra/ from .github/workflows/deploy.yml"

  depends_on = [google_project_service.federation]
}

# Only identities from the repository (already narrowed to main above) may act as it.
resource "google_service_account_iam_member" "github_can_deploy" {
  service_account_id = google_service_account.deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

# What `terraform apply` in ../ needs, resource type by resource type. Deliberately no
# roles/owner, roles/editor or any IAM-admin role.
locals {
  deploy_roles = {
    # google_artifact_registry_repository, and `docker push`
    "roles/artifactregistry.admin" = "images and the registry repository"
    # google_cloud_run_v2_service / _job and their *_iam_member bindings
    "roles/run.admin" = "Cloud Run services, jobs and their invoker bindings"
    # google_cloud_scheduler_job
    "roles/cloudscheduler.admin" = "Scheduler triggers"
    # google_secret_manager_secret and its iam_member bindings (containers only, never values)
    "roles/secretmanager.admin" = "Secret Manager containers and access grants"
    # google_storage_bucket (PDF cache) and the Terraform state bucket
    "roles/storage.admin" = "the PDF cache bucket and the Terraform state"
    # google_monitoring_alert_policy / _notification_channel
    "roles/monitoring.admin" = "alert policies and the notification channel"
    # google_logging_metric
    "roles/logging.configWriter" = "log-based metrics"
    # google_service_account (the four runtime accounts)
    "roles/iam.serviceAccountAdmin" = "the runtime service accounts"
    # deploy Cloud Run / Scheduler as those runtime accounts
    "roles/iam.serviceAccountUser" = "running services and jobs as the runtime accounts"
    # google_project_service
    "roles/serviceusage.serviceUsageAdmin" = "enabling APIs"
  }
}

resource "google_project_iam_member" "deploy" {
  for_each = local.deploy_roles

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.deploy.email}"
}
