#!/usr/bin/env bash
set -euo pipefail

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required. Add it to .env before running setup.sh." >&2
  exit 1
fi

echo "Running schema.sql..."
psql "$DATABASE_URL" -f schema.sql

echo "Running migration_phase4_alert_events.sql..."
psql "$DATABASE_URL" -f migration_phase4_alert_events.sql

echo "Database setup complete."
