"use client";

import { useEffect, useState } from "react";
import { adminPost, ApiError, apiGet, publicPost } from "@/lib/api";
import type {
  CorrectionSummary,
  NoticeBatchSummary,
  RunSummary,
  SiteStatus,
  StatusMessage,
  StuckDelivery,
  WithdrawalSummary,
} from "@/lib/types";
import { Button, Field, Lede, Notice, PageTitle, textInputClasses } from "@/components/ui";

export default function AdminPage() {
  const [loading, setLoading] = useState(true);
  const [signedIn, setSignedIn] = useState(false);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    apiGet<{ email: string }>("/admin/api/me")
      .then(() => setSignedIn(true))
      .catch((err) => {
        // 401/403 mean "sign in"; anything else is an outage, not a sign-out.
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          setSignedIn(false);
        } else {
          setLoadError(true);
        }
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <p role="status" className="font-gothic text-ink-soft">
        Loading&hellip;
      </p>
    );
  }
  if (loadError) {
    return (
      <div>
        <PageTitle>Admin</PageTitle>
        <Notice kind="error">Couldn&rsquo;t reach the server. Reload to try again.</Notice>
      </div>
    );
  }
  return signedIn ? <Dashboard /> : <LoginRequest />;
}

function LoginRequest() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState<StatusMessage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      setSent(await publicPost<StatusMessage>("/admin/api/login", { email }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  if (sent) {
    return (
      <div>
        <PageTitle>Check your email</PageTitle>
        <Notice kind="success">{sent.message}</Notice>
      </div>
    );
  }

  return (
    <div>
      <PageTitle>Admin sign-in</PageTitle>
      <Lede>Restricted to the allowlisted owner address.</Lede>
      {error && <Notice kind="error">{error}</Notice>}
      <form onSubmit={handleSubmit}>
        <Field htmlFor="admin-email" label="Email">
          <input
            id="admin-email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={textInputClasses("mt-1")}
          />
        </Field>
        <Button type="submit" disabled={submitting}>
          {submitting ? "Sending…" : "Send sign-in link"}
        </Button>
      </form>
    </div>
  );
}

function Dashboard() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [stuck, setStuck] = useState<StuckDelivery[]>([]);
  const [notices, setNotices] = useState<NoticeBatchSummary[]>([]);
  const [withdrawals, setWithdrawals] = useState<WithdrawalSummary[]>([]);
  const [corrections, setCorrections] = useState<CorrectionSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  // A destructive action waits here for a second, explicit click.
  const [confirming, setConfirming] = useState<
    { kind: "withdraw" } | { kind: "notice"; date: string; action: "approve" | "suppress" } | null
  >(null);
  const [storyId, setStoryId] = useState("");
  const [reason, setReason] = useState("");
  const [correctionStoryId, setCorrectionStoryId] = useState("");
  const [description, setDescription] = useState("");
  const [siteStatus, setSiteStatus] = useState<SiteStatus | null>(null);
  const [statusDegraded, setStatusDegraded] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");

  async function refresh() {
    try {
      const [runsData, stuckData, noticesData, withdrawalsData, correctionsData, statusData] =
        await Promise.all([
          apiGet<RunSummary[]>("/admin/api/runs"),
          apiGet<StuckDelivery[]>("/admin/api/deliveries/stuck"),
          apiGet<NoticeBatchSummary[]>("/admin/api/notices"),
          apiGet<WithdrawalSummary[]>("/admin/api/withdrawals"),
          apiGet<CorrectionSummary[]>("/admin/api/corrections"),
          apiGet<SiteStatus>("/admin/api/status"),
        ]);
      setRuns(runsData);
      setStuck(stuckData);
      setNotices(noticesData);
      setWithdrawals(withdrawalsData);
      setCorrections(correctionsData);
      setSiteStatus(statusData);
      setStatusDegraded(statusData.degraded);
      setStatusMessage(statusData.message ?? "");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load the dashboard.");
    }
  }

  useEffect(() => {
    // `refresh` awaits before touching state, so this is genuinely
    // asynchronous — the rule can't see across the function boundary, and
    // `refresh` is reused below by `decide` and `withdraw` too, so it can't
    // simply be inlined as a `.then()` chain here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, []);

  async function decide(editionDate: string, action: "approve" | "suppress") {
    setBusy(true);
    setError(null);
    setDone(null);
    setConfirming(null);
    try {
      await adminPost(`/admin/api/notices/${editionDate}/${action}`);
      setDone(
        action === "approve"
          ? `Failure notices for ${editionDate} approved.`
          : `Failure notices for ${editionDate} suppressed.`,
      );
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "That failed.");
    } finally {
      setBusy(false);
    }
  }

  async function withdraw() {
    setBusy(true);
    setError(null);
    setDone(null);
    setConfirming(null);
    try {
      await adminPost(`/admin/api/stories/${storyId.trim()}/withdraw`, { reason });
      setDone("Story withdrawn. A new revision without it has been published.");
      setStoryId("");
      setReason("");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Withdrawal failed.");
    } finally {
      setBusy(false);
    }
  }

  async function correctStory(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      await adminPost(`/admin/api/stories/${correctionStoryId.trim()}/correct`, { description });
      setDone("Correction recorded.");
      setCorrectionStoryId("");
      setDescription("");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Recording the correction failed.");
    } finally {
      setBusy(false);
    }
  }

  async function saveStatus(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      const updated = await adminPost<SiteStatus>("/admin/api/status", {
        degraded: statusDegraded,
        message: statusDegraded && statusMessage.trim() ? statusMessage.trim() : null,
      });
      setSiteStatus(updated);
      setStatusMessage(updated.message ?? "");
      setDone(
        updated.degraded ? "Public status set to degraded." : "Public status set to operational.",
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Updating the status failed.");
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    await adminPost("/admin/api/logout").catch(() => undefined);
    window.location.reload();
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <PageTitle>Admin dashboard</PageTitle>
        <Button variant="secondary" onClick={signOut}>
          Sign out
        </Button>
      </div>

      {error && <Notice kind="error">{error}</Notice>}
      {done && <Notice kind="success">{done}</Notice>}

      <section className="mb-10">
        <h2 className="font-head mb-3 text-xl">Site status</h2>
        <p className="mb-3 text-sm text-ink-soft">
          What <code>/status</code> shows the public. No automated monitoring drives this yet — flip
          it manually during a real incident, and clear it once it&rsquo;s resolved.
        </p>
        {siteStatus && (
          <p className="mb-3 text-sm">
            Currently:{" "}
            {siteStatus.degraded ? (
              <span className="font-semibold text-danger">degraded</span>
            ) : (
              <span className="font-semibold text-success">operational</span>
            )}
            {siteStatus.updated_at &&
              ` (since ${new Date(siteStatus.updated_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST)`}
          </p>
        )}
        <form onSubmit={saveStatus} className="max-w-md">
          <label className="font-gothic mb-3 flex min-h-11 items-center gap-3 text-sm">
            <input
              className="stamp-check"
              type="checkbox"
              checked={statusDegraded}
              onChange={(e) => setStatusDegraded(e.target.checked)}
            />
            The site is currently degraded or down
          </label>
          {statusDegraded && (
            <Field htmlFor="status-message" label="Message shown to visitors">
              <input
                id="status-message"
                value={statusMessage}
                onChange={(e) => setStatusMessage(e.target.value)}
                className={textInputClasses("mt-1")}
              />
            </Field>
          )}
          <Button type="submit" disabled={busy}>
            Update status
          </Button>
        </form>
      </section>

      <section className="mb-10">
        <h2 className="font-head mb-3 text-xl">Recent job runs</h2>
        {runs.length === 0 ? (
          <p className="text-sm text-ink-soft">No runs recorded.</p>
        ) : (
          <Table
            headers={["Job", "Edition", "Status", "Started (IST)"]}
            rows={runs.map((run) => [
              run.job,
              run.edition_date ?? "—",
              run.status,
              new Date(run.started_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" }),
            ])}
          />
        )}
      </section>

      <section className="mb-10">
        <h2 className="font-head mb-3 text-xl">Deliveries stuck in sending</h2>
        {stuck.length === 0 ? (
          <p className="text-sm text-ink-soft">None flagged.</p>
        ) : (
          <Table
            headers={["Edition", "Type", "Attempts", "Claimed (IST)"]}
            rows={stuck.map((row) => [
              row.edition_date,
              row.type,
              String(row.attempts),
              row.claimed_at
                ? new Date(row.claimed_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })
                : "—",
            ])}
          />
        )}
      </section>

      <section className="mb-10">
        <h2 className="font-head mb-3 text-xl">Failure-notice batches</h2>
        {notices.length === 0 ? (
          <p className="text-sm text-ink-soft">None recorded.</p>
        ) : (
          <ul className="space-y-2">
            {notices.map((batch) => (
              <li
                key={batch.edition_date}
                className="flex flex-wrap items-center justify-between gap-2 border-2 border-ink bg-paper-raised px-3 py-2 text-sm"
              >
                <span>
                  {batch.edition_date} — {batch.status} ({batch.recipient_count} recipients)
                </span>
                {batch.status === "held" &&
                  (confirming?.kind === "notice" && confirming.date === batch.edition_date ? (
                    <span className="flex flex-wrap items-center gap-2">
                      <span>
                        {confirming.action === "approve"
                          ? `Send apology emails to ${batch.recipient_count} readers?`
                          : "Suppress these notices? They will not be sent."}
                      </span>
                      <Button
                        variant={confirming.action === "approve" ? "primary" : "danger"}
                        disabled={busy}
                        onClick={() => decide(batch.edition_date, confirming.action)}
                      >
                        Confirm
                      </Button>
                      <Button variant="secondary" onClick={() => setConfirming(null)}>
                        Cancel
                      </Button>
                    </span>
                  ) : (
                    <span className="flex gap-2">
                      <Button
                        disabled={busy}
                        onClick={() =>
                          setConfirming({
                            kind: "notice",
                            date: batch.edition_date,
                            action: "approve",
                          })
                        }
                      >
                        Approve
                      </Button>
                      <Button
                        variant="danger"
                        disabled={busy}
                        onClick={() =>
                          setConfirming({
                            kind: "notice",
                            date: batch.edition_date,
                            action: "suppress",
                          })
                        }
                      >
                        Suppress
                      </Button>
                    </span>
                  ))}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mb-10">
        <h2 className="font-head mb-3 text-xl">Withdraw a story</h2>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            setConfirming({ kind: "withdraw" });
          }}
          className="max-w-md"
        >
          <Field htmlFor="story-id" label="Story ID">
            <input
              id="story-id"
              required
              value={storyId}
              onChange={(e) => setStoryId(e.target.value)}
              className={textInputClasses("mt-1")}
            />
          </Field>
          <Field htmlFor="withdraw-reason" label="Reason">
            <input
              id="withdraw-reason"
              required
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className={textInputClasses("mt-1")}
            />
          </Field>
          {confirming?.kind === "withdraw" ? (
            <div className="border-2 border-dashed border-press-red p-3">
              <p className="mb-3 text-sm">
                Withdraw this story now? Readers not yet sent today&rsquo;s edition will get a
                revision without it. Readers who already have it are handled as a correction.
              </p>
              <div className="flex flex-wrap gap-3">
                <Button type="button" variant="danger" disabled={busy} onClick={withdraw}>
                  Confirm withdrawal
                </Button>
                <Button type="button" variant="secondary" onClick={() => setConfirming(null)}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <Button type="submit" variant="danger" disabled={busy}>
              Withdraw
            </Button>
          )}
        </form>
      </section>

      <section className="mb-10">
        <h2 className="font-head mb-3 text-xl">Recent withdrawals</h2>
        {withdrawals.length === 0 ? (
          <p className="text-sm text-ink-soft">None yet.</p>
        ) : (
          <Table
            headers={["Headline", "Genre", "Edition", "Reason"]}
            rows={withdrawals.map((row) => [row.headline, row.genre, row.edition_date, row.reason])}
          />
        )}
      </section>

      <section className="mb-10">
        <h2 className="font-head mb-3 text-xl">Correct a story</h2>
        <p className="mb-3 text-sm text-ink-soft">
          Shown alongside the story in the archive, and in the next edition for readers who received
          it — never edits the story itself.
        </p>
        <form onSubmit={correctStory} className="max-w-md">
          <Field htmlFor="correction-story-id" label="Story ID">
            <input
              id="correction-story-id"
              required
              value={correctionStoryId}
              onChange={(e) => setCorrectionStoryId(e.target.value)}
              className={textInputClasses("mt-1")}
            />
          </Field>
          <Field htmlFor="correction-description" label="What was wrong, and what's correct">
            <input
              id="correction-description"
              required
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className={textInputClasses("mt-1")}
            />
          </Field>
          <Button type="submit" disabled={busy}>
            Record correction
          </Button>
        </form>
      </section>

      <section>
        <h2 className="font-head mb-3 text-xl">Recent corrections</h2>
        {corrections.length === 0 ? (
          <p className="text-sm text-ink-soft">None yet.</p>
        ) : (
          <Table
            headers={["Headline", "Genre", "Edition", "Description", "Announced"]}
            rows={corrections.map((row) => [
              row.headline,
              row.genre,
              row.edition_date,
              row.description,
              row.announced_on ?? "not yet",
            ])}
          />
        )}
      </section>
    </div>
  );
}

function Table({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b-2 border-ink text-ink-soft">
            {headers.map((header) => (
              <th key={header} className="py-2 pr-4 font-semibold">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex} className="border-b border-dotted border-ink">
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} className="py-2 pr-4">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
