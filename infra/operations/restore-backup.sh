#!/bin/sh
set -eu

umask 077

[ "${NEXORA_RESTORE_OWNER_PRESENT:-}" = "yes" ] || {
  echo "restore requires explicit owner presence" >&2
  exit 2
}
[ "${NEXORA_RESTORE_RECENT_REAUTHENTICATION:-}" = "yes" ] || {
  echo "restore requires recent owner reauthentication" >&2
  exit 2
}
[ "${NEXORA_RUNTIME_STOPPED_CONFIRM:-}" = "yes" ] || {
  echo "API, Web and Worker must be stopped before restore" >&2
  exit 2
}
[ -n "${NEXORA_RESTORE_BACKUP_ID:-}" ] || {
  echo "NEXORA_RESTORE_BACKUP_ID is required" >&2
  exit 2
}
[ "${NEXORA_RESTORE_CONFIRM:-}" = "RESTORE-$NEXORA_RESTORE_BACKUP_ID" ] || {
  echo "restore confirmation does not match the selected backup" >&2
  exit 2
}

for command in age pg_restore psql python3 nexora-operations; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "required restore command is unavailable: $command" >&2
    exit 2
  }
done

for variable in NEXORA_RESTORE_IDENTITY_FILE NEXORA_POSTGRES_PASSWORD_FILE; do
  value="$(eval "printf '%s' \"\${$variable:-}\"")"
  [ -n "$value" ] && [ "${value#/}" != "$value" ] && [ -f "$value" ] && [ ! -L "$value" ] || {
    echo "$variable must name an absolute regular non-symbolic file" >&2
    exit 2
  }
done
python3 - "$NEXORA_RESTORE_IDENTITY_FILE" <<'PY'
import pathlib
import re
import sys

lines = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
if len(lines) != 1 or re.fullmatch(r"AGE-SECRET-KEY-1[0-9A-Z]{50,100}", lines[0]) is None:
    raise SystemExit("restore identity must contain exactly one age X25519 private identity")
PY

case "${NEXORA_BACKUP_OFFSITE_ROOT:-}" in
  /*) ;;
  *) echo "NEXORA_BACKUP_OFFSITE_ROOT must be absolute" >&2; exit 2 ;;
esac
case "${NEXORA_ARTIFACT_ROOT:-}" in
  /*) ;;
  *) echo "NEXORA_ARTIFACT_ROOT must be absolute" >&2; exit 2 ;;
esac
[ -d "$NEXORA_ARTIFACT_ROOT" ] && [ ! -L "$NEXORA_ARTIFACT_ROOT" ] || exit 2
[ -z "$(find "$NEXORA_ARTIFACT_ROOT" -mindepth 1 -maxdepth 1 -print -quit)" ] || {
  echo "artifact restore target must be empty" >&2
  exit 2
}

nexora-operations verify-backup \
  --root "$NEXORA_BACKUP_OFFSITE_ROOT" \
  --backup-id "$NEXORA_RESTORE_BACKUP_ID" >/dev/null

staging="$(mktemp -d "${TMPDIR:-/tmp}/nexora-restore.XXXXXXXX")"
cleanup() {
  chmod -R u+rwX "$staging" 2>/dev/null || true
  rm -rf "$staging"
}
trap cleanup EXIT HUP INT TERM

age \
  --decrypt \
  --identity="$NEXORA_RESTORE_IDENTITY_FILE" \
  --output="$staging/bundle.tar" \
  "$NEXORA_BACKUP_OFFSITE_ROOT/$NEXORA_RESTORE_BACKUP_ID.tar.age"

python3 - "$staging/bundle.tar" "$staging" <<'PY'
import json
import hashlib
import pathlib
import tarfile
import sys

bundle = pathlib.Path(sys.argv[1])
target = pathlib.Path(sys.argv[2])
with tarfile.open(bundle) as archive:
    archive.extractall(target, filter="data")
payload = json.loads((target / "contents.json").read_text(encoding="utf-8"))
if payload.get("schema_version") != "nexora-backup-contents-v1" or payload.get("secrets_included") is not False:
    raise SystemExit("backup contents manifest is invalid")
for entry in payload.get("files", []):
    path = target / entry["name"]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if path.stat().st_size != entry["size_bytes"] or digest != entry["sha256"]:
        raise SystemExit("backup content checksum mismatch")
PY

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

PGPASSFILE="$staging/pgpass" psql \
  --host=postgresql \
  --port=5432 \
  --username=nexora \
  --dbname=nexora \
  --set=ON_ERROR_STOP=1 \
  --command="DROP SCHEMA IF EXISTS nexora CASCADE;"

PGPASSFILE="$staging/pgpass" pg_restore \
  --host=postgresql \
  --port=5432 \
  --username=nexora \
  --dbname=nexora \
  --clean \
  --if-exists \
  --no-owner \
  --no-acl \
  "$staging/database.dump"

python3 - "$staging/artifacts.tar" "$NEXORA_ARTIFACT_ROOT" <<'PY'
import pathlib
import sys
import tarfile

archive_path = pathlib.Path(sys.argv[1])
target = pathlib.Path(sys.argv[2])
with tarfile.open(archive_path) as archive:
    if any(member.issym() or member.islnk() for member in archive.getmembers()):
        raise SystemExit("artifact restore archive cannot contain links")
    archive.extractall(target, filter="data")
PY

PGPASSFILE="$staging/pgpass" psql \
  --host=postgresql \
  --port=5432 \
  --username=nexora \
  --dbname=nexora \
  --set=ON_ERROR_STOP=1 \
  --command="UPDATE nexora.sessions SET revoked_at = CURRENT_TIMESTAMP WHERE revoked_at IS NULL; UPDATE nexora.service_tokens SET revoked_at = CURRENT_TIMESTAMP WHERE revoked_at IS NULL;"

echo "NEXORA_RESTORE_REQUIRES_SERVICE_TOKEN_ROTATION=yes"
echo "Keep the runtime stopped until a new scoped service token is registered on both systems."
