#!/bin/sh
set -eu

mode=""
if [ "${1:-}" = "--apply" ]; then
  [ "${NEXORA_RETENTION_OWNER_APPROVED:-}" = "yes" ] || {
    echo "retention apply requires explicit owner approval" >&2
    exit 2
  }
  mode="--apply"
elif [ -n "${1:-}" ]; then
  echo "usage: run-retention.sh [--apply]" >&2
  exit 2
fi

nexora-operations retention $mode
exec nexora-operations backup-retention $mode
