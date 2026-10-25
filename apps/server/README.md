# Nexora server

The server package contains a minimal FastAPI liveness boundary, an inert worker,
typed non-secret runtime settings, and one explicit composition factory shared
by both entry points. Database, authentication, TRD Bot integration, durable jobs,
and production readiness are intentionally deferred.

```bash
uv run nexora-api
uv run nexora-worker --check
```

Configuration is read only from the allowlisted `NEXORA_*` process environment
variables documented in `.env.example`. Unknown prefixed variables and unsafe
profile combinations fail closed; dotenv files are never loaded automatically.
