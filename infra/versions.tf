terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.5"
    }
  }

  # Bucket name is supplied at `terraform init -backend-config=...` time,
  # not hardcoded here, so the same config works before the bucket exists
  # (bootstrap, see README) and after (normal use). Terraform refuses a
  # `backend "gcs" {}` block with variables inside it, which is why this is
  # empty rather than referencing var.state_bucket.
  backend "gcs" {}
}
