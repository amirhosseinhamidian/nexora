Nexora local Docker kit (developer preview, not production)

Copy BOTH files into the ROOT of the Nexora Git repository (next to package.json).

1. Stop previous "docker run --name nexora-web" with Ctrl+C.
2. From Nexora repository root, run:
   bash nexora-local.sh up
3. Trust locally generated TLS certificate:
   bash nexora-local.sh trust
4. Create one-time bootstrap token:
   bash nexora-local.sh bootstrap
5. Open https://localhost:8443/fa/bootstrap ; complete passkey registration.
   Save recovery codes OFFLINE. Then visit https://localhost:8443/fa/login.

Other commands:
  bash nexora-local.sh status
  bash nexora-local.sh logs
  bash nexora-local.sh worker
  bash nexora-local.sh down

Safety: The compose uses port 8443 bound to 127.0.0.1 only, does not enable TRD Bot sync,
never performs real orders, and is local development only. Database volume survives down.
Do NOT run `docker compose down -v` unless you explicitly want to delete local data.
Credentials under ~/.config/nexora-docker are not committed to Git.

If Docker Desktop cannot start 'gateway' with network_mode service:api, report the
exact docker compose logs. Do not expose API via 0.0.0.0 or turn off its security
checks to work around the issue.
