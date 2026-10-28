#!/bin/sh
set -eu

umask 077

require_file() {
  value="$(eval "printf '%s' \"\${$1:-}\"")"
  [ -n "$value" ] && [ "${value#/}" != "$value" ] && [ -f "$value" ] && [ ! -L "$value" ] || {
    echo "$1 must name an absolute regular non-symbolic file" >&2
    exit 2
  }
}

require_directory() {
  value="$(eval "printf '%s' \"\${$1:-}\"")"
  [ -n "$value" ] && [ "${value#/}" != "$value" ] && [ -d "$value" ] && [ ! -L "$value" ] || {
    echo "$1 must name an absolute non-symbolic directory" >&2
    exit 2
  }
}

for command in age pg_dump python3 tar; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "required backup command is unavailable: $command" >&2
    exit 2
  }
done

require_file NEXORA_POSTGRES_PASSWORD_FILE
require_file NEXORA_AGE_RECIPIENT_FILE
require_directory NEXORA_ARTIFACT_ROOT
require_directory NEXORA_BACKUP_ROOT
require_directory NEXORA_BACKUP_OFFSITE_ROOT

python3 - "$NEXORA_AGE_RECIPIENT_FILE" <<'PY'
import pathlib
import re
import sys

lines = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
if len(lines) != 1 or re.fullmatch(r"age1[0-9a-z]{50,100}", lines[0]) is None:
    raise SystemExit("age recipient file must contain exactly one X25519 public recipient")
PY

case "${SOURCE_COMMIT_SHA:-}" in
  *[!0-9a-f]*|'')
    echo "SOURCE_COMMIT_SHA must be the deployed 40-character commit SHA" >&2
    exit 2
    ;;
  *)
    [ "${#SOURCE_COMMIT_SHA}" -eq 40 ] || {
      echo "SOURCE_COMMIT_SHA must be the deployed 40-character commit SHA" >&2
      exit 2
    }
    ;;
esac

created_at="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
entropy="$(python3 -c 'import secrets; print(secrets.token_hex(4))')"
backup_id="$(date -u '+%Y%m%dT%H%M%SZ')-$entropy"
staging="$(mktemp -d "${TMPDIR:-/tmp}/nexora-backup.XXXXXXXX")"
cleanup() {
  chmod -R u+rwX "$staging" 2>/dev/null || true
  rm -rf "$staging"
}
trap cleanup EXIT HUP INT TERM

python3 - "$NEXORA_POSTGRES_PASSWORD_FILE" "$staging/pgpass" <<'PY'
import pathlib
import sys

password = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").removesuffix("\n")
if not password or "\n" in password or "\r" in password or "\0" in password:
    raise SystemExit("PostgreSQL password file must contain exactly one non-empty line")
escaped = password.replace("\\", "\\\\").replace(":", "\\:")
pathlib.Path(sys.argv[2]).write_text(f"postgresql:5432:nexora:nexora:{escaped}\n", encoding="utf-8")
PY
chmod 0600 "$staging/pgpass"

PGPASSFILE="$staging/pgpass" pg_dump \
  --host=postgresql \
  --port=5432 \
  --username=nexora \
  --dbname=nexora \
  --format=custom \
  --no-owner \
  --no-acl \
  --file="$staging/database.dump"

tar \
  --create \
  --file="$staging/artifacts.tar" \
  --numeric-owner \
  --owner=0 \
  --group=0 \
  --sort=name \
  --mtime='@0' \
  --directory="$NEXORA_ARTIFACT_ROOT" \
  .

python3 - "$staging" "$backup_id" "$created_at" <<'PY'
import hashlib
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
files = []
for name in ("database.dump", "artifacts.tar"):
    path = root / name
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    files.append({"name": name, "size_bytes": size, "sha256": digest.hexdigest()})
payload = {
    "schema_version": "nexora-backup-contents-v1",
    "backup_id": sys.argv[2],
    "created_at": sys.argv[3],
    "files": files,
    "secrets_included": False,
}
(root / "contents.json").write_text(
    json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
    encoding="utf-8",
)
PY

tar \
  --create \
  --file="$staging/$backup_id.tar" \
  --numeric-owner \
  --owner=0 \
  --group=0 \
  --sort=name \
  --mtime='@0' \
  --directory="$staging" \
  database.dump artifacts.tar contents.json

age \
  --encrypt \
  --recipients-file="$NEXORA_AGE_RECIPIENT_FILE" \
  --output="$staging/$backup_id.tar.age" \
  "$staging/$backup_id.tar"

nexora-operations publish-backup \
  --backup-id "$backup_id" \
  --created-at "$created_at" \
  "$staging/$backup_id.tar.age"

echo "NEXORA_BACKUP_CREATED=$backup_id"
