#!/usr/bin/env bash
set -euo pipefail

echo "This project now uses the Supabase Python client for app database access."
echo "Apply database schema manually in the Supabase dashboard:"
echo
echo "1. Open Supabase > SQL Editor."
echo "2. Paste and run schema.sql."
echo "3. For existing databases, also run migration_phase2_sentiment.sql and migration_phase4_alert_events.sql."
echo
echo "Then set SUPABASE_URL and SUPABASE_KEY in .env or Streamlit Secrets."
