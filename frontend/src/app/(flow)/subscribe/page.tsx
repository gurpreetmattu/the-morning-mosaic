"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { GenreCard } from "@/components/editorial/GenreCard";
import { formatSlot } from "@/components/editorial/format";
import { TurnstileWidget } from "@/components/TurnstileWidget";
import { ChoiceGroup } from "@/components/flow/ChoiceGroup";
import { CityCombobox } from "@/components/flow/CityCombobox";
import { EditionSummary } from "@/components/flow/EditionSummary";
import { StepTicket } from "@/components/flow/StepTicket";
import { Button, Field, Notice, PageTitle, textInputClasses } from "@/components/ui";
import { GENRES } from "@/content/genres";
import { apiGet, ApiError, publicPost } from "@/lib/api";
import type { SignupPayload, SiteConfig, StatusMessage } from "@/lib/types";

const MAX_KEYWORDS = 10;
const DEFAULT_SLOT = "07:00";
const DRAFT_KEY = "mm-subscribe-draft";

const STEPS = [
  { name: "Genres", title: "What do you want to read?" },
  { name: "City", title: "Where should we check the weather?" },
  { name: "Time", title: "When should it arrive?" },
  { name: "You", title: "Where should we send it?" },
] as const;

const EDITION_OPTIONS = [
  { value: "india", label: "India-focused" },
  { value: "mixed", label: "Mixed" },
  { value: "global", label: "Global" },
];
const FREQUENCY_OPTIONS = [
  { value: "daily", label: "Every day" },
  { value: "weekdays", label: "Weekdays only" },
];

const slotLabel = (slot: string) => slot.slice(0, 5); // "07:00:00" -> "07:00"
const EMAIL_SHAPE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface Draft {
  genres: string[];
  cityId: string;
  slot: string;
  frequency: string;
  editionPreference: string;
  keywordInput: string;
}

// Only non-personal choices are kept across a refresh. Name and email never
// touch storage (CLAUDE.md: minimal personal data).
function readDraft(): Partial<Draft> {
  try {
    return JSON.parse(sessionStorage.getItem(DRAFT_KEY) ?? "{}") as Partial<Draft>;
  } catch {
    return {};
  }
}

export default function SubscribePage() {
  const [config, setConfig] = useState<SiteConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);

  const [step, setStep] = useState(1);
  const [genres, setGenres] = useState<string[]>([]);
  const [cityId, setCityId] = useState("");
  const [slot, setSlot] = useState(DEFAULT_SLOT);
  const [frequency, setFrequency] = useState("daily");
  const [editionPreference, setEditionPreference] = useState("mixed");
  const [keywordInput, setKeywordInput] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [ageConfirmed, setAgeConfirmed] = useState(false);
  const [consented, setConsented] = useState(false);
  const [turnstileToken, setTurnstileToken] = useState<string | undefined>(undefined);

  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<StatusMessage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cityInvalid, setCityInvalid] = useState(false);

  const headingRef = useRef<HTMLHeadingElement>(null);
  const stepChanged = useRef(false);

  useEffect(() => {
    apiGet<SiteConfig>("/api/config")
      .then((data) => {
        setConfig(data);
        const draft = readDraft();
        const known = new Set(data.genres.map((g) => g.key));
        const fromUrl = (new URLSearchParams(window.location.search).get("genres") ?? "")
          .split(",")
          .filter((g) => known.has(g));
        const chosen = fromUrl.length ? fromUrl : (draft.genres ?? []).filter((g) => known.has(g));
        setGenres(chosen);
        if (data.cities.some((c) => c.id === draft.cityId)) setCityId(draft.cityId ?? "");
        const slots = data.delivery_slots.map(slotLabel);
        setSlot(
          draft.slot && slots.includes(draft.slot)
            ? draft.slot
            : slots.includes(DEFAULT_SLOT)
              ? DEFAULT_SLOT
              : (slots[0] ?? DEFAULT_SLOT),
        );
        if (draft.frequency) setFrequency(draft.frequency);
        if (draft.editionPreference) setEditionPreference(draft.editionPreference);
        if (draft.keywordInput) setKeywordInput(draft.keywordInput);
      })
      .catch(() => setConfigError("We couldn't load the signup form. Please try again shortly."));
  }, []);

  useEffect(() => {
    if (!config) return;
    try {
      const draft: Draft = { genres, cityId, slot, frequency, editionPreference, keywordInput };
      sessionStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
    } catch {
      // Storage unavailable: the flow still works, it just won't survive a refresh.
    }
  }, [config, genres, cityId, slot, frequency, editionPreference, keywordInput]);

  // Route-style focus management: land on the new step's heading.
  useEffect(() => {
    if (stepChanged.current) headingRef.current?.focus();
    stepChanged.current = true;
  }, [step]);

  const keywords = useMemo(
    () =>
      keywordInput
        .split(",")
        .map((word) => word.trim())
        .filter(Boolean)
        .slice(0, MAX_KEYWORDS),
    [keywordInput],
  );

  const genreNames = useMemo(() => {
    const names = new Map(config?.genres.map((g) => [g.key, g.display_name]) ?? []);
    return genres.map((key) => ({ key, name: names.get(key) ?? key }));
  }, [config, genres]);
  const cityName = config?.cities.find((c) => c.id === cityId)?.name ?? null;

  function toggleGenre(key: string, on: boolean) {
    setGenres((cur) => (on ? [...cur, key] : cur.filter((g) => g !== key)));
  }

  /** Returns an error message for the step, or null when it can be left. */
  function validate(forStep: number): string | null {
    if (forStep === 1 && genres.length === 0) return "Choose at least one genre.";
    if (forStep === 2 && !cityId) {
      setCityInvalid(true);
      return "Pick a city from the list. Can't find yours? Choose the nearest one.";
    }
    if (forStep === 4) {
      if (!name.trim()) return "Tell us your name, so the paper can say who it's for.";
      if (!EMAIL_SHAPE.test(email.trim()))
        return "That email doesn't look right. Check for typos, like a missing @ or domain.";
      if (!ageConfirmed) return "This service is for readers aged 18 and over.";
      if (!consented) return "Please tick the box to agree to receive The Morning Mosaic by email.";
    }
    return null;
  }

  function go(to: number) {
    setError(null);
    setStep(to);
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const problem = validate(step);
    if (problem) {
      setError(problem);
      return;
    }
    setError(null);
    setCityInvalid(false);
    if (step < STEPS.length) {
      setStep(step + 1);
      return;
    }

    const payload: SignupPayload = {
      name: name.trim(),
      email: email.trim(),
      city_id: cityId,
      genres,
      delivery_slot: slot,
      frequency,
      edition_preference: editionPreference,
      keywords,
      age_confirmed: ageConfirmed,
      turnstile_token: turnstileToken,
    };

    setSubmitting(true);
    try {
      setResult(await publicPost<StatusMessage>("/api/signup", payload));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (configError) {
    return (
      <div>
        <PageTitle>Start my edition</PageTitle>
        <Notice kind="error">{configError}</Notice>
      </div>
    );
  }

  if (result) {
    const waitlisted = result.status === "waitlisted";
    return (
      <div className="mx-auto max-w-xl text-center">
        <svg aria-hidden viewBox="0 0 96 64" className="mx-auto mb-4 h-16 w-24 text-ink">
          <rect
            x="2"
            y="2"
            width="92"
            height="60"
            fill="var(--paper-raised)"
            stroke="currentColor"
            strokeWidth="3"
          />
          <path d="M2 2 L48 38 L94 2" fill="none" stroke="currentColor" strokeWidth="3" />
        </svg>
        <PageTitle>{waitlisted ? "You're on the waitlist" : "Check your inbox"}</PageTitle>
        <div className="mt-4 text-start">
          <Notice kind="success">{result.message}</Notice>
        </div>
        {!waitlisted && (
          <ol className="font-gothic mx-auto max-w-sm space-y-1 text-start text-ink-soft">
            <li>1. Open the email we just sent to {email}.</li>
            <li>2. Tap the confirm button inside it.</li>
            <li>3. Your first edition arrives after you confirm.</li>
          </ol>
        )}
        <p className="mt-6">
          <Link href="/" className="underline">
            Back to the front page
          </Link>
        </p>
      </div>
    );
  }

  const stepMeta = STEPS[step - 1];
  const frequencyLabel = FREQUENCY_OPTIONS.find((o) => o.value === frequency)?.label ?? frequency;

  return (
    <div className="grid gap-10 lg:grid-cols-[minmax(0,640px)_1fr]">
      <form onSubmit={handleSubmit} noValidate aria-label="Subscribe">
        <h1 className="font-mast mb-4 text-[length:var(--fs-h2)] leading-tight font-normal">
          Start my edition
        </h1>
        <ol className="font-gothic mb-4 flex flex-wrap gap-2 text-sm">
          {STEPS.map((s, i) => {
            const n = i + 1;
            const done = n < step;
            return (
              <li key={s.name}>
                <button
                  type="button"
                  disabled={!done}
                  aria-current={n === step ? "step" : undefined}
                  onClick={() => go(n)}
                  className={`min-h-11 border-2 px-3 ${
                    n === step
                      ? "border-ink bg-ink text-paper"
                      : done
                        ? "border-ink bg-paper-raised underline"
                        : "border-dashed border-rule-soft text-ink-muted"
                  }`}
                >
                  {n}. {s.name}
                </button>
              </li>
            );
          })}
        </ol>

        <StepTicket
          step={step}
          total={STEPS.length}
          name={stepMeta.name}
          title={stepMeta.title}
          headingRef={headingRef}
        />

        {error && <Notice kind="error">{error}</Notice>}

        {step === 1 && (
          <div>
            <p className="font-gothic mb-4 text-ink-soft">
              Pick at least one. Each genre brings 4&ndash;6 stories.
            </p>
            <fieldset>
              <legend className="sr-only">Genres</legend>
              <div className="grid grid-cols-2 gap-5 sm:grid-cols-3">
                {config?.genres.map((genre, i) => (
                  <GenreCard
                    key={genre.key}
                    genre={genre.key}
                    name={genre.display_name}
                    blurb={genre.blurb || GENRES.find((g) => g.slug === genre.key)?.blurb || ""}
                    numeral={i + 1}
                    checked={genres.includes(genre.key)}
                    onChange={(on) => toggleGenre(genre.key, on)}
                  />
                ))}
              </div>
            </fieldset>
            <p aria-live="polite" className="font-gothic mt-4 text-sm">
              {genres.length === 0
                ? "No genres chosen yet."
                : `${genres.length} genre${genres.length === 1 ? "" : "s"} chosen.`}
            </p>

            <div className="mt-8 border-t-2 border-dotted border-ink pt-6">
              <p className="kicker mb-4 text-ink-soft">Make it yours (optional)</p>
              <ChoiceGroup
                legend="Edition preference"
                helper="How strongly should India-relevant stories rank?"
                options={EDITION_OPTIONS}
                value={editionPreference}
                onChange={setEditionPreference}
              />
              <Field
                htmlFor="keywords"
                label={`Followed keywords (comma-separated, up to ${MAX_KEYWORDS})`}
              >
                <input
                  id="keywords"
                  value={keywordInput}
                  onChange={(e) => setKeywordInput(e.target.value)}
                  placeholder="cricket, isro"
                  className={textInputClasses()}
                />
              </Field>
            </div>
          </div>
        )}

        {step === 2 && config && (
          <div>
            <p id="city-help" className="font-gothic mb-2 text-ink-soft">
              Weather for your city appears in your edition.
            </p>
            <label htmlFor="city-search" className="kicker mb-1 block">
              City
            </label>
            <CityCombobox
              cities={config.cities}
              value={cityId}
              onChange={(id) => {
                setCityId(id);
                if (id) setCityInvalid(false);
              }}
              inputId="city-search"
              invalid={cityInvalid}
              describedBy="city-help"
            />
          </div>
        )}

        {step === 3 && config && (
          <div>
            <p className="font-gothic mb-2 text-ink-soft">
              Choose any time from 6:00 to 9:00 AM IST.
            </p>
            <p className="font-figures mb-4 text-4xl font-bold" aria-live="polite">
              <span className="sr-only">Arrives around </span>
              {formatSlot(slot)}
            </p>
            <ChoiceGroup
              legend="Delivery time"
              variant="stub"
              options={config.delivery_slots.map((s) => ({
                value: slotLabel(s),
                label: slotLabel(s),
              }))}
              value={slot}
              onChange={setSlot}
            />
            <ChoiceGroup
              legend="How often"
              helper="Weekdays only skips the weekend editions too."
              options={FREQUENCY_OPTIONS}
              value={frequency}
              onChange={setFrequency}
            />
          </div>
        )}

        {step === 4 && (
          <div>
            <div className="mb-4">
              <label htmlFor="name" className="kicker mb-1 block text-ink">
                Name
              </label>
              <input
                id="name"
                autoComplete="given-name"
                aria-describedby="name-help"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className={textInputClasses()}
              />
              <p id="name-help" className="font-gothic mt-1 text-sm text-ink-soft">
                Your first name appears in the masthead: &ldquo;Curated for &hellip;&rdquo;.
              </p>
            </div>
            <Field htmlFor="email" label="Email">
              <input
                id="email"
                type="email"
                inputMode="email"
                autoComplete="email"
                autoCapitalize="none"
                spellCheck={false}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={textInputClasses()}
              />
            </Field>

            <label className="font-gothic mb-3 flex min-h-11 items-start gap-3">
              <input
                type="checkbox"
                checked={ageConfirmed}
                onChange={(e) => setAgeConfirmed(e.target.checked)}
                className="stamp-check mt-1"
              />
              <span>I confirm I am 18 years of age or older.</span>
            </label>
            <label className="font-gothic mb-4 flex min-h-11 items-start gap-3">
              <input
                type="checkbox"
                checked={consented}
                onChange={(e) => setConsented(e.target.checked)}
                className="stamp-check mt-1"
              />
              <span>
                Email me The Morning Mosaic every morning at my chosen time. I can change or stop
                this any time. See the{" "}
                <Link href="/privacy" className="underline">
                  privacy notice
                </Link>
                .
              </span>
            </label>

            <TurnstileWidget onToken={setTurnstileToken} />
          </div>
        )}

        <div className="sticky bottom-0 z-10 mt-8 flex gap-3 border-t-4 border-ink bg-paper p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] lg:static lg:border-0 lg:bg-transparent lg:p-0">
          {step > 1 && (
            <Button type="button" variant="secondary" onClick={() => go(step - 1)}>
              Back
            </Button>
          )}
          <Button type="submit" disabled={submitting || !config} aria-busy={submitting}>
            {step < STEPS.length ? "Next" : submitting ? "Subscribing…" : "Confirm and subscribe"}
          </Button>
        </div>
      </form>

      <div className="lg:sticky lg:top-6 lg:self-start">
        <EditionSummary
          genres={genreNames}
          cityName={cityName}
          timeLabel={formatSlot(slot)}
          frequencyLabel={frequencyLabel}
        />
      </div>
    </div>
  );
}
