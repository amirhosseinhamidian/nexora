FROM ghcr.io/astral-sh/uv:0.13.4 AS uv
FROM python:3.13.16-slim-bookworm AS python
FROM postgres:17.6-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH=/app/.venv/bin:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin

COPY --from=python /usr/local /usr/local
COPY --from=uv /uv /uvx /bin/
RUN apt-get update \
    && apt-get install --yes --no-install-recommends age=1.1.1-1+b3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY apps/server ./apps/server
RUN uv sync --frozen --no-dev
COPY infra/operations ./infra/operations

ENTRYPOINT []
CMD ["/bin/sh"]
