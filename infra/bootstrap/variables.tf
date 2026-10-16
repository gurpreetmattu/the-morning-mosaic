variable "project_id" {
  description = "The GCP project the deploy runs against."
  type        = string
}

variable "region" {
  description = "Default region for the provider (nothing here is regional)."
  type        = string
  default     = "asia-south1"
}

variable "github_repository" {
  description = "owner/name of the repository whose main branch may deploy."
  type        = string
  default     = "gurpreetmattu/the-morning-mosaic"
}
