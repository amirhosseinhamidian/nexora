# Nexora server

The P1-01 server package contains only the minimal FastAPI liveness boundary and
an inert worker composition root. Database, authentication, TRD Bot integration,
durable jobs, and production readiness are intentionally deferred.

```bash
uv run nexora-api
uv run nexora-worker --check
```
