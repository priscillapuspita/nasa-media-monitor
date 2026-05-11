#!/usr/bin/env bash
set -euo pipefail

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
else
  echo "Virtual environment not found at .venv/bin/activate." >&2
  echo "Create it with: python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

streamlit run streamlit_dashboard.py --server.port 8501
