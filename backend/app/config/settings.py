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
    freellmpool_url: AnyHttpUrl
    freellmpool_api_key: SecretStr
    llm_fallback_url: AnyHttpUrl | None = None
    llm_fallback_api_key: SecretStr | None = None

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
