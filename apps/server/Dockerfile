FROM ghcr.io/astral-sh/uv:0.13.4 AS uv
FROM python:3.13.16-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app
COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
COPY apps/server ./apps/server
RUN uv sync --frozen --no-dev

USER 65532:65532
EXPOSE 8000
CMD ["uv", "run", "--frozen", "nexora-api"]
