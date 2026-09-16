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
# to build; no env vars are baked into this image.
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
