# One image, seven workloads: the api Cloud Run service and the six Cloud
# Run jobs (feedback, build, late_update, delivery, failure_notice,
# bounces). They share the same code and dependencies; only the command
# Cloud Run runs differs, set per resource in Terraform (infra/cloud_run_*.tf)
# rather than baked into the image.
#
# System libraries beyond Python: WeasyPrint needs Pango/Cairo to render
# PDFs, which is unavailable on the maintainer's Windows dev machine (see
# docs/BACKLOG.md) — this is the one place it can actually run.

FROM python:3.12-slim AS base

# GTK/Pango/Cairo for WeasyPrint, plus the DejaVu fonts so PDF pages render
# with something other than tofu boxes. libpq5 is psycopg's runtime dependency
# (psycopg[binary] ships its own libpq, but the OS still needs the loader libs
# it links against).
RUN apt-get update && apt-get install --no-install-recommends -y \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi8 \
    shared-mime-info \
    fonts-dejavu-core \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

FROM base AS builder

RUN apt-get update && apt-get install --no-install-recommends -y curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never

# Dependencies first, so an app-code change doesn't invalidate this layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev --no-editable

COPY backend/app ./backend/app
COPY evals ./evals
RUN uv sync --frozen --no-dev --no-editable

FROM base AS runtime

RUN groupadd --system app && useradd --system --gid app --home-dir /app app
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/backend/app ./backend/app
COPY config ./config
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
# app/config/loader.py finds /config by walking up from its own file's
# location, which only lands on the repo root in an editable dev checkout —
# here the package is installed into site-packages, so it must be told.
ENV CONFIG_DIR=/app/config
# /app is owned by root; fontconfig (via WeasyPrint) wants a writable cache
# directory for the non-root runtime user, and /tmp is the one place Cloud
# Run always gives a writable filesystem.
ENV HOME=/tmp XDG_CACHE_HOME=/tmp/.cache

USER app

# No EXPOSE/CMD: the api service and each job override command and args in
# Terraform (see infra/cloud_run_api.tf, infra/cloud_run_jobs.tf) — there is
# no single right default for an image that runs as seven different things.
