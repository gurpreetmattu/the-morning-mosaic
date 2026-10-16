terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # Same state bucket as ../, under its own prefix so the two roots never share a state.
  # Initialise with: terraform init -backend-config="bucket=<project-id>-tfstate"
  backend "gcs" {
    prefix = "bootstrap"
  }
}
