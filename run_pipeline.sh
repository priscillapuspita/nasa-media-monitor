#!/usr/bin/env bash
set -euo pipefail

LOG_FILE="pipeline.log"

log() {
  printf '[%s] %s\n' "$(date -u '+%Y-%m-%d %H:%M:%S UTC')" "$*" | tee -a "$LOG_FILE"
}

run_step() {
  local name="$1"
  shift

  log "Starting: ${name}"
  {
    printf '[%s] Command: %s\n' "$(date -u '+%Y-%m-%d %H:%M:%S UTC')" "$*"
    "$@"
  } 2>&1 | while IFS= read -r line; do
    log "$line"
  done
  log "Finished: ${name}"
}

log "Pipeline started."
run_step "Ingest mentions" python ingest_mentions.py
run_step "Analyze sentiment" python sentiment_analysis.py
run_step "Dry-run alerts" python alerting.py --once --dry-run
log "Pipeline completed."
