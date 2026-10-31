#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
COMPOSE_FILE="docker-compose.nexora-local.yml"
export NEXORA_LOCAL_DIR="$HOME/.config/nexora-docker"

compose() {
  docker compose -f "$COMPOSE_FILE" "$@"
}

setup() {
  mkdir -p "$NEXORA_LOCAL_DIR/artifacts"
  chmod 700 "$NEXORA_LOCAL_DIR" "$NEXORA_LOCAL_DIR/artifacts"

  if [[ ! -e "$NEXORA_LOCAL_DIR/db-password" ]]; then
    (umask 077; openssl rand -hex 32 > "$NEXORA_LOCAL_DIR/db-password")
  fi
  if [[ ! -e "$NEXORA_LOCAL_DIR/auth-pepper" ]]; then
    (umask 077; openssl rand -hex 32 > "$NEXORA_LOCAL_DIR/auth-pepper")
  fi
  printf 'postgresql+psycopg://nexora:%s@db:5432/nexora\n' \
    "$(cat "$NEXORA_LOCAL_DIR/db-password")" > "$NEXORA_LOCAL_DIR/db.dsn"
  printf 'https://localhost:8443\n' > "$NEXORA_LOCAL_DIR/origin"
  chmod 600 "$NEXORA_LOCAL_DIR/db-password" "$NEXORA_LOCAL_DIR/auth-pepper" \
    "$NEXORA_LOCAL_DIR/db.dsn" "$NEXORA_LOCAL_DIR/origin"

  cat > "$NEXORA_LOCAL_DIR/Caddyfile" <<'CADDY'
{
  auto_https disable_redirects
}

https://localhost:8443 {
  tls internal

  handle_path /api/* {
    reverse_proxy 127.0.0.1:8000
  }

  handle /health/* {
    reverse_proxy 127.0.0.1:8000
  }

  handle {
    reverse_proxy web:3000
  }
}
CADDY
  chmod 600 "$NEXORA_LOCAL_DIR/Caddyfile"
}

case "${1:-}" in
  up)
    setup
    if ! docker image inspect nexora-web:local >/dev/null 2>&1; then
      echo 'Building Nexora web image ...'
      docker build -f apps/web/Dockerfile -t nexora-web:local .
    fi
    compose up -d --wait db
    compose build api
    compose run --rm migrate
    compose up -d api web gateway
    echo
    echo 'Open: https://localhost:8443/fa/bootstrap'
    echo 'API:  https://localhost:8443/health/live'
    echo 'To trust local HTTPS: bash nexora-local.sh trust'
    echo 'To issue a bootstrap token: bash nexora-local.sh bootstrap'
    ;;
  trust)
    # Trigger Caddy's internal CA initialization, ignoring untrusted TLS for this smoke.
    curl --silent --show-error --insecure --max-time 15 \
      https://localhost:8443/health/live >/dev/null
    compose cp gateway:/data/caddy/pki/authorities/local/root.crt \
      "$NEXORA_LOCAL_DIR/caddy-local-ca.crt"
    echo 'Trusting Caddy local development CA in macOS login keychain ...'
    security add-trusted-cert -d -r trustRoot \
      -k "$HOME/Library/Keychains/login.keychain-db" \
      "$NEXORA_LOCAL_DIR/caddy-local-ca.crt"
    echo 'Local CA trust requested. Restart the browser if HTTPS is still marked untrusted.'
    ;;
  bootstrap)
    compose exec -T api nexora-identity create-bootstrap-token
    ;;
  worker)
    compose --profile worker up -d worker
    ;;
  status)
    compose ps
    ;;
  logs)
    compose logs --tail 100 api web gateway db
    ;;
  down)
    compose down
    echo 'Stopped. Database and certificate volumes were preserved.'
    ;;
  *)
    echo "Usage: bash nexora-local.sh {up|trust|bootstrap|worker|status|logs|down}"
    exit 2
    ;;
esac
