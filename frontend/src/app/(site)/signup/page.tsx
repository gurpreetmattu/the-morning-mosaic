"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGet, ApiError, publicPost } from "@/lib/api";
import type { SiteConfig, SignupPayload, StatusMessage } from "@/lib/types";
import { Button, Field, Lede, Notice, PageTitle, textInputClasses } from "@/components/ui";
import { TurnstileWidget } from "@/components/TurnstileWidget";

const MAX_KEYWORDS = 10;

function slotLabel(slot: string): string {
  return slot.slice(0, 5); // "07:00:00" -> "07:00"
}

export default function SignupPage() {
  const [config, setConfig] = useState<SiteConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [cityId, setCityId] = useState("");
  const [genres, setGenres] = useState<string[]>([]);
  const [deliverySlot, setDeliverySlot] = useState("");
  const [frequency, setFrequency] = useState("daily");
  const [editionPreference, setEditionPreference] = useState("mixed");
  const [keywordInput, setKeywordInput] = useState("");
  const [ageConfirmed, setAgeConfirmed] = useState(false);
  const [turnstileToken, setTurnstileToken] = useState<string | undefined>(undefined);

  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<StatusMessage | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<SiteConfig>("/api/config")
      .then((data) => {
        setConfig(data);
        setCityId(data.cities[0]?.id ?? "");
        setDeliverySlot(data.delivery_slots[2] ?? data.delivery_slots[0] ?? "");
      })
      .catch(() => setConfigError("We couldn't load the signup form. Please try again shortly."));
  }, []);

  const keywords = useMemo(
    () =>
      keywordInput
        .split(",")
        .map((word) => word.trim())
        .filter(Boolean)
        .slice(0, MAX_KEYWORDS),
    [keywordInput],
  );

  function toggleGenre(key: string) {
    setGenres((current) =>
      current.includes(key) ? current.filter((g) => g !== key) : [...current, key],
    );
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setResult(null);

    if (genres.length === 0) {
      setError("Choose at least one genre.");
      return;
    }
    if (!ageConfirmed) {
      setError("This service is for readers aged 18 and over.");
      return;
    }

    const payload: SignupPayload = {
      name,
      email,
      city_id: cityId,
      genres,
      delivery_slot: slotLabel(deliverySlot),
      frequency,
      edition_preference: editionPreference,
      keywords,
      age_confirmed: ageConfirmed,
      turnstile_token: turnstileToken,
    };

    setSubmitting(true);
    try {
      const response = await publicPost<StatusMessage>("/api/signup", payload);
      setResult(response);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (configError) {
    return <Notice kind="error">{configError}</Notice>;
  }

  if (result) {
    return (
      <div>
        <PageTitle>
          {result.status === "waitlisted" ? "You're on the waitlist" : "Check your email"}
        </PageTitle>
        <Notice kind="success">{result.message}</Notice>
      </div>
    );
  }

  return (
    <div>
      <PageTitle>Sign up</PageTitle>
      <Lede>Choose your genres, your city, and when you&rsquo;d like it to arrive.</Lede>

      {error && <Notice kind="error">{error}</Notice>}

      <form onSubmit={handleSubmit}>
        <Field htmlFor="name" label="Name">
          <input
            id="name"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={textInputClasses("mt-1")}
          />
        </Field>

        <Field htmlFor="email" label="Email">
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={textInputClasses("mt-1")}
          />
        </Field>

        <Field htmlFor="city" label="City">
          <select
            id="city"
            required
            value={cityId}
            onChange={(e) => setCityId(e.target.value)}
            className={textInputClasses("mt-1")}
          >
            {config?.cities.map((city) => (
              <option key={city.id} value={city.id}>
                {city.name}, {city.state}
              </option>
            ))}
          </select>
        </Field>

        <fieldset className="mb-4">
          <legend className="mb-2 text-sm font-semibold">Genres</legend>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {config?.genres.map((genre) => (
              <label key={genre.key} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={genres.includes(genre.key)}
                  onChange={() => toggleGenre(genre.key)}
                />
                {genre.display_name}
              </label>
            ))}
          </div>
        </fieldset>

        <Field htmlFor="slot" label="Delivery time (IST)">
          <select
            id="slot"
            value={deliverySlot}
            onChange={(e) => setDeliverySlot(e.target.value)}
            className={textInputClasses("mt-1")}
          >
            {config?.delivery_slots.map((slot) => (
              <option key={slot} value={slot}>
                {slotLabel(slot)}
              </option>
            ))}
          </select>
        </Field>

        <Field htmlFor="frequency" label="Frequency">
          <select
            id="frequency"
            value={frequency}
            onChange={(e) => setFrequency(e.target.value)}
            className={textInputClasses("mt-1")}
          >
            <option value="daily">Every day</option>
            <option value="weekdays">Weekdays only</option>
          </select>
        </Field>

        <Field htmlFor="edition-preference" label="Edition preference">
          <select
            id="edition-preference"
            value={editionPreference}
            onChange={(e) => setEditionPreference(e.target.value)}
            className={textInputClasses("mt-1")}
          >
            <option value="india">India-focused</option>
            <option value="mixed">Mixed</option>
            <option value="global">Global</option>
          </select>
        </Field>

        <Field
          htmlFor="keywords"
          label={`Followed keywords (optional, comma-separated, up to ${MAX_KEYWORDS})`}
        >
          <input
            id="keywords"
            value={keywordInput}
            onChange={(e) => setKeywordInput(e.target.value)}
            placeholder="cricket, isro"
            className={textInputClasses("mt-1")}
          />
        </Field>

        <label className="mb-4 flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            checked={ageConfirmed}
            onChange={(e) => setAgeConfirmed(e.target.checked)}
            className="mt-1"
          />
          I confirm I am 18 years of age or older.
        </label>

        <TurnstileWidget onToken={setTurnstileToken} />

        <Button type="submit" disabled={submitting || !config}>
          {submitting ? "Signing up…" : "Sign up"}
        </Button>
      </form>
    </div>
  );
}
