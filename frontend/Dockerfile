FROM node:24-bookworm-slim AS development
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
RUN chown node:node /app
USER node
COPY --chown=node:node package.json package-lock.json ./
RUN --mount=type=cache,target=/home/node/.npm,uid=1000,gid=1000 npm ci --include=dev --no-audit --no-fund --fetch-retries=1 --fetch-timeout=60000
COPY --chown=node:node . .
RUN mkdir -p .next
EXPOSE 3000
CMD ["npm", "run", "dev"]

FROM node:24-bookworm-slim AS builder
ENV NEXT_TELEMETRY_DISABLED=1 NODE_ENV=production
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --include=dev --no-audit --no-fund --fetch-retries=1 --fetch-timeout=60000
COPY . .
RUN npm run build

FROM node:24-bookworm-slim AS production
ENV NEXT_TELEMETRY_DISABLED=1 NODE_ENV=production HOSTNAME=0.0.0.0 PORT=3000
WORKDIR /app
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
COPY --from=builder --chown=node:node /app/public ./public
USER node
EXPOSE 3000
HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=5 CMD node -e "fetch('http://127.0.0.1:3000/health').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"
CMD ["node", "server.js"]
