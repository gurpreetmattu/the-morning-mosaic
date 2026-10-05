# Security policy

## Reporting a vulnerability

Please do **not** open a public issue. Use GitHub's private reporting:
**Security → Report a vulnerability** on this repository.

Include what you found, how to reproduce it, and the impact. You can expect an acknowledgement
within 3 working days.

## Scope

In scope: the API, the website, the email and PDF links (signed tokens), the admin dashboard,
and the infrastructure code in `infra/`.

Subscriber personal data is handled under India's DPDP Act. If you believe personal data has been
exposed, say so in the report so it can be handled under the incident runbook in
[`docs/runbooks/incident-response.md`](docs/runbooks/incident-response.md).

## Supported versions

Only the current `main` branch (the deployed version) receives fixes.
