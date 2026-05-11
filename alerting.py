"""Hourly mention spike alerting with APScheduler and Telegram."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from config import DATABASE_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


ALERT_TYPE_MENTION_SPIKE = "mention_spike"


@dataclass(frozen=True)
class SpikeCheck:
    window_start: datetime
    window_end: datetime
    current_volume: int
    baseline_volume: float
    threshold_multiplier: float

    @property
    def threshold(self) -> float:
        return self.baseline_volume * self.threshold_multiplier

    @property
    def is_spike(self) -> bool:
        return self.baseline_volume > 0 and self.current_volume > self.threshold


def build_spike_message(check: SpikeCheck) -> str:
    return (
        "NASA Media Monitor alert\n"
        f"Mention spike detected: {check.current_volume} mentions in the last hour.\n"
        f"7-day hourly average: {check.baseline_volume:.2f}\n"
        f"Alert threshold: > {check.threshold:.2f} mentions "
        f"({check.threshold_multiplier:.1f}x baseline)\n"
        f"Window: {check.window_start:%Y-%m-%d %H:%M UTC} to "
        f"{check.window_end:%Y-%m-%d %H:%M UTC}"
    )


def send_telegram_message(bot_token: str, chat_id: str, message: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = urlencode(
        {
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    request = Request(url, data=data, method="POST")

    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram request failed with HTTP {error.code}: {details}") from error
    except URLError as error:
        raise RuntimeError(f"Telegram request failed: {error.reason}") from error

    if not payload.get("ok"):
        raise RuntimeError(f"Telegram API returned an error: {payload}")


def fetch_spike_check(database_url: str, threshold_multiplier: float) -> SpikeCheck:
    import psycopg
    from psycopg.rows import dict_row

    sql = """
        WITH bounds AS (
            SELECT
                date_trunc('hour', NOW()) AS window_end,
                date_trunc('hour', NOW()) - INTERVAL '1 hour' AS window_start
        ),
        current_window AS (
            SELECT COUNT(*)::int AS current_volume
            FROM mentions, bounds
            WHERE published_at >= bounds.window_start
                AND published_at < bounds.window_end
        ),
        baseline AS (
            SELECT (COUNT(*)::numeric / 168.0) AS baseline_volume
            FROM mentions, bounds
            WHERE published_at >= bounds.window_start - INTERVAL '7 days'
                AND published_at < bounds.window_start
        )
        SELECT
            bounds.window_start,
            bounds.window_end,
            current_window.current_volume,
            COALESCE(baseline.baseline_volume, 0) AS baseline_volume
        FROM bounds, current_window, baseline
    """

    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            row = cursor.fetchone()

    return SpikeCheck(
        window_start=row["window_start"],
        window_end=row["window_end"],
        current_volume=row["current_volume"],
        baseline_volume=float(row["baseline_volume"]),
        threshold_multiplier=threshold_multiplier,
    )


def alert_already_sent(database_url: str, check: SpikeCheck) -> bool:
    import psycopg

    sql = """
        SELECT 1
        FROM alert_events
        WHERE alert_type = %s
            AND window_start = %s
            AND window_end = %s
        LIMIT 1
    """

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                sql,
                (
                    ALERT_TYPE_MENTION_SPIKE,
                    check.window_start,
                    check.window_end,
                ),
            )
            return cursor.fetchone() is not None


def record_alert_sent(database_url: str, check: SpikeCheck) -> None:
    import psycopg

    sql = """
        INSERT INTO alert_events (
            alert_type,
            window_start,
            window_end,
            current_volume,
            baseline_volume,
            threshold_multiplier
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (alert_type, window_start, window_end) DO NOTHING
    """

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                sql,
                (
                    ALERT_TYPE_MENTION_SPIKE,
                    check.window_start,
                    check.window_end,
                    check.current_volume,
                    check.baseline_volume,
                    check.threshold_multiplier,
                ),
            )
        connection.commit()


def check_and_send_alert(
    database_url: str,
    telegram_bot_token: str,
    telegram_chat_id: str,
    threshold_multiplier: float,
    dry_run: bool = False,
) -> SpikeCheck:
    check = fetch_spike_check(database_url, threshold_multiplier)

    if not check.is_spike:
        print(
            "No spike detected: "
            f"{check.current_volume} mentions vs {check.baseline_volume:.2f} baseline."
        )
        return check

    if alert_already_sent(database_url, check):
        print("Spike detected, but alert was already sent for this hourly window.")
        return check

    message = build_spike_message(check)
    if dry_run:
        print(message)
        return check

    send_telegram_message(telegram_bot_token, telegram_chat_id, message)
    record_alert_sent(database_url, check)
    print("Telegram spike alert sent.")
    return check


def run_scheduler(
    database_url: str,
    telegram_bot_token: str,
    telegram_chat_id: str,
    threshold_multiplier: float,
) -> None:
    from apscheduler.schedulers.blocking import BlockingScheduler

    scheduler = BlockingScheduler(timezone=timezone.utc)
    scheduler.add_job(
        check_and_send_alert,
        "interval",
        hours=1,
        next_run_time=datetime.now(tz=timezone.utc),
        kwargs={
            "database_url": database_url,
            "telegram_bot_token": telegram_bot_token,
            "telegram_chat_id": telegram_chat_id,
            "threshold_multiplier": threshold_multiplier,
        },
        id="mention_spike_alert",
        replace_existing=True,
    )
    print("Alert scheduler started. Checking mention spikes every hour.")
    scheduler.start()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run NASA mention spike alerts.")
    parser.add_argument("--once", action="store_true", help="Run one spike check and exit.")
    parser.add_argument("--dry-run", action="store_true", help="Print the alert instead of sending it.")
    parser.add_argument("--threshold-multiplier", type=float, default=2.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.threshold_multiplier <= 0:
        raise SystemExit("--threshold-multiplier must be greater than 0.")

    if args.once:
        check_and_send_alert(
            database_url=DATABASE_URL,
            telegram_bot_token=TELEGRAM_BOT_TOKEN,
            telegram_chat_id=TELEGRAM_CHAT_ID,
            threshold_multiplier=args.threshold_multiplier,
            dry_run=args.dry_run,
        )
        return

    run_scheduler(
        database_url=DATABASE_URL,
        telegram_bot_token=TELEGRAM_BOT_TOKEN,
        telegram_chat_id=TELEGRAM_CHAT_ID,
        threshold_multiplier=args.threshold_multiplier,
    )


if __name__ == "__main__":
    main()
