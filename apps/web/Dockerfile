FROM node:24.22.1-bookworm-slim AS dependencies

ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH
WORKDIR /app
RUN npm install --global pnpm@10.34.8
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
COPY apps/web/package.json ./apps/web/package.json
COPY packages/config/package.json ./packages/config/package.json
COPY packages/ui/package.json ./packages/ui/package.json
COPY packages/contracts/package.json ./packages/contracts/package.json
RUN pnpm install --frozen-lockfile

FROM dependencies AS build
ENV NEXT_TELEMETRY_DISABLED=1
COPY apps/web ./apps/web
COPY packages ./packages
RUN pnpm --filter @nexora/web build

FROM node:24.22.1-bookworm-slim AS runtime
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
COPY --from=build --chown=node:node /app ./
USER node
EXPOSE 3000
CMD ["./node_modules/.bin/next", "start", "apps/web"]
