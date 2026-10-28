FROM ghcr.io/astral-sh/uv:0.13.4 AS uv
FROM python:3.13.16-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/tmp/nexora-uv-cache \
    PATH=/app/.venv/bin:$PATH

WORKDIR /app
COPY --from=uv /uv /uvx /bin/
COPY --chown=65532:65532 pyproject.toml uv.lock ./
COPY --chown=65532:65532 apps/server ./apps/server
COPY --chown=65532:65532 alembic.ini ./
COPY --chown=65532:65532 alembic ./alembic
RUN uv sync --frozen --no-dev \
    && rm -rf "$UV_CACHE_DIR" \
    && mkdir -p /var/lib/nexora/artifacts /var/log/nexora \
    && chmod 0700 /var/lib/nexora/artifacts /var/log/nexora \
    && chown -R 65532:65532 \
        /app /var/lib/nexora/artifacts /var/log/nexora

USER 65532:65532
EXPOSE 8000
CMD ["nexora-api"]
