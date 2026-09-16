// Mirrors the FastAPI response models this frontend actually reads.
// Keep field names identical to backend/app/api/routes/*.py so a schema
// change there is a compile error here, not a silent runtime mismatch.

export interface GenreOption {
  key: string;
  display_name: string;
  blurb: string;
}

export interface CityOption {
  id: string;
  name: string;
  state: string;
}

export interface SiteConfig {
  genres: GenreOption[];
  cities: CityOption[];
  delivery_slots: string[]; // "HH:MM:SS"
  frequencies: string[];
  edition_preferences: string[];
}

export interface SignupPayload {
  name: string;
  email: string;
  city_id: string;
  genres: string[];
  delivery_slot: string; // "HH:MM"
  frequency: string;
  edition_preference: string;
  keywords: string[];
  age_confirmed: boolean;
  turnstile_token?: string;
}

export interface StatusMessage {
  status: string;
  message: string;
}

export interface MeResponse {
  email: string;
  name: string;
  city_id: string | null;
  status: string;
  delivery_slot: string;
  frequency: string;
  edition_preference: string;
  language: string;
  genres: string[];
  keywords: string[];
}

export interface PreferencesUpdate {
  name?: string;
  city_id?: string | null;
  genres?: string[];
  delivery_slot?: string;
  frequency?: string;
  edition_preference?: string;
  keywords?: string[];
}

export interface ArchivedSection {
  genre: string;
  status: string;
  html: string;
  story_count: number;
}

export interface ArchivedEdition {
  edition_date: string;
  edition_number: number;
  special_edition_key: string | null;
  is_weekend: boolean;
  revision: number;
  sections: ArchivedSection[];
}

export interface EditionSummary {
  edition_date: string;
  edition_number: number;
  special_edition_key: string | null;
}

export interface ArchivePage {
  editions: EditionSummary[];
  has_more: boolean;
}

export interface RunSummary {
  id: string;
  job: string;
  edition_date: string | null;
  status: string;
  started_at: string;
  finished_at: string | null;
  deadline_at: string | null;
  detail: Record<string, unknown> | null;
}

export interface StuckDelivery {
  id: string;
  user_id: string | null;
  edition_date: string;
  type: string;
  attempts: number;
  claimed_at: string | null;
}

export interface NoticeBatchSummary {
  edition_date: string;
  status: string;
  recipient_count: number;
  expires_at: string;
  decided_at: string | null;
  decided_by: string | null;
}

export interface WithdrawResponse {
  story_id: string;
  genre: string;
  revision: number;
  remaining_stories: number;
}

export interface WithdrawalSummary {
  story_id: string;
  headline: string;
  genre: string;
  edition_date: string;
  reason: string;
  withdrawn_at: string;
}
