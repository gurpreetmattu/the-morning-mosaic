"""Pre-flight check: is this environment ready to run the app?

    uv run python -m app.preflight            # offline checks only
    uv run python -m app.preflight --live     # also touch DB, SMTP, IMAP, LLM, Turnstile
    uv run python -m app.preflight --prod     # hold the environment to production rules

Run it against the exact environment you are about to deploy (export the
production values, or point it at a file via the usual `.env`). It prints
PASS / WARN / FAIL per check and exits 1 on any FAIL.

Without `--prod`, rules that only matter in production are reported as WARN so
a dev machine can still run it. With `--prod` they are FAIL, and APP_ENV must
itself be `prod`.

Secret values are never printed. `--live` never sends mail, never writes to the
database, and only logs in to (never reads) the mailbox. Turnstile and the LLM
gateway are probed with requests that carry no personal data.
"""

from __future__ import annotations

import argparse
import contextlib
import imaplib
import os
import re
import smtplib
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path

import httpx
from pydantic import AnyHttpUrl, SecretStr, ValidationError

from app.clock import IST
from app.config.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
TIMEOUT = 15.0
# Gmail's daily recipient cap covers ALL mail (CLAUDE.md "Email and delivery").
GMAIL_SAFE_SUBSCRIBER_CAP = 400
PLACEHOLDER_HINTS = ("changeme", "change-me", "example", "placeholder", "your-", "xxx", "todo")


# Settings that exist only for local development; prod never needs them wired.
DEV_ONLY = frozenset({"PDF_CACHE_DIR"})


class Level(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True)
class Check:
    level: Level
    name: str
    detail: str = ""


class Report:
    def __init__(self, prod_mode: bool) -> None:
        self.prod_mode = prod_mode
        self.checks: list[Check] = []

    @property
    def strict(self) -> Level:
        """Severity of a rule that only matters in production."""
        return Level.FAIL if self.prod_mode else Level.WARN

    def add(self, level: Level, name: str, detail: str = "") -> None:
        self.checks.append(Check(level, name, detail))

    def ok(self, name: str, detail: str = "") -> None:
        self.add(Level.PASS, name, detail)

    def warn(self, name: str, detail: str) -> None:
        self.add(Level.WARN, name, detail)

    def fail(self, name: str, detail: str) -> None:
        self.add(Level.FAIL, name, detail)

    def prod_rule(self, passed: bool, name: str, detail: str) -> None:
        if passed:
            self.ok(name)
        else:
            self.add(self.strict, name, detail)

    @property
    def failed(self) -> bool:
        return any(check.level is Level.FAIL for check in self.checks)

    def render(self) -> str:
        lines = [
            f"[{c.level}] {c.name}" + (f" - {c.detail}" if c.detail else "") for c in self.checks
        ]
        counts = {level: sum(c.level is level for c in self.checks) for level in Level}
        lines.append("")
        lines.append(
            f"{counts[Level.PASS]} passed, {counts[Level.WARN]} warnings, "
            f"{counts[Level.FAIL]} failed"
        )
        return "\n".join(lines)


def _secret(value: SecretStr | None) -> str:
    return value.get_secret_value() if value is not None else ""


def _is_local_host(host: str | None) -> bool:
    return host in (None, "", "localhost", "127.0.0.1", "0.0.0.0", "::1") or host.endswith(".local")


def _looks_like_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(hint in lowered for hint in PLACEHOLDER_HINTS)


# --------------------------------------------------------------------------
# Offline checks
# --------------------------------------------------------------------------


def load_settings(report: Report, env: Mapping[str, str]) -> Settings | None:
    """Settings must validate. Lists the failing field names, never their values."""
    try:
        settings = Settings()  # type: ignore[call-arg]
    except ValidationError as error:
        for problem in error.errors():
            field = ".".join(str(part) for part in problem["loc"]) or "?"
            report.fail(f"setting {field.upper()}", f"{problem['type']}: {problem['msg']}")
        return None
    report.ok("settings load and validate")
    if report.prod_mode:
        report.prod_rule(
            settings.is_prod, "APP_ENV is prod", f"APP_ENV={settings.app_env!r}; set it to prod"
        )
    if env.get("EDITION_LAUNCH_DATE_OVERRIDE"):
        report.prod_rule(
            False,
            "EDITION_LAUNCH_DATE_OVERRIDE unset",
            "the app refuses to start in prod with this set; remove it",
        )
    return settings


def check_core(report: Report, settings: Settings) -> None:
    base = settings.base_url
    report.prod_rule(
        base.scheme == "https" and not _is_local_host(base.host),
        "BASE_URL is a public https origin",
        f"BASE_URL={base} - every link in every email is built from it",
    )
    report.prod_rule(
        not _is_local_host(settings.llm_gateway_url.host),
        "LLM_GATEWAY_URL is publicly reachable",
        f"host {settings.llm_gateway_url.host!r} is local; a deployed job cannot reach it",
    )
    key = _secret(settings.token_signing_key)
    report.prod_rule(
        len(key) >= 32 and not _looks_like_placeholder(key),
        "TOKEN_SIGNING_KEY is long and non-placeholder",
        "use at least 32 random characters; rotating it later breaks every unsubscribe link",
    )
    report.prod_rule(
        bool(_secret(settings.turnstile_secret_key)) and bool(settings.turnstile_site_key),
        "Turnstile site key and secret are set",
        "in prod, signup raises without a Turnstile secret",
    )
    report.prod_rule(
        bool(settings.gcp_project_id) and bool(settings.gcs_pdf_bucket),
        "GCP_PROJECT_ID and GCS_PDF_BUCKET are set",
        "PDFs cache to Cloud Storage in prod",
    )
    report.prod_rule(
        not _looks_like_placeholder(settings.sender_name) and settings.sender_name.strip() != "",
        "SENDER_NAME is set",
        "shown in every recipient's inbox",
    )


def check_database(report: Report, settings: Settings) -> None:
    url = _secret(settings.database_url)
    host = re.sub(r"^[^@]*@", "", url.split("//", 1)[-1]).split("/", 1)[0].split(":")[0]
    report.prod_rule(
        not _is_local_host(host), "DATABASE_URL is not a local database", f"host is {host!r}"
    )
    if "-pooler" in host:
        direct = _secret(settings.database_direct_url)
        report.prod_rule(
            bool(direct) and "-pooler" not in direct,
            "DATABASE_DIRECT_URL set for a pooled DATABASE_URL",
            "pooled Neon URL without a direct one: the job lock's advisory lock can land on "
            "the wrong backend (app/jobs/locking.py)",
        )
    if not _is_local_host(host):
        report.prod_rule(
            "sslmode=require" in url or "sslmode=verify" in url,
            "DATABASE_URL requires TLS",
            "add ?sslmode=require",
        )


def check_mail(report: Report, settings: Settings) -> None:
    sender_domain = str(settings.sender_email).rsplit("@", 1)[-1].lower()
    if sender_domain in ("gmail.com", "googlemail.com"):
        report.ok("sender is Gmail", "~500 recipients/day cap covers ALL mail")
        report.prod_rule(
            settings.max_active_subscribers <= GMAIL_SAFE_SUBSCRIBER_CAP,
            "MAX_ACTIVE_SUBSCRIBERS leaves room under Gmail's quota",
            f"{settings.max_active_subscribers} > {GMAIL_SAFE_SUBSCRIBER_CAP}; "
            "opt-in and magic-link mail share the same daily quota",
        )
    elif settings.smtp_host.endswith("gmail.com"):
        report.warn("SMTP_HOST is Gmail but SENDER_EMAIL is not", "Gmail will rewrite the From")
    if settings.is_prod and settings.test_email_allowlist.strip():
        report.warn(
            "TEST_EMAIL_ALLOWLIST is set in prod",
            "harmless (ignored in prod) but suggests a dev .env was copied over",
        )
    if not settings.is_prod:
        if settings.allowlisted_test_emails:
            report.ok(
                "dev sending is allowlisted", f"{len(settings.allowlisted_test_emails)} address(es)"
            )
        else:
            report.warn(
                "TEST_EMAIL_ALLOWLIST is empty",
                "outside prod nothing will be emailed; add your own address to test delivery",
            )


def check_llm(report: Report, settings: Settings) -> None:
    pairs = (
        ("LLM_FALLBACK", settings.llm_fallback_url, settings.llm_fallback_api_key),
        ("LLM_SECONDARY", settings.llm_secondary_url, settings.llm_secondary_api_key),
    )
    for prefix, url, key in pairs:
        if (url is None) != (key is None):
            report.fail(
                f"{prefix}_URL / {prefix}_API_KEY",
                "set one without the other; both or neither",
            )
        elif url is None:
            report.warn(
                f"{prefix} gateway not configured",
                "no failover for that route (see config/models.yaml); a quota day stops it",
            )
        else:
            report.ok(f"{prefix} gateway configured")


def check_providers(report: Report, settings: Settings) -> None:
    """Optional providers: missing ones degrade a feature rather than break the app."""
    optional = [
        ("OPENWEATHERMAP_API_KEY", settings.openweathermap_api_key, "weather box"),
        ("MARKET_API_KEY", settings.market_api_key, "market strip"),
        ("SPORTS_API_KEY", settings.sports_api_key, "sports scores/fixtures"),
        ("TMDB_API_KEY", settings.tmdb_api_key, "movie releases"),
        ("UNSPLASH_ACCESS_KEY", settings.unsplash_access_key, "Unsplash images"),
        ("PEXELS_API_KEY", settings.pexels_api_key, "Pexels images"),
    ]
    for name, value, feature in optional:
        if _secret(value):
            report.ok(f"{name} set")
        else:
            report.warn(f"{name} unset", f"{feature} will be omitted from every edition")
    if not any(
        _secret(k)
        for k in (settings.newsdata_api_key, settings.gnews_api_key, settings.newsapi_key)
    ):
        report.ok("no news API keys", "RSS-only collection (the primary path)")
    langfuse = (settings.langfuse_public_key, settings.langfuse_secret_key)
    if all(_secret(k) for k in langfuse):
        report.ok("Langfuse keys set")
    elif any(_secret(k) for k in langfuse):
        report.fail("LANGFUSE keys", "public and secret key must both be set or both be unset")
    else:
        report.warn("Langfuse unset", "no LLM tracing")


def check_launch_date(report: Report, today: date) -> None:
    from app.config.loader import load_editions

    editions = load_editions()
    launch = editions.launch_date
    days = (launch - today).days
    if report.prod_mode and days < 0:
        report.ok(
            "launch_date", f"{launch} ({-days} days ago); confirm it is the real go-live date"
        )
    elif days < 0:
        report.warn(
            "launch_date",
            f"{launch} is already past: edition numbers count from it; confirm it is the "
            "real go-live date and not a placeholder",
        )
    elif days == 0:
        report.warn("launch_date", f"{launch} is today; confirm it is the real go-live date")
    else:
        report.add(
            report.strict,
            "launch_date is in the future",
            f"{launch} is {days} day(s) away; builds before it fail by design",
        )


def check_config_files(report: Report) -> None:
    from app.config import loader

    loaders = (
        loader.load_genres,
        loader.load_sources,
        loader.load_models,
        loader.load_editions,
        loader.load_cities,
        loader.load_policy,
    )
    for load in loaders:
        label = load.__name__.removeprefix("load_") + ".yaml"
        try:
            load()
        except Exception as error:
            report.fail(f"config/{label}", f"{type(error).__name__}: {str(error)[:200]}")
        else:
            report.ok(f"config/{label} validates")
    sources = loader.load_sources().sources
    enabled = [s for s in sources if s.enabled]
    report.prod_rule(
        bool(enabled), "at least one source is enabled", "no source is enabled: nothing to collect"
    )
    covered = {genre for source in enabled for genre in source.genres}
    all_genres = set(loader.load_genres().active_keys)
    missing = sorted(all_genres - covered)
    if missing:
        report.add(
            report.strict,
            "every genre has an enabled source",
            f"no enabled source for: {', '.join(missing)}",
        )
    else:
        report.ok(f"every genre has an enabled source ({len(enabled)} enabled)")


def check_repo_wiring(report: Report) -> None:
    """Drift between Settings, .env.example, and Terraform. Skipped if the files are absent."""
    fields = {name.upper(): info for name, info in Settings.model_fields.items()}
    example = REPO_ROOT / ".env.example"
    if example.is_file():
        text = example.read_text(encoding="utf-8")
        listed = set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", text, flags=re.MULTILINE))
        missing = sorted(set(fields) - listed)
        if missing:
            report.warn(".env.example is missing settings", ", ".join(missing))
        else:
            report.ok(".env.example lists every setting")
    locals_tf = REPO_ROOT / "infra" / "locals.tf"
    if locals_tf.is_file():
        tf = locals_tf.read_text(encoding="utf-8")
        unwired = sorted(
            name for name in fields if name not in DEV_ONLY and not re.search(rf"\b{name}\b", tf)
        )
        # Not every setting needs wiring (defaults, dev-only, GCS-derived), so
        # this is a WARN to look at, not a verdict.
        if unwired:
            report.warn(
                "settings absent from infra/locals.tf",
                f"{', '.join(unwired)}; if one is needed in prod, the deployed service will "
                "silently run without it",
            )
        else:
            report.ok("infra/locals.tf passes every setting to Cloud Run")
    secrets_tf = REPO_ROOT / "infra" / "secrets.tf"
    if secrets_tf.is_file():
        ids = set(re.findall(r'"([a-z0-9-]+)"', secrets_tf.read_text(encoding="utf-8")))
        secret_fields = [
            name
            for name, info in Settings.model_fields.items()
            if "SecretStr" in str(info.annotation)
        ]
        no_container = sorted(
            name.upper() for name in secret_fields if name.replace("_", "-") not in ids
        )
        if no_container:
            report.warn(
                "SecretStr settings with no Secret Manager container",
                ", ".join(no_container),
            )
        else:
            report.ok("every secret setting has a Secret Manager container")


# --------------------------------------------------------------------------
# Live checks (--live): read-only
# --------------------------------------------------------------------------


def live_database(report: Report, settings: Settings) -> None:
    from sqlalchemy import create_engine, text

    from app.db.engine import normalise_url

    engine = create_engine(
        normalise_url(_secret(settings.database_url)),
        connect_args={"connect_timeout": int(TIMEOUT)},
    )
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
            report.ok("database reachable")
            current = None
            try:
                current = conn.execute(text("select version_num from alembic_version")).scalar()
            except Exception:
                conn.rollback()
            head = _alembic_head()
            if current is None:
                report.fail("database is migrated", "no alembic_version; run alembic upgrade head")
            elif head is not None and current != head:
                report.fail("database is at the latest migration", f"at {current}, head is {head}")
            else:
                report.ok("database is at the latest migration", str(current))
            for table, where, name in (
                ("cities", "true", "cities seeded"),
                ("sources", "enabled", "enabled sources seeded"),
            ):
                try:
                    count = conn.execute(
                        text(f"select count(*) from {table} where {where}")
                    ).scalar()
                except Exception as error:
                    conn.rollback()
                    report.fail(name, type(error).__name__)
                    continue
                if count:
                    report.ok(name, str(count))
                else:
                    report.fail(name, f"{table} is empty; run python -m app.jobs.seed")
    except Exception as error:
        report.fail("database reachable", type(error).__name__)
    finally:
        engine.dispose()


def _alembic_head() -> str | None:
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        migrations = REPO_ROOT / "backend" / "migrations"
        if not migrations.is_dir():
            return None
        config = Config()
        config.set_main_option("script_location", str(migrations))
        return ScriptDirectory.from_config(config).get_current_head()
    except Exception:
        return None


def live_smtp(report: Report, settings: Settings) -> None:
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=TIMEOUT) as smtp:
            smtp.starttls()
            smtp.login(str(settings.sender_email), _secret(settings.gmail_app_password))
        report.ok("SMTP login works", "nothing sent")
    except Exception as error:
        report.fail(
            "SMTP login", f"{type(error).__name__}: check the app password and 2-step verification"
        )


def live_imap(report: Report, settings: Settings) -> None:
    try:
        client = imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port, timeout=TIMEOUT)
        try:
            client.login(str(settings.sender_email), _secret(settings.gmail_app_password))
        finally:
            with contextlib.suppress(Exception):
                client.logout()
        report.ok("IMAP login works", "no mail read")
    except Exception as error:
        report.fail("IMAP login", f"{type(error).__name__}: is IMAP enabled on the account?")


def live_llm(report: Report, settings: Settings) -> None:
    gateways: list[tuple[str, AnyHttpUrl, SecretStr | None]] = [
        ("LLM_GATEWAY", settings.llm_gateway_url, settings.llm_gateway_api_key)
    ]
    if settings.llm_fallback_url:
        gateways.append(("LLM_FALLBACK", settings.llm_fallback_url, settings.llm_fallback_api_key))
    if settings.llm_secondary_url:
        gateways.append(
            ("LLM_SECONDARY", settings.llm_secondary_url, settings.llm_secondary_api_key)
        )
    for name, url, key in gateways:
        endpoint = str(url).rstrip("/") + "/models"
        try:
            response = httpx.get(
                endpoint, headers={"Authorization": f"Bearer {_secret(key)}"}, timeout=TIMEOUT
            )
        except httpx.HTTPError as error:
            report.fail(f"{name} reachable", type(error).__name__)
            continue
        if response.status_code in (401, 403):
            report.fail(f"{name} key accepted", f"HTTP {response.status_code}: key rejected")
        elif response.status_code >= 400:
            report.warn(
                f"{name} /models", f"HTTP {response.status_code}; some gateways don't expose it"
            )
        else:
            report.ok(f"{name} reachable and key accepted")


def live_turnstile(report: Report, settings: Settings) -> None:
    secret = _secret(settings.turnstile_secret_key)
    if not secret:
        report.warn("Turnstile secret", "not set; nothing to verify")
        return
    from app.api.security import TURNSTILE_VERIFY_URL

    try:
        response = httpx.post(
            TURNSTILE_VERIFY_URL,
            data={"secret": secret, "response": "preflight-not-a-real-token"},
            timeout=TIMEOUT,
        )
        codes = set(response.json().get("error-codes", []))
    except Exception as error:
        report.fail("Turnstile verify call", type(error).__name__)
        return
    if codes & {"invalid-input-secret", "missing-input-secret"}:
        report.fail("Turnstile secret accepted", "Cloudflare says the secret is invalid")
    else:
        report.ok(
            "Turnstile secret accepted",
            "a real widget token round trip is still untested (needs a browser)",
        )


# --------------------------------------------------------------------------


def run(*, live: bool, prod_mode: bool, env: Mapping[str, str] | None = None) -> Report:
    report = Report(prod_mode)
    env = os.environ if env is None else env
    settings = load_settings(report, env)
    check_config_files(report)
    if settings is not None:
        check_core(report, settings)
        check_database(report, settings)
        check_mail(report, settings)
        check_llm(report, settings)
        check_providers(report, settings)
        from app.clock import now_utc

        check_launch_date(report, now_utc().astimezone(IST).date())
    check_repo_wiring(report)
    if live and settings is not None:
        live_database(report, settings)
        live_smtp(report, settings)
        live_imap(report, settings)
        live_llm(report, settings)
        live_turnstile(report, settings)
    elif live:
        report.fail("live checks skipped", "settings did not load")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--live", action="store_true", help="also probe DB, SMTP, IMAP, LLM, Turnstile"
    )
    parser.add_argument("--prod", action="store_true", help="enforce production rules as FAIL")
    args = parser.parse_args(argv)
    report = run(live=args.live, prod_mode=args.prod)
    print(report.render())
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
