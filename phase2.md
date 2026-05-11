# Phase 2 — Sentiment Analysis

Add a sentiment analysis module that reads rows from the Supabase `mentions` table, classifies each mention as `positive`, `neutral`, or `negative`, and writes the sentiment label plus confidence score back.

## Files

- `sentiment_analysis.py`: batch sentiment analysis script.
- `migration_phase2_sentiment.sql`: migration for existing Phase 1 databases.
- `schema.sql`: updated fresh database schema with sentiment columns.
- `test_sentiment_analysis.py`: unit tests for label mapping and sentiment text preparation.
- `requirements.txt`: updated with the `requests` dependency for hosted HuggingFace inference.

## Model

This phase uses the HuggingFace Inference API with this model:

```text
cardiffnlp/twitter-roberta-base-sentiment
```

The model returns Cardiff labels:

- `LABEL_0` -> `negative`
- `LABEL_1` -> `neutral`
- `LABEL_2` -> `positive`

## Database Changes

Run this migration against an existing Phase 1 database:

Run `migration_phase2_sentiment.sql` in the Supabase SQL editor.

The migration adds:

```sql
sentiment_label TEXT
sentiment_confidence NUMERIC(5, 4)
sentiment_analyzed_at TIMESTAMPTZ
```

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Add a HuggingFace API token to `.env`:

```text
HUGGINGFACE_API_TOKEN=your_huggingface_api_token
```

## Run

Analyze rows that do not have sentiment yet:

```bash
python sentiment_analysis.py
```

Process a smaller batch:

```bash
python sentiment_analysis.py --limit 25 --batch-size 4
```

Reprocess existing sentiment rows:

```bash
python sentiment_analysis.py --force
```

## Processing Logic

The script:

- loads `SUPABASE_URL` and `SUPABASE_KEY` from `.env`, Streamlit secrets, or the shell environment
- selects mentions where `sentiment_label IS NULL`
- combines `headline` and `raw_text`
- cleans HTML and whitespace
- classifies sentiment through the HuggingFace Inference API
- stores `sentiment_label`, `sentiment_confidence`, and `sentiment_analyzed_at`

## Test

Run:

```bash
python -m unittest -q
```
