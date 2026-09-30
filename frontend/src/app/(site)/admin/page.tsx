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

  useEffect(() => {
    apiGet<{ email: string }>("/admin/api/me")
      .then(() => setSignedIn(true))
      .catch(() => setSignedIn(false))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return null;
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
    try {
      await adminPost(`/admin/api/notices/${editionDate}/${action}`);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "That failed.");
    } finally {
      setBusy(false);
    }
  }

  async function withdraw(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await adminPost(`/admin/api/stories/${storyId}/withdraw`, { reason });
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
    try {
      await adminPost(`/admin/api/stories/${correctionStoryId}/correct`, { description });
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
    try {
      const updated = await adminPost<SiteStatus>("/admin/api/status", {
        degraded: statusDegraded,
        message: statusDegraded && statusMessage.trim() ? statusMessage.trim() : null,
      });
      setSiteStatus(updated);
      setStatusMessage(updated.message ?? "");
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

      <section className="mb-10">
        <h2 className="mb-3 text-lg font-semibold">Site status</h2>
        <p className="mb-3 text-sm text-muted">
          What <code>/status</code> shows the public. No automated monitoring drives this yet —
          flip it manually during a real incident, and clear it once it&rsquo;s resolved.
        </p>
        {siteStatus && (
          <p className="mb-3 text-sm">
            Currently:{" "}
            {siteStatus.degraded ? (
              <span className="font-semibold text-red-700">degraded</span>
            ) : (
              <span className="font-semibold text-green-700">operational</span>
            )}
            {siteStatus.updated_at &&
              ` (since ${new Date(siteStatus.updated_at).toLocaleString()})`}
          </p>
        )}
        <form onSubmit={saveStatus} className="max-w-md">
          <label className="mb-3 flex items-center gap-2 text-sm">
            <input
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
        <h2 className="mb-3 text-lg font-semibold">Recent job runs</h2>
        {runs.length === 0 ? (
          <p className="text-sm text-muted">No runs recorded.</p>
        ) : (
          <Table
            headers={["Job", "Edition", "Status", "Started"]}
            rows={runs.map((run) => [
              run.job,
              run.edition_date ?? "—",
              run.status,
              new Date(run.started_at).toLocaleString(),
            ])}
          />
        )}
      </section>

      <section className="mb-10">
        <h2 className="mb-3 text-lg font-semibold">Deliveries stuck in sending</h2>
        {stuck.length === 0 ? (
          <p className="text-sm text-muted">None flagged.</p>
        ) : (
          <Table
            headers={["Edition", "Type", "Attempts", "Claimed"]}
            rows={stuck.map((row) => [
              row.edition_date,
              row.type,
              String(row.attempts),
              row.claimed_at ? new Date(row.claimed_at).toLocaleString() : "—",
            ])}
          />
        )}
      </section>

      <section className="mb-10">
        <h2 className="mb-3 text-lg font-semibold">Failure-notice batches</h2>
        {notices.length === 0 ? (
          <p className="text-sm text-muted">None recorded.</p>
        ) : (
          <ul className="space-y-2">
            {notices.map((batch) => (
              <li
                key={batch.edition_date}
                className="flex flex-wrap items-center justify-between gap-2 rounded border border-rule px-3 py-2 text-sm"
              >
                <span>
                  {batch.edition_date} — {batch.status} ({batch.recipient_count} recipients)
                </span>
                {batch.status === "held" && (
                  <span className="flex gap-2">
                    <Button disabled={busy} onClick={() => decide(batch.edition_date, "approve")}>
                      Approve
                    </Button>
                    <Button
                      variant="danger"
                      disabled={busy}
                      onClick={() => decide(batch.edition_date, "suppress")}
                    >
                      Suppress
                    </Button>
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mb-10">
        <h2 className="mb-3 text-lg font-semibold">Withdraw a story</h2>
        <form onSubmit={withdraw} className="max-w-md">
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
          <Button type="submit" variant="danger" disabled={busy}>
            Withdraw
          </Button>
        </form>
      </section>

      <section className="mb-10">
        <h2 className="mb-3 text-lg font-semibold">Recent withdrawals</h2>
        {withdrawals.length === 0 ? (
          <p className="text-sm text-muted">None yet.</p>
        ) : (
          <Table
            headers={["Headline", "Genre", "Edition", "Reason"]}
            rows={withdrawals.map((row) => [row.headline, row.genre, row.edition_date, row.reason])}
          />
        )}
      </section>

      <section className="mb-10">
        <h2 className="mb-3 text-lg font-semibold">Correct a story</h2>
        <p className="mb-3 text-sm text-muted">
          Shown alongside the story in the archive, and in the next edition for readers who
          received it — never edits the story itself.
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
        <h2 className="mb-3 text-lg font-semibold">Recent corrections</h2>
        {corrections.length === 0 ? (
          <p className="text-sm text-muted">None yet.</p>
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
          <tr className="border-b border-rule text-muted">
            {headers.map((header) => (
              <th key={header} className="py-2 pr-4 font-semibold">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.join("|")} className="border-b border-rule/50">
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
