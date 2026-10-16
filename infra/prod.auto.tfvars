# Production settings that are NOT secret and must be the same on every apply,
# wherever it runs. Terraform loads *.auto.tfvars by itself, so a local
# `terraform apply` and the GitHub Actions deploy (.github/workflows/deploy.yml)
# both see these. The CI workflow cannot see the gitignored terraform.tfvars, which is
# why anything that has to survive a CI deploy lives here and not there.
#
# Never put a secret or an email address in this file: the repository is public.
# Emails, the LLM gateway URLs and the Turnstile key come from repository variables
# in CI and from terraform.tfvars locally. Secrets live in Secret Manager.

# The web service's own URL: every emailed link and CORS use it. Without this a CI apply
# would reset it to the placeholder in variables.tf and break every link in every email.
# Change it when a custom domain is mapped (see infra/README.md).
base_url = "https://mosaic-web-297073209731.asia-south1.run.app"

# Scheduler triggers kept paused on purpose. late-update-2 is the 07:05 late update, paused
# because it starved the build on alternate days (docs/BACKLOG.md). Dropping this line would
# un-pause it on the next apply.
paused_schedules = ["late-update-2"]

sender_name = "The Morning Mosaic"

# Gemini's OpenAI-compatible endpoint: the configured fallback provider (CLAUDE.md, LLM access).
llm_fallback_url = "https://generativelanguage.googleapis.com/v1beta/openai"
