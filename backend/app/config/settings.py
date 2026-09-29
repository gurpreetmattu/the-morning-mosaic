"""Environment-driven settings.

Nothing here carries a production value as a default: URLs, sender details, and
credentials must come from the environment (or Secret Manager in prod).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, EmailStr, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- core ---
    app_env: Literal["dev", "prod"] = "dev"
    base_url: AnyHttpUrl
    timezone: str = "Asia/Kolkata"
    log_level: str = "INFO"

    # --- database ---
    database_url: SecretStr
    # Optional. Neon's pooled endpoint ("-pooler" in the hostname) is
    # PgBouncer in transaction mode, which can silently hand the next
    # transaction on the same client connection to a *different* physical
    # backend — fatal for a session-scoped pg_advisory_lock, which the job
    # guard depends on (see app/jobs/locking.py). Set this to Neon's direct
    # endpoint (same string, "-pooler" removed from the hostname) in any
    # environment that uses the pooled URL for DATABASE_URL. Falls back to
    # database_url when unset, which is correct for a single non-pooled
    # Postgres in local dev.
    database_direct_url: SecretStr | None = None

    # --- outbound mail ---
    smtp_host: str
    smtp_port: int = 587
    sender_email: EmailStr
    sender_name: str
    gmail_app_password: SecretStr

    # --- bounce processing (read-only use of the same mailbox) ---
    imap_host: str
    imap_port: int = 993

    # --- delivery safety rails ---
    admin_email: EmailStr
    test_email_allowlist: str = ""
    max_active_subscribers: int = Field(default=400, gt=0)
    failure_notice_auto_limit: int = Field(default=50, gt=0)

    # --- LLM access ---
    llm_gateway_url: AnyHttpUrl
    llm_gateway_api_key: SecretStr
    llm_fallback_url: AnyHttpUrl | None = None
    llm_fallback_api_key: SecretStr | None = None
    # A second, distinct alternate gateway (currently Cloudflare Workers AI,
    # for Fact-checker) — kept separate from llm_fallback_* so a pinned agent
    # can sit on a genuinely different vendor from another pinned agent's
    # gateway (see ModelSpec.gateway in config/schemas.py).
    llm_secondary_url: AnyHttpUrl | None = None
    llm_secondary_api_key: SecretStr | None = None

    # --- tokens and anti-abuse ---
    token_signing_key: SecretStr
    turnstile_site_key: str | None = None
    turnstile_secret_key: SecretStr | None = None

    # --- news providers ---
    newsdata_api_key: SecretStr | None = None
    gnews_api_key: SecretStr | None = None
    newsapi_key: SecretStr | None = None

    # --- extras providers ---
    openweathermap_api_key: SecretStr | None = None
    market_api_key: SecretStr | None = None
    sports_api_key: SecretStr | None = None
    tmdb_api_key: SecretStr | None = None

    # --- images ---
    unsplash_access_key: SecretStr | None = None
    pexels_api_key: SecretStr | None = None

    # --- observability ---
    langfuse_public_key: SecretStr | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_host: AnyHttpUrl | None = None

    # --- GCP ---
    gcp_project_id: str | None = None
    gcp_region: str = "asia-south1"
    gcs_pdf_bucket: str | None = None

    # --- PDF caching outside prod, where there is no bucket ---
    pdf_cache_dir: str = ".cache/pdf"

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"

    @property
    def allowlisted_test_emails(self) -> frozenset[str]:
        """Addresses dev is permitted to email. Empty outside dev."""
        if self.is_prod:
            return frozenset()
        raw = (entry.strip().lower() for entry in self.test_email_allowlist.split(","))
        return frozenset(entry for entry in raw if entry)

    def may_send_to(self, email: str) -> bool:
        """Outside prod, sending is restricted to the test allowlist."""
        if self.is_prod:
            return True
        return email.strip().lower() in self.allowlisted_test_emails


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


class SeedSettings(BaseSettings):
    """The seed job (`app/jobs/seed.py`) only ever reads and writes
    reference tables from `/config` — it never sends mail, calls an LLM, or
    does anything else the full `Settings` requires a value for. Requiring
    all eleven of those anyway was real, reported friction in dev (see
    docs/BACKLOG.md) for no reason tied to what the job actually does.
    A separate, narrower model — not `Settings` with more fields made
    optional — keeps every other consumer's guarantee that a `Settings`
    instance means a fully configured app intact."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: SecretStr


@lru_cache(maxsize=1)
def get_seed_settings() -> SeedSettings:
    return SeedSettings()  # type: ignore[call-arg]
