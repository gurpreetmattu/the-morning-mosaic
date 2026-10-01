# Multi-stage build producing Next.js's standalone output: a self-contained
# server.js plus only the node_modules it actually traced as used, rather
# than the whole dependency tree.

FROM node:22-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# BACKEND_ORIGIN is read at request time (see next.config.ts), not needed
# to build. The one value baked in is the *public* Turnstile site key: Next
# inlines NEXT_PUBLIC_* into the client bundle at build time, so passing it
# only at runtime leaves the widget unrendered and blocks every signup in prod.
# Pass it with --build-arg; the secret key never enters this image.
ARG NEXT_PUBLIC_TURNSTILE_SITE_KEY=""
ENV NEXT_PUBLIC_TURNSTILE_SITE_KEY=$NEXT_PUBLIC_TURNSTILE_SITE_KEY
RUN npm run build

FROM node:22-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production PORT=8080 HOSTNAME=0.0.0.0

RUN groupadd --system app && useradd --system --gid app app
COPY --from=builder /app/public ./public
COPY --from=builder --chown=app:app /app/.next/standalone ./
COPY --from=builder --chown=app:app /app/.next/static ./.next/static

USER app
EXPOSE 8080
CMD ["node", "server.js"]
