# Phase 4 — Alerting

Add an APScheduler job that checks for mention spikes every hour and sends a Telegram bot message when volume exceeds `2x` the 7-day rolling hourly average.

## Files

- `alerting.py`: scheduled mention spike alert worker.
- `migration_phase4_alert_events.sql`: creates the alert log table for existing databases.
- `schema.sql`: updated fresh schema with `alert_events`.
- `test_alerting.py`: unit tests for spike detection and alert message formatting.
- `.env.example`: updated with Telegram credentials.
- `requirements.txt`: updated with APScheduler.

## Database Changes

Run this migration against an existing database:

```bash
psql "$DATABASE_URL" -f migration_phase4_alert_events.sql
```

The `alert_events` table records sent alerts so the worker does not send duplicate messages for the same hourly window.

## Telegram Setup

Add these variables to `.env`:

```text
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

## Run Once

Run one check and exit:

```bash
python alerting.py --once
```

Preview without sending a Telegram message:

```bash
python alerting.py --once --dry-run
```

## Run Scheduler

Start the hourly APScheduler worker:

```bash
python alerting.py
```

The worker checks immediately on startup, then every hour.

## Spike Logic

The worker compares:

- current volume: mentions published in the previous complete hour
- baseline volume: average hourly mention volume across the previous 7 days

An alert sends when:

```text
current_hour_volume > 2.0 * seven_day_hourly_average
```

You can override the threshold:

```bash
python alerting.py --threshold-multiplier 2.5
```

## Test

Run:

```bash
python -m unittest -q
```
