"""Analyze mention sentiment with cardiffnlp/twitter-roberta-base-sentiment."""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

from config import ConfigError, get_supabase_client, require_config_value
from ingest_mentions import clean_text


MODEL_NAME = "cardiffnlp/twitter-roberta-base-sentiment-latest"
INFERENCE_API_URL = f"https://router.huggingface.co/hf-inference/models/{MODEL_NAME}"
LABEL_MAP = {
    "LABEL_0": "negative",
    "LABEL_1": "neutral",
    "LABEL_2": "positive",
    "negative": "negative",
    "neutral": "neutral",
    "positive": "positive",
}


@dataclass(frozen=True)
class MentionForSentiment:
    id: int
    headline: str
    raw_text: str | None


@dataclass(frozen=True)
class SentimentResult:
    mention_id: int
    label: str
    confidence: float
    analyzed_at: datetime


class HuggingFaceSentimentClient:
    def __init__(
        self,
        api_token: str,
        api_url: str = INFERENCE_API_URL,
        timeout_seconds: int = 60,
        max_retries: int = 3,
    ) -> None:
        self.api_url = api_url
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.headers = {"Authorization": f"Bearer {api_token}"}

    def analyze_batch(self, texts: list[str]) -> list[list[dict[str, Any]]]:
        payload = {
            "inputs": texts,
            "options": {"wait_for_model": True},
        }

        for attempt in range(self.max_retries):
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=self.timeout_seconds,
            )
            if response.status_code == 503 and attempt < self.max_retries - 1:
                wait_seconds = min(2**attempt, 8)
                time.sleep(wait_seconds)
                continue

            if response.status_code in {403, 404}:
                print(
                    "HuggingFace API unavailable for sentiment scoring "
                    f"({response.status_code}); using local fallback scorer."
                )
                return [fallback_sentiment_scores(text) for text in texts]

            response.raise_for_status()
            return normalize_api_response(response.json())

        raise RuntimeError("HuggingFace Inference API did not return a usable response.")


def build_sentiment_text(headline: str, raw_text: str | None, max_chars: int = 1800) -> str:
    parts = [clean_text(headline), clean_text(raw_text)]
    text = clean_text(". ".join(part for part in parts if part))
    return text[:max_chars]


def normalize_model_label(label: str) -> str:
    normalized = LABEL_MAP.get(label)
    if not normalized:
        raise ValueError(f"Unsupported sentiment label from model: {label}")
    return normalized


def fallback_sentiment_scores(text: str) -> list[dict[str, Any]]:
    positive_words = {
        "achieve",
        "advance",
        "award",
        "breakthrough",
        "discover",
        "discovery",
        "excellent",
        "first",
        "historic",
        "innovation",
        "launch",
        "launched",
        "mission",
        "new",
        "success",
        "successful",
        "support",
    }
    negative_words = {
        "accident",
        "alarm",
        "bad",
        "cancel",
        "concern",
        "crash",
        "crisis",
        "delay",
        "delayed",
        "fail",
        "failed",
        "failure",
        "risk",
        "problem",
        "threat",
        "warning",
    }
    words = {word.strip(".,:;!?()[]{}\"'").lower() for word in text.split()}
    positive_count = len(words & positive_words)
    negative_count = len(words & negative_words)

    if positive_count > negative_count:
        return [
            {"label": "positive", "score": 0.7},
            {"label": "neutral", "score": 0.2},
            {"label": "negative", "score": 0.1},
        ]
    if negative_count > positive_count:
        return [
            {"label": "negative", "score": 0.7},
            {"label": "neutral", "score": 0.2},
            {"label": "positive", "score": 0.1},
        ]
    return [
        {"label": "neutral", "score": 0.6},
        {"label": "positive", "score": 0.2},
        {"label": "negative", "score": 0.2},
    ]


def normalize_api_response(payload: Any) -> list[list[dict[str, Any]]]:
    if isinstance(payload, dict) and payload.get("error"):
        raise RuntimeError(f"HuggingFace Inference API error: {payload['error']}")

    if not isinstance(payload, list):
        raise RuntimeError(f"Unexpected HuggingFace response: {payload}")

    if not payload:
        return []

    if all(isinstance(item, dict) for item in payload):
        return [payload]

    normalized: list[list[dict[str, Any]]] = []
    for item in payload:
        if isinstance(item, list):
            normalized.append(item)
        elif isinstance(item, dict):
            normalized.append([item])
        else:
            raise RuntimeError(f"Unexpected HuggingFace response item: {item}")

    return normalized


def pick_best_sentiment(model_output: list[dict[str, Any]]) -> tuple[str, float]:
    if not model_output:
        raise ValueError("Model returned no sentiment scores.")

    best = max(model_output, key=lambda row: row["score"])
    return normalize_model_label(best["label"]), round(float(best["score"]), 4)


def analyze_mentions(
    mentions: list[MentionForSentiment],
    sentiment_client: HuggingFaceSentimentClient,
    batch_size: int,
) -> list[SentimentResult]:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1.")

    if not mentions:
        return []

    texts = [build_sentiment_text(mention.headline, mention.raw_text) for mention in mentions]
    analyzed_at = datetime.now(tz=timezone.utc)
    results: list[SentimentResult] = []

    for start in range(0, len(texts), batch_size):
        batch_mentions = mentions[start : start + batch_size]
        batch_texts = texts[start : start + batch_size]
        batch_outputs = sentiment_client.analyze_batch(batch_texts)

        for mention, output in zip(batch_mentions, batch_outputs):
            label, confidence = pick_best_sentiment(output)
            results.append(
                SentimentResult(
                    mention_id=mention.id,
                    label=label,
                    confidence=confidence,
                    analyzed_at=analyzed_at,
                )
            )

    return results


def fetch_mentions_for_analysis(
    supabase_client,
    limit: int,
    force: bool,
) -> list[MentionForSentiment]:
    query = (
        supabase_client.table("mentions")
        .select("id, headline, raw_text")
        .order("published_at", desc=True, nullsfirst=False)
        .order("id", desc=True)
        .limit(limit)
    )
    if not force:
        query = query.is_("sentiment_label", "null")

    rows = query.execute().data

    return [
        MentionForSentiment(
            id=row["id"],
            headline=row["headline"],
            raw_text=row["raw_text"],
        )
        for row in rows
    ]


def store_sentiment_results(supabase_client, results: list[SentimentResult]) -> int:
    if not results:
        return 0

    for result in results:
        supabase_client.table("mentions").update(
            {
                "sentiment_label": result.label,
                "sentiment_confidence": result.confidence,
                "sentiment_analyzed_at": result.analyzed_at.isoformat(),
            }
        ).eq("id", result.mention_id).execute()

    return len(results)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze sentiment for stored mentions.")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess rows even if they already have sentiment labels.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.limit < 1:
        raise SystemExit("--limit must be at least 1.")
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be at least 1.")

    try:
        supabase_client = get_supabase_client()
        huggingface_api_token = require_config_value("HUGGINGFACE_API_TOKEN")
    except ConfigError as error:
        raise SystemExit(str(error)) from error

    mentions = fetch_mentions_for_analysis(supabase_client, args.limit, args.force)
    if not mentions:
        print("No mentions need sentiment analysis.")
        return

    sentiment_client = HuggingFaceSentimentClient(huggingface_api_token)
    results = analyze_mentions(mentions, sentiment_client, args.batch_size)
    stored_count = store_sentiment_results(supabase_client, results)
    print(f"Analyzed and updated {stored_count} mentions.")


if __name__ == "__main__":
    main()
