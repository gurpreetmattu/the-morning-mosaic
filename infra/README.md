# Terraform — The Morning Mosaic

Provisions everything CLAUDE.md's Deployment section names: two Cloud Run
services (`web`, `api`), seven Cloud Run jobs, Cloud Scheduler triggers for
each at the times in CLAUDE.md's "Jobs" section, Secret Manager containers,
Artifact Registry, the PDF cache bucket, and two Cloud Monitoring alerts.

**Nothing here has been applied.** There is no GCP project for this
project yet (see the Blockers section of `docs/BACKLOG.md`); this config
has been checked with `terraform fmt` and `terraform validate` only —
`terraform plan`/`apply` need real credentials against a real project,
which don't exist in this environment. Read this file before the first
real apply.

## Architecture, in one paragraph

There is no load balancer and no custom domain. `web` (Next.js) is the only
public origin; `frontend/src/proxy.ts` forwards the JSON API and every
emailed-link page to `api` server-side, so the backend's session and CSRF
cookies — first-party by design — actually work. `BASE_URL` (embedded in
every email) is `web`'s own Cloud Run URL. See `frontend/README.md` for the
full reasoning and `frontend/next.config.ts` / `frontend/src/proxy.ts` for
the code. When a custom domain exists later, mapping it to `web` is the
only change this implies anywhere.

## One-time bootstrap

Terraform's own state needs a GCS bucket that this config can't create for
itself (the backend has to exist before `terraform init` can use it):

```
gcloud config set project <project-id>
gcloud services enable storage.googleapis.com
gcloud storage buckets create gs://<project-id>-tfstate --location=asia-south1 --uniform-bucket-level-access
```

Then:

```
cd infra
terraform init -backend-config="bucket=<project-id>-tfstate"
cp terraform.tfvars.example terraform.tfvars   # fill in project_id, sender_email, admin_email, freellmpool_url
```

## Images

Terraform deploys images; it does not build them. `.github/workflows/deploy.yml`
builds and pushes both on every push to `main`, but only once a `GCP_PROJECT_ID`
repository variable exists — until then it's a no-op, since there's no GCP
project for it to push to (see `docs/BACKLOG.md`). Before the first real
apply, or any time before that variable is set, build and push both by
hand:

```
gcloud auth configure-docker asia-south1-docker.pkg.dev

docker build -f backend/Dockerfile -t asia-south1-docker.pkg.dev/<project-id>/the-morning-mosaic/backend:manual .
docker push asia-south1-docker.pkg.dev/<project-id>/the-morning-mosaic/backend:manual

docker build -f frontend/Dockerfile -t asia-south1-docker.pkg.dev/<project-id>/the-morning-mosaic/web:manual frontend
docker push asia-south1-docker.pkg.dev/<project-id>/the-morning-mosaic/web:manual
```

(The Artifact Registry repo those paths reference is itself created by
`terraform apply`, which is a chicken-and-egg problem the first time
through: apply once with the default placeholder images first — the
services will exist but their revisions won't serve — push the real images
to the now-existing repo, then set `backend_image`/`web_image` in
`terraform.tfvars` and apply again.)

## Apply, twice

The first apply creates everything, including both Cloud Run services, but
`api`'s `BASE_URL` can't yet be `web`'s real URL — that would make `api`
depend on `web`'s Terraform output while `web` already depends on `api`'s
(for `BACKEND_ORIGIN`), a dependency cycle Terraform refuses to plan. See
the `base_url` variable in `variables.tf`.

```
terraform apply                     # creates everything; api's BASE_URL is a placeholder
terraform output web_url            # read the real URL
# set base_url = "<that>" in terraform.tfvars
terraform apply                     # api now has the right BASE_URL
```

Every apply after that is a normal, single-pass `terraform apply`.

## Secrets

Terraform creates the Secret Manager **containers** in `secrets.tf` and
grants the api/jobs service accounts read access to all of them; it never
writes a value into any of them, so no secret ever appears in a `.tf` file,
a `terraform plan`, or the state file. Populate at least the four the app
cannot start without:

```
printf '%s' '<value>' | gcloud secrets versions add database-url         --data-file=-
printf '%s' '<value>' | gcloud secrets versions add gmail-app-password   --data-file=-
printf '%s' '<value>' | gcloud secrets versions add token-signing-key    --data-file=-
printf '%s' '<value>' | gcloud secrets versions add freellmpool-api-key    --data-file=-
```

Everything else in `secrets.tf` corresponds to an optional field in
`backend/app/config/settings.py` and can stay empty until the matching
provider account exists (see `docs/BACKLOG.md`'s blockers) — a job that
needs one and finds it unset fails exactly as it would locally with a
missing `.env` entry.

A Cloud Run revision that references a secret with no version will exist
but won't become ready. That's expected until the four above are set.

## What isn't here

- **CI actually running.** `.github/workflows/{ci,deploy,evals-nightly}.yml`
  exist and lint/typecheck/test/validate on every PR (verified — see
  `docs/BACKLOG.md`), but nothing has ever executed on GitHub's own
  infrastructure: there is no git remote yet, so no repository for a
  workflow to run in.
- **`deploy.yml`'s Workload Identity Federation setup.** The workflow
  authenticates via WIF rather than a downloaded service account key, but
  the WIF pool/provider/service-account binding it expects
  (`GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_DEPLOY_SERVICE_ACCOUNT` repository
  variables) don't exist yet either — another thing that needs the GCP
  project first.
- **A custom domain / load balancer** — deliberately not needed for this
  architecture; see above.
- **Alerting beyond two conditions** (a failed job execution, api 5xx
  responses). CLAUDE.md also wants alerts on deadline misses and sharp
  drops in verified story counts; both need either structured logging or a
  custom metric neither of which exist yet (`docs/BACKLOG.md`).
- **Neon.** CLAUDE.md specifies Postgres on Neon, not Cloud SQL, so
  `DATABASE_URL` is a plain secret value here, not a Terraform-managed
  database resource — there is nothing for Terraform to provision.
