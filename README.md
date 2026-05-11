# NASA Media Monitor

A personal media intelligence project inspired by platforms like Meltwater. It ingests NASA-related mentions from NewsAPI and Reddit, stores them in PostgreSQL, scores sentiment with the HuggingFace Inference API, displays a Streamlit dashboard, and sends Telegram alerts when mention volume spikes.

## Features

- NewsAPI and Reddit ingestion
- PostgreSQL storage
- HuggingFace-hosted sentiment analysis
- Streamlit dashboard
- Hourly APScheduler spike alerts
- Telegram bot notifications

## Setup

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create your environment file:

```bash
cp .env.example .env
```

Then fill in the placeholder values in `.env`.

## Environment Variables

Required by the full pipeline:

- `DATABASE_URL`: PostgreSQL connection string.
- `NEWSAPI_KEY`: API key for NewsAPI article search.
- `HUGGINGFACE_API_TOKEN`: HuggingFace token for hosted sentiment inference.
- `REDDIT_CLIENT_ID`: Reddit app client ID.
- `REDDIT_CLIENT_SECRET`: Reddit app client secret.
- `REDDIT_USER_AGENT`: Reddit API user agent string.
- `MENTION_QUERY`: default query for NASA-related monitoring.
- `TELEGRAM_BOT_TOKEN`: Telegram bot token for alert messages.
- `TELEGRAM_CHAT_ID`: Telegram chat ID that receives alerts.

## Database

Create a PostgreSQL database:

```bash
createdb nasa_media_monitor
```

Run migrations:

```bash
./setup.sh
```

This runs:

```bash
psql "$DATABASE_URL" -f schema.sql
psql "$DATABASE_URL" -f migration_phase4_alert_events.sql
```

For an existing Phase 1 database, also run:

```bash
psql "$DATABASE_URL" -f migration_phase2_sentiment.sql
```

## Run Scripts

Ingest NASA mentions:

```bash
python ingest_mentions.py
```

Analyze sentiment:

```bash
python sentiment_analysis.py
```

Run one dry-run alert check:

```bash
python alerting.py --once --dry-run
```

Run the hourly alert scheduler:

```bash
python alerting.py
```

Run the full local pipeline:

```bash
./run_pipeline.sh
```

Pipeline output is appended to `pipeline.log`.

## Dashboard

Start Streamlit locally:

```bash
./start_dashboard.sh
```

Or run directly:

```bash
streamlit run streamlit_dashboard.py --server.port 8501
```

Then open:

```text
http://localhost:8501
```

## Tests

Run the offline test suite:

```bash
python -m unittest -q
```

## Deployment Notes

For Streamlit Community Cloud:

- app file: `streamlit_dashboard.py`
- dependencies: `requirements.txt`
- Streamlit config: `streamlit_app_config.toml`
- configure secrets/environment variables in the Streamlit Cloud settings

Keep `.env` out of Git. It is ignored by `.gitignore`.
