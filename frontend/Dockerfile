FROM node:20-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json ./

# Install every dependency, including devDependencies: `next build` needs
# typescript, tailwindcss and @tailwindcss/postcss, which live in
# devDependencies. `npm ci --only=production` here made the build stage fail.
RUN npm ci


FROM node:20-alpine AS builder

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Rewrites are resolved at build time and serialised into the build manifest, so
# a runtime environment variable cannot change the proxy target. The image must
# bake in the compose service name; the browser cannot resolve it, only the Next
# server can, and only from inside the Docker network.
ARG BACKEND_INTERNAL_URL=http://backend:8000
ENV BACKEND_INTERNAL_URL=$BACKEND_INTERNAL_URL
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build


FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
