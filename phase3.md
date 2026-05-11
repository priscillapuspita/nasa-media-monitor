# Phase 3 — Streamlit Dashboard

Build a Streamlit dashboard that reads from the Supabase `mentions` table and visualizes NASA media coverage.

## Files

- `streamlit_dashboard.py`: Streamlit application.
- `test_streamlit_dashboard.py`: unit tests for keyword extraction, alert logic, and timestamp formatting.
- `requirements.txt`: updated with Streamlit, pandas, and Plotly.

## Dashboard Views

The dashboard displays:

- daily mention volume line chart
- sentiment donut chart
- top sources bar chart
- trending keywords
- live alert feed

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Make sure `.env` contains:

```text
SUPABASE_URL=https://tjqxdpoygfwdfmqjybsv.supabase.co
SUPABASE_KEY=your_supabase_anon_public_key
```

## Run

```bash
streamlit run streamlit_dashboard.py
```

## Data Requirements

The dashboard expects the `mentions` table from Phase 1 and the sentiment columns from Phase 2:

```sql
sentiment_label
sentiment_confidence
sentiment_analyzed_at
```

If no data is available, the dashboard shows an empty-state message instead of failing.

## Live Alert Feed

The alert feed currently highlights:

- negative mentions with confidence of at least `0.60`
- positive mentions with confidence of at least `0.85`
- undated mentions, because they may need data cleanup

## Test

Run:

```bash
python -m unittest -q
```
