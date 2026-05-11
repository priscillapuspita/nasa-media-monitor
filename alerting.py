"""Hourly mention spike alerting with APScheduler and Telegram."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from config import ConfigError, get_supabase_client, require_env


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


def parse_timestamp(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def fetch_spike_check(supabase_client, threshold_multiplier: float) -> SpikeCheck:
    now = datetime.now(tz=timezone.utc)
    window_end = now.replace(minute=0, second=0, microsecond=0)
    window_start = window_end - timedelta(hours=1)
    baseline_start = window_start - timedelta(days=7)

    response = (
        supabase_client.table("mentions")
        .select("published_at")
        .gte("published_at", baseline_start.isoformat())
        .lt("published_at", window_end.isoformat())
        .execute()
    )

    current_volume = 0
    baseline_count = 0
    for row in response.data:
        published_at = parse_timestamp(row.get("published_at"))
        if published_at is None:
            continue
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        if window_start <= published_at < window_end:
            current_volume += 1
        if baseline_start <= published_at < window_start:
            baseline_count += 1

    baseline_volume = baseline_count / 168.0

    return SpikeCheck(
        window_start=window_start,
        window_end=window_end,
        current_volume=current_volume,
        baseline_volume=baseline_volume,
        threshold_multiplier=threshold_multiplier,
    )


def alert_already_sent(supabase_client, check: SpikeCheck) -> bool:
    response = (
        supabase_client.table("alert_events")
        .select("id")
        .eq("alert_type", ALERT_TYPE_MENTION_SPIKE)
        .eq("window_start", check.window_start.isoformat())
        .eq("window_end", check.window_end.isoformat())
        .limit(1)
        .execute()
    )
    return bool(response.data)


def record_alert_sent(supabase_client, check: SpikeCheck) -> None:
    supabase_client.table("alert_events").upsert(
        {
            "alert_type": ALERT_TYPE_MENTION_SPIKE,
            "window_start": check.window_start.isoformat(),
            "window_end": check.window_end.isoformat(),
            "current_volume": check.current_volume,
            "baseline_volume": check.baseline_volume,
            "threshold_multiplier": check.threshold_multiplier,
        },
        on_conflict="alert_type,window_start,window_end",
    ).execute()


def check_and_send_alert(
    supabase_client,
    telegram_bot_token: str,
    telegram_chat_id: str,
    threshold_multiplier: float,
    dry_run: bool = False,
) -> SpikeCheck:
    check = fetch_spike_check(supabase_client, threshold_multiplier)

    if not check.is_spike:
        print(
            "No spike detected: "
            f"{check.current_volume} mentions vs {check.baseline_volume:.2f} baseline."
        )
        return check

    if alert_already_sent(supabase_client, check):
        print("Spike detected, but alert was already sent for this hourly window.")
        return check

    message = build_spike_message(check)
    if dry_run:
        print(message)
        return check

    send_telegram_message(telegram_bot_token, telegram_chat_id, message)
    record_alert_sent(supabase_client, check)
    print("Telegram spike alert sent.")
    return check


def run_scheduler(
    supabase_client,
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
            "supabase_client": supabase_client,
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

    try:
        supabase_client = get_supabase_client()
        telegram_config = require_env("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
    except ConfigError as error:
        raise SystemExit(str(error)) from error

    telegram_bot_token = telegram_config["TELEGRAM_BOT_TOKEN"]
    telegram_chat_id = telegram_config["TELEGRAM_CHAT_ID"]

    if args.once:
        check_and_send_alert(
            supabase_client=supabase_client,
            telegram_bot_token=telegram_bot_token,
            telegram_chat_id=telegram_chat_id,
            threshold_multiplier=args.threshold_multiplier,
            dry_run=args.dry_run,
        )
        return

    run_scheduler(
        supabase_client=supabase_client,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        threshold_multiplier=args.threshold_multiplier,
    )


if __name__ == "__main__":
    main()
