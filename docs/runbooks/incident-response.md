# Incident response

CLAUDE.md requires this runbook to cover three things: a data breach, a
leaked secret, and sending wrong content. All three follow the same shape
— contain, assess, notify, remediate, record — but the specifics differ
enough that they're separate sections below.

**This is a draft, like `frontend/src/app/privacy` and `/terms`.** The
legal specifics in the data-breach section — what the DPDP Act actually
requires and on what timeline — need confirmation from counsel before this
is relied on during a real incident; nothing here should be read as legal
advice.

## General principles

1. **Contain first, understand second.** Stop the bleeding (rotate a
   secret, pull a story, pause sending) before you have a complete picture.
   A slower, well-understood remediation is still better than an
   unbounded ongoing leak.
2. **Admin alerts, not the app's own mail.** CLAUDE.md is explicit that
   admin alerts must never depend on the app's own Gmail sender, since
   that's exactly what an incident might have broken. Coordinate over
   whatever channel Cloud Monitoring's notification channel reaches
   (currently: email to `ADMIN_EMAIL`, see `infra/monitoring.tf`) or
   directly, out of band.
3. **Never delete evidence before it's captured.** `pipeline_runs`,
   `deliveries`, and `llm_calls` are the audit trail; export or note the
   relevant rows before any remediation step that might touch them (a
   secret rotation doesn't, a database restore might).
4. **Write it down afterwards.** Add a dated entry to
   `docs/runbooks/incident-log.md` (create it if this is the first
   incident) with what happened, what was affected, and what changed as a
   result. If the response to this incident revealed the runbook itself
   was wrong or incomplete, fix this file in the same pass.

## 1. Data breach

A breach here means personal data (`users.email`, `.name`, `.city_id`; not
anonymised deliveries/feedback rows) became visible to someone who
shouldn't have had it — a misconfigured bucket, a compromised database
credential, an exposed backup, a bug that leaked another user's data in a
response.

### Contain

- If the exposure is ongoing (e.g. a bucket left public, a route leaking
  data), close that specific hole immediately — before assessing full
  scope. For a database credential, see "Leaked secrets" below; rotating
  `DATABASE_URL` cuts off any access using the old credential right away.
- If the cause is a code bug, the fastest safe fix is usually pulling the
  affected route or field, not shipping a patch under pressure. A slightly
  degraded service beats a code fix that introduces a second bug.

### Assess

- Which table(s) and which rows. `users` is the only table holding
  identifying data directly; everything else (`deliveries`, `feedback`,
  `story_withdrawals`, etc.) references a `user_id` that's nulled on
  deletion and carries no personal data of its own.
- How many people, and whether any of them are minors — the service is
  18+ (`age_confirmed`), so this shouldn't apply, but confirm rather than
  assume.
- Time window: check `pipeline_runs` and application logs for when the
  exposure started and was closed, not just when it was noticed.

### Notify

India's DPDP Act (2023) requires notifying the Data Protection Board of
India and each affected Data Principal (user) of a personal data breach.
**Confirm the current DPDP Rules with counsel before acting on a
timeline** — the rules were still being finalised at the time this was
written, and the exact deadlines and required notification format may have
changed. Directionally: notify affected users without unnecessary delay,
in plain language, saying what happened, what data was involved, and what
you're doing about it — no jargon, no minimising. Notify the Board
promptly as well; do not wait for a complete forensic picture to make
first contact with either.

There is a published privacy contact for exactly this
(`frontend/src/app/privacy` — itself still a draft) — use it, or the
`ADMIN_EMAIL` address, as the point of contact.

### Remediate

- Rotate any credential that could have been the vector (see below).
- If reader accounts might have been accessed rather than just data
  exposed, force every session to end immediately: rotate
  `TOKEN_SIGNING_KEY`. Read the consequences of that in "Leaked secrets"
  first — it also invalidates every unsubscribe link ever sent.
- Consider whether affected users should be proactively offered account
  deletion (`POST /api/me/delete`) even though it's already
  self-service — a direct link in the notification lowers the bar during
  a moment when trust is already damaged.

## 2. Leaked secrets

Every secret lives in Secret Manager in prod (`infra/secrets.tf` creates
the containers; see `infra/README.md` for how values are set). **Rotating
a secret's value does not affect an already-running Cloud Run instance**:
Cloud Run resolves `secret_key_ref` env vars once, at container start, so
a new secret version only takes effect on the *next* revision — adding a
version alone changes nothing until something forces a redeploy. The
reliable way to force one is a real redeploy (`terraform apply`, even with
the same image tag, or `gcloud run deploy` / `gcloud run jobs deploy` with
the existing image) rather than an in-place `services update` with nothing
else changed, which may or may not create a new revision depending on
whether Cloud Run considers the spec to have changed.

| Secret | Rotate with | Consequences |
|---|---|---|
| `DATABASE_URL` | Rotate the credential at Neon, then `gcloud secrets versions add database-url` | None beyond a brief connection blip once the new revision is live. Old credential stops working the moment Neon rotates it, independent of Cloud Run picking up the new value. |
| `GMAIL_APP_PASSWORD` | Revoke the app password in the Google Account, generate a new one, `gcloud secrets versions add gmail-app-password` | Sending and bounce-reading both stop until the new revision is live. No reader-visible data is lost — queued deliveries retry on the next run. |
| `TOKEN_SIGNING_KEY` | `gcloud secrets versions add token-signing-key` | **The most disruptive rotation.** Every reader and admin session ends immediately (forces a re-login — this may be exactly what you want after a breach). Every outstanding feedback link, PDF link, and admin-login link stops working. Every unsubscribe link ever sent stops working too, because `unsubscribe_token()` derives its value from this key (`app/email/tokens.py`) — readers who try an old unsubscribe link land on the "that link is not valid" page, whose text already tells them to reply to any edition instead. Opt-in and magic-link tokens are unaffected: their stored hash doesn't depend on this key. |
| `LLMBUFFET_API_KEY` / `LLM_FALLBACK_API_KEY` | Rotate at the provider, `gcloud secrets versions add ...` | Build/late-update/ranker calls fail until the new revision is live; the pipeline's existing retry and fallback-provider logic handles this the same as any other outage. |
| `TURNSTILE_SECRET_KEY` | Rotate at Cloudflare, `gcloud secrets versions add turnstile-secret-key` | Until the new revision is live, the old (now-invalid-at-Cloudflare) secret makes every real signup fail Turnstile verification (`verify_turnstile` returns `False`, not an error) — signups are refused, not accepted insecurely, in the gap. If `TURNSTILE_SECRET_KEY` is ever unset entirely rather than just stale, `verify_turnstile` raises instead in prod (`app/api/security.py`) — refuses outright rather than silently skipping the check. |
| Any news/weather/market/sports/image/Langfuse key | Rotate at the provider, `gcloud secrets versions add <name>` | Scoped to whichever service/extra uses it; no cross-feature impact. |

If the leak was a **committed secret** (accidentally pushed to git), rotating
the value is necessary but not sufficient — the old value stays in git
history. Treat it as permanently public: rotate immediately, and don't
rely on rewriting history to contain it once a repository has a remote
(there is none yet — see `docs/BACKLOG.md`).

## 3. Sending wrong content

"Wrong" covers two different problems with different fixes:

### A story hasn't finished sending yet

Use the admin kill switch: `POST /admin/api/stories/{id}/withdraw` (or the
dashboard at `/admin`) with a reason. This publishes a new revision
without the story, and every delivery run after that point uses the new
revision — readers not yet sent today's edition won't get it. Readers
already sent it are the next case.

### A story already reached readers

**This is a real gap, not a solved path.** The `corrections` table exists
(`app/models/content.py`) and CLAUDE.md's process — mark the story
corrected in the archive, note the correction in the next edition for
affected readers — is specified, but no code writes to that table, renders
a correction in the archive, or adds a correction note to an edition yet.
Recorded in `docs/BACKLOG.md`. Until it's built, do this by hand:

1. Withdraw the story (above), so no one else receives it.
2. Insert a row directly:
   ```sql
   INSERT INTO corrections (id, story_id, description, corrected_at)
   VALUES (gen_random_uuid(), '<story_id>', '<what was wrong and what the correct information is>', now());
   ```
3. Identify affected readers. There is no ready-made query for "who
   received this specific story" — deliveries record a revision, not
   individual stories within it. As a starting point:
   ```sql
   SELECT DISTINCT d.user_id
   FROM deliveries d
   JOIN edition_revisions r ON r.id = d.revision_id
   JOIN editions e ON e.id = r.edition_id
   WHERE e.edition_date = '<edition_date>'
     AND d.type = 'newsletter'
     AND d.status = 'sent';
   ```
   This over-includes anyone sent *any* revision of that day, not just
   ones containing the story before it was withdrawn — narrow it by hand
   using `edition_sections` for the specific genre and revision range, or
   accept the over-inclusion for a correction (better to over-notify than
   miss someone).
4. Send a manual correction note to that list — there's no template for
   this yet either (`app/render/templates/system/` has failure and paused
   notices only). Keep it short: what was wrong, what's correct, no
   further action needed from the reader unless the error was
   consequential (e.g. a wrong figure that materially changes the story).
5. If the error was severe enough to warrant it, consider whether it's
   also a data-breach or trust issue (e.g. a factual error caused by
   sending one reader's personalised content to another) — if so, follow
   section 1 too.
