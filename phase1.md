# Phase 1 — Data Ingestion + Storage

Build a Python ingestion layer that fetches NASA-related media mentions from NewsAPI and Reddit, cleans the records, and stores them in PostgreSQL.

## Files

- `schema.sql`: PostgreSQL schema for the `mentions` table.
- `ingest_mentions.py`: ingestion script for NewsAPI and Reddit.
- `.env.example`: required environment variables.
- `requirements.txt`: Python dependency list.
- `test_ingest_mentions.py`: unit tests for text cleaning and timestamp parsing.

## Database Schema

```sql
CREATE TABLE IF NOT EXISTS mentions (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    headline TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    published_at TIMESTAMPTZ,
    raw_text TEXT
);
```

## Setup

1. Create a PostgreSQL database:

```bash
createdb nasa_media_monitor
```

2. Apply the schema:

```bash
psql "$DATABASE_URL" -f schema.sql
```

3. Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

4. Create a local `.env` file based on `.env.example`. The ingestion script loads this file automatically.

## Required API Credentials

NewsAPI:

- `NEWSAPI_KEY`

Reddit:

- `REDDIT_CLIENT_ID`
- `REDDIT_CLIENT_SECRET`
- `REDDIT_USER_AGENT`

The Reddit script uses the official OAuth client-credentials flow and searches Reddit through `oauth.reddit.com/search`.

## Run

```bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/nasa_media_monitor
export NEWSAPI_KEY=your_newsapi_key
export REDDIT_CLIENT_ID=your_reddit_client_id
export REDDIT_CLIENT_SECRET=your_reddit_client_secret
export REDDIT_USER_AGENT="nasa-media-monitor/0.1 by your_reddit_username"

python ingest_mentions.py
```

Optional custom query:

```bash
python ingest_mentions.py --query 'NASA OR Artemis OR "James Webb"' --news-limit 25 --reddit-limit 25
```

## Cleaning Logic

The script:

- removes HTML tags from text fields
- decodes HTML entities
- collapses extra whitespace
- ignores records without a headline or URL
- deduplicates records by URL with PostgreSQL `ON CONFLICT`

## Output

The script prints a short ingestion summary:

```text
Fetched 32 NewsAPI mentions, 18 Reddit mentions, stored 50 records.
```

## Test

Run the built-in unit tests:

```bash
python -m unittest -q
```
