"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, apiGet, publicPost, readerPatch, readerPost } from "@/lib/api";
import type { MeResponse, PreferencesUpdate, SiteConfig, StatusMessage } from "@/lib/types";
import { GenreCard } from "@/components/editorial/GenreCard";
import { ChoiceGroup } from "@/components/flow/ChoiceGroup";
import { CityCombobox } from "@/components/flow/CityCombobox";
import { Button, Field, Lede, Notice, PageTitle, textInputClasses } from "@/components/ui";
import { GENRES } from "@/content/genres";

const MAX_KEYWORDS = 10;

const EDITION_OPTIONS = [
  { value: "india", label: "India-focused" },
  { value: "mixed", label: "Mixed" },
  { value: "global", label: "Global" },
];
const FREQUENCY_OPTIONS = [
  { value: "daily", label: "Every day" },
  { value: "weekdays", label: "Weekdays only" },
];

const STATUS_LABELS: Record<string, string> = {
  active: "Active",
  paused: "Paused",
  pending: "Waiting for your confirmation",
  waitlisted: "On the waitlist",
  unsubscribed: "Unsubscribed",
  bounced: "Emails to this address are bouncing",
};

function slotLabel(slot: string): string {
  return slot.slice(0, 5);
}

function parseKeywords(input: string): string[] {
  return input
    .split(",")
    .map((word) => word.trim())
    .filter(Boolean)
    .slice(0, MAX_KEYWORDS);
}

export default function PreferencesPage() {
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [config, setConfig] = useState<SiteConfig | null>(null);
  const [signedOutNote, setSignedOutNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      apiGet<MeResponse>("/api/me").catch((err) => {
        // Only a 401 means "not signed in"; anything else is a failure to load.
        if (err instanceof ApiError && err.status === 401) return null;
        throw err;
      }),
      apiGet<SiteConfig>("/api/config"),
    ])
      .then(([meResult, configResult]) => {
        if (cancelled) return;
        setMe(meResult);
        setConfig(configResult);
        setLoadError(false);
      })
      .catch(() => {
        if (!cancelled) setLoadError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  if (loading) {
    return (
      <p role="status" className="font-gothic text-ink-soft">
        Loading your subscription&hellip;
      </p>
    );
  }
  if (loadError) {
    return (
      <div>
        <PageTitle>Manage your subscription</PageTitle>
        <Notice kind="error">We couldn&rsquo;t load your subscription. Please try again.</Notice>
        <Button
          onClick={() => {
            setLoading(true);
            setAttempt((n) => n + 1);
          }}
        >
          Try again
        </Button>
      </div>
    );
  }
  if (!me) return <LoginRequest note={signedOutNote} />;
  return (
    <Dashboard
      me={me}
      config={config}
      onSignedOut={(note) => {
        setSignedOutNote(note);
        setMe(null);
      }}
    />
  );
}

function LoginRequest({ note }: { note?: string | null }) {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState<StatusMessage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      setSent(await publicPost<StatusMessage>("/api/login", { email }));
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
      <PageTitle>Manage your subscription</PageTitle>
      <Lede>Enter your email and we&rsquo;ll send you a sign-in link.</Lede>
      {note && <Notice kind="success">{note}</Notice>}
      {error && <Notice kind="error">{error}</Notice>}
      <form onSubmit={handleSubmit}>
        <Field htmlFor="login-email" label="Email">
          <input
            id="login-email"
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

function Dashboard({
  me: initialMe,
  config,
  onSignedOut,
}: {
  me: MeResponse;
  config: SiteConfig | null;
  onSignedOut: (note: string) => void;
}) {
  const [me, setMe] = useState(initialMe);
  const [keywordInput, setKeywordInput] = useState(initialMe.keywords.join(", "));
  const [status, setStatus] = useState<{ kind: "error" | "success"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const noticeRef = useRef<HTMLDivElement>(null);

  // The notice sits at the top while the buttons that cause it are at the bottom: on a phone the
  // result would otherwise appear off-screen.
  useEffect(() => {
    if (status) noticeRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [status]);

  async function save(update: PreferencesUpdate) {
    if (me.genres.length === 0) {
      setStatus({ kind: "error", text: "Choose at least one genre." });
      return;
    }
    if (!me.city_id) {
      setStatus({ kind: "error", text: "Pick a city from the list." });
      return;
    }
    const typedKeywords = keywordInput.split(",").filter((word) => word.trim()).length;
    setBusy(true);
    setStatus(null);
    try {
      const updated = await readerPatch<MeResponse>("/api/me", update);
      setMe(updated);
      setKeywordInput(updated.keywords.join(", "));
      setStatus({
        kind: "success",
        text:
          typedKeywords > MAX_KEYWORDS
            ? `Saved. Only the first ${MAX_KEYWORDS} keywords were kept.`
            : "Saved.",
      });
    } catch (err) {
      setStatus({ kind: "error", text: err instanceof ApiError ? err.message : "Save failed." });
    } finally {
      setBusy(false);
    }
  }

  async function togglePause() {
    setBusy(true);
    setStatus(null);
    try {
      const path = me.status === "paused" ? "/api/me/resume" : "/api/me/pause";
      const updated = await readerPost<MeResponse>(path);
      // Only the status changes: edits the reader hasn't saved yet stay on screen.
      setMe((current) => ({ ...current, status: updated.status }));
      setStatus({
        kind: "success",
        text: updated.status === "paused" ? "Delivery paused." : "Delivery resumed.",
      });
    } catch (err) {
      setStatus({ kind: "error", text: err instanceof ApiError ? err.message : "That failed." });
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    await readerPost("/api/logout").catch(() => undefined);
    onSignedOut("You've been signed out.");
  }

  async function deleteAccount() {
    setBusy(true);
    try {
      await readerPost("/api/me/delete");
      onSignedOut("Your account and personal data have been deleted.");
    } catch (err) {
      setStatus({ kind: "error", text: err instanceof ApiError ? err.message : "That failed." });
      setBusy(false);
    }
  }

  function toggleGenre(key: string) {
    const next = me.genres.includes(key) ? me.genres.filter((g) => g !== key) : [...me.genres, key];
    setMe({ ...me, genres: next });
  }

  return (
    <div>
      <PageTitle>Your subscription</PageTitle>
      <Lede>
        Signed in as {me.email} · {STATUS_LABELS[me.status] ?? me.status}
      </Lede>

      <div ref={noticeRef}>{status && <Notice kind={status.kind}>{status.text}</Notice>}</div>

      <fieldset className="mb-8">
        <legend className="kicker mb-3 text-ink">Genres</legend>
        <div className="grid grid-cols-2 gap-5 sm:grid-cols-3">
          {config?.genres.map((genre, i) => (
            <GenreCard
              key={genre.key}
              genre={genre.key}
              name={genre.display_name}
              blurb={genre.blurb || GENRES.find((g) => g.slug === genre.key)?.blurb || ""}
              numeral={i + 1}
              checked={me.genres.includes(genre.key)}
              onChange={() => toggleGenre(genre.key)}
            />
          ))}
        </div>
      </fieldset>

      {config && (
        <>
          <div className="mb-6">
            <label htmlFor="pref-city" className="kicker mb-1 block text-ink">
              City
            </label>
            <CityCombobox
              cities={config.cities}
              value={me.city_id ?? ""}
              onChange={(id) => setMe({ ...me, city_id: id })}
              inputId="pref-city"
            />
          </div>

          <ChoiceGroup
            legend="Delivery time (IST)"
            variant="stub"
            options={config.delivery_slots.map((s) => ({
              value: slotLabel(s),
              label: slotLabel(s),
            }))}
            value={slotLabel(me.delivery_slot)}
            onChange={(v) => setMe({ ...me, delivery_slot: `${v}:00` })}
          />
        </>
      )}

      <ChoiceGroup
        legend="Frequency"
        helper="Weekdays only skips the weekend editions too."
        options={FREQUENCY_OPTIONS}
        value={me.frequency}
        onChange={(v) => setMe({ ...me, frequency: v })}
      />

      <ChoiceGroup
        legend="Edition preference"
        options={EDITION_OPTIONS}
        value={me.edition_preference}
        onChange={(v) => setMe({ ...me, edition_preference: v })}
      />

      <Field
        htmlFor="pref-keywords"
        label={`Followed keywords (optional, comma-separated, up to ${MAX_KEYWORDS})`}
      >
        <input
          id="pref-keywords"
          value={keywordInput}
          onChange={(e) => setKeywordInput(e.target.value)}
          placeholder="cricket, isro"
          className={textInputClasses()}
        />
      </Field>

      <div className="mb-8 flex flex-wrap gap-3">
        <Button
          disabled={busy}
          onClick={() =>
            save({
              genres: me.genres,
              delivery_slot: slotLabel(me.delivery_slot),
              city_id: me.city_id,
              frequency: me.frequency,
              edition_preference: me.edition_preference,
              keywords: parseKeywords(keywordInput),
            })
          }
        >
          Save changes
        </Button>
        <Button variant="secondary" disabled={busy} onClick={togglePause}>
          {me.status === "paused" ? "Resume delivery" : "Pause delivery"}
        </Button>
        <Button variant="secondary" disabled={busy} onClick={signOut}>
          Sign out
        </Button>
      </div>

      <div className="border-t-4 border-double border-ink pt-6">
        <h2 className="font-head mb-2 text-xl">Your data</h2>
        <div className="flex flex-wrap items-center gap-3">
          <a href="/api/me/export" className="font-gothic text-sm underline">
            Download a copy of your data
          </a>
        </div>

        <div className="mt-4">
          {!confirmingDelete ? (
            <Button variant="danger" onClick={() => setConfirmingDelete(true)}>
              Delete my account
            </Button>
          ) : (
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-sm">This removes your personal data permanently.</span>
              <Button variant="danger" disabled={busy} onClick={deleteAccount}>
                Confirm delete
              </Button>
              <Button variant="secondary" onClick={() => setConfirmingDelete(false)}>
                Cancel
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
