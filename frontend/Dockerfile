# syntax=docker/dockerfile:1.7

# ── Stage 1: Build the Vite bundle ──────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Install deps first for better layer caching
COPY package.json package-lock.json ./
RUN npm ci

# Vite inlines VITE_* at build time, so they must be present during `npm run build`.
# Railway passes these via service-level build args (configured in the dashboard).
ARG VITE_API_BASE
ARG VITE_CLERK_PUBLISHABLE_KEY
ENV VITE_API_BASE=${VITE_API_BASE}
ENV VITE_CLERK_PUBLISHABLE_KEY=${VITE_CLERK_PUBLISHABLE_KEY}

COPY . .
RUN npm run build

# ── Stage 2: Serve static assets via nginx ──────────────────────────────────
FROM nginx:1.27-alpine AS runtime

# nginx:alpine ships an entrypoint that runs envsubst over /etc/nginx/templates/*.template
# on container start — that's how we bind to Railway's dynamic $PORT.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=builder /app/dist /usr/share/nginx/html

# Only substitute $PORT; leave nginx's own $uri, $http_*, etc. untouched.
ENV NGINX_ENVSUBST_FILTER="^PORT$"

# Sensible default; Railway overrides PORT at runtime.
ENV PORT=8080
EXPOSE 8080

# Basic healthcheck — nginx serves index.html on any path thanks to SPA fallback.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null "http://127.0.0.1:${PORT}/" || exit 1

CMD ["nginx", "-g", "daemon off;"]
