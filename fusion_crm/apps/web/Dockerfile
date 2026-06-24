# Fusion CRM — Web image (Next.js 14, App Router, standalone output)
#
# Three-stage build:
#   1. deps     — install npm deps (cached layer keyed on package-lock)
#   2. builder  — `next build` -> .next/standalone + .next/static
#   3. runner   — slim runtime image with only standalone output
#
# Built from `apps/web` as context (see deploy-prod.yml build-web job).
# Runs as non-root uid 10001 per apps/CLAUDE.md.

FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# `next build` emits .next/standalone and .next/static when
# next.config.mjs sets `output: "standalone"`.
# COMMIT_SHA flows in via `docker build --build-arg COMMIT_SHA=...` from
# deploy-prod.yml. next.config.mjs bakes it as NEXT_PUBLIC_COMMIT_SHA so
# VersionWatcher can detect a backend upgrade (ENG-150).
ARG COMMIT_SHA=dev
ENV COMMIT_SHA=$COMMIT_SHA
# ``INTERNAL_API_URL`` has to be available at BUILD time too — the
# ``rewrites()`` block in ``next.config.mjs`` reads it to compose the
# ``/api/*`` fallback destination and bakes the result into the
# standalone bundle. Setting it only as a runtime Cloud Run env var
# leaves the bundle on the localhost:8000 default, which then
# ECONNREFUSEDs in production (ENG-158).
ARG INTERNAL_API_URL=http://localhost:8000
ENV INTERNAL_API_URL=$INTERNAL_API_URL
# ``NEXT_PUBLIC_API_BASE_URL`` is exposed to the client bundle for
# anything that needs the public origin (e.g. absolute links in
# emails). Default to the local dev origin; deploy passes the prod
# value as a build-arg.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:3000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Non-root runtime user (uid 10001 — matches apps/api + apps/worker).
RUN addgroup --system --gid 10001 nextjs \
 && adduser --system --uid 10001 nextjs

# Public assets (favicon, mockServiceWorker.js, etc.) are served by
# Next.js directly from /public.
COPY --from=builder --chown=nextjs:nextjs /app/public ./public

# Semantic Analytics workbench docs are read with fs at request time.
# Standalone tracing does not automatically copy arbitrary markdown files.
COPY --from=builder --chown=nextjs:nextjs /app/content ./content

# .next/standalone is a fully self-contained Node server with only
# the deps Next.js detected via tracing. .next/static must be copied
# alongside it under .next/static.
COPY --from=builder --chown=nextjs:nextjs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

# Cloud Run probes `/` by default. Next.js handles the response.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
    CMD wget -q -O - http://127.0.0.1:3000/ >/dev/null || exit 1

CMD ["node", "server.js"]
