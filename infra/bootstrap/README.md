# Bootstrap: keyless GitHub -> Google Cloud login

A separate Terraform root, applied by hand by the owner, that lets the deploy workflow
(`.github/workflows/deploy.yml`) authenticate to Google Cloud without a stored key
(Workload Identity Federation). It is separate from `../` on purpose: the deploy account can
change nearly everything in `../`, but not this, so a compromised workflow cannot widen its own
access.

What it creates:

- a workload identity pool and a GitHub OIDC provider that **only accepts tokens from
  `gurpreetmattu/the-morning-mosaic` on `refs/heads/main`** (forks, pull requests and other
  branches get nothing);
- the service account `mosaic-deploy`, which only that identity may act as;
- the project roles `mosaic-deploy` needs to run `../`'s `terraform apply` (listed with the
  reason for each in `main.tf`; no Owner, Editor or IAM-admin role);
- the `sts` and `cloudresourcemanager` APIs.

No key is created or downloaded.

## Apply (owner, once)

```
cd infra/bootstrap
terraform init -backend-config="bucket=the-morning-mosaic-tfstate"
terraform plan  -var="project_id=the-morning-mosaic"
terraform apply -var="project_id=the-morning-mosaic"
terraform output
```

## Then set these GitHub repository variables

(Settings -> Secrets and variables -> Actions -> Variables)

| Variable | Value |
| --- | --- |
| `GCP_PROJECT_ID` | `the-morning-mosaic` (this one switches the deploy workflow on) |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `terraform output workload_identity_provider` |
| `GCP_DEPLOY_SERVICE_ACCOUNT` | `terraform output deploy_service_account` |
| `TURNSTILE_SITE_KEY` | the public Turnstile site key |
| `SENDER_EMAIL`, `ADMIN_EMAIL` | as in `../terraform.tfvars` |
| `LLM_GATEWAY_URL`, `LLM_SECONDARY_URL` | as in `../terraform.tfvars` |

Set `GCP_PROJECT_ID` last: until it exists the workflow does nothing.

## Undo

`terraform destroy -var="project_id=the-morning-mosaic"` removes everything here; the deploy
workflow then simply cannot authenticate. Nothing in `../` depends on it.
