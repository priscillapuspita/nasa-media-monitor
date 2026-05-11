"""Fetch NASA media mentions from NewsAPI and Reddit, then store them in PostgreSQL."""

from __future__ import annotations

import argparse
import html
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from config import (
    DATABASE_URL,
    MENTION_QUERY,
    NEWSAPI_KEY,
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
)


NEWSAPI_ENDPOINT = "https://newsapi.org/v2/everything"
REDDIT_TOKEN_ENDPOINT = "https://www.reddit.com/api/v1/access_token"
REDDIT_SEARCH_ENDPOINT = "https://oauth.reddit.com/search"


@dataclass(frozen=True)
class Mention:
    source: str
    headline: str
    url: str
    published_at: datetime | None
    raw_text: str


def clean_text(value: str | None) -> str:
    """Normalize API text into a compact plain-text string."""
    if not value:
        return ""

    text = html.unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def parse_unix_datetime(value: int | float | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc)


def get_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    request = Request(url, headers=headers or {})
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Request failed with HTTP {error.code}: {details}") from error
    except URLError as error:
        raise RuntimeError(f"Request failed: {error.reason}") from error


def post_form_json(
    url: str,
    form: dict[str, str],
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    encoded_form = urlencode(form).encode("utf-8")
    request = Request(url, data=encoded_form, headers=headers or {}, method="POST")
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Request failed with HTTP {error.code}: {details}") from error
    except URLError as error:
        raise RuntimeError(f"Request failed: {error.reason}") from error


def fetch_newsapi_mentions(query: str, page_size: int) -> list[Mention]:
    params = {
        "q": query,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": str(page_size),
        "apiKey": NEWSAPI_KEY,
    }
    payload = get_json(f"{NEWSAPI_ENDPOINT}?{urlencode(params)}")
    articles = payload.get("articles", [])

    mentions: list[Mention] = []
    for article in articles:
        title = clean_text(article.get("title"))
        url = clean_text(article.get("url"))
        description = clean_text(article.get("description"))
        content = clean_text(article.get("content"))
        source_name = clean_text((article.get("source") or {}).get("name"))

        if not title or not url:
            continue

        mentions.append(
            Mention(
                source=f"NewsAPI: {source_name or 'Unknown'}",
                headline=title,
                url=url,
                published_at=parse_datetime(article.get("publishedAt")),
                raw_text=clean_text(" ".join(part for part in [description, content] if part)),
            )
        )

    return mentions


def get_reddit_access_token() -> str | None:
    credentials = f"{REDDIT_CLIENT_ID}:{REDDIT_CLIENT_SECRET}".encode("utf-8")
    import base64

    encoded_credentials = base64.b64encode(credentials).decode("ascii")
    payload = post_form_json(
        REDDIT_TOKEN_ENDPOINT,
        {"grant_type": "client_credentials"},
        {
            "Authorization": f"Basic {encoded_credentials}",
            "User-Agent": REDDIT_USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    return payload.get("access_token")


def fetch_reddit_mentions(query: str, limit: int) -> list[Mention]:
    access_token = get_reddit_access_token()
    if not access_token:
        return []

    params = {
        "q": query,
        "sort": "new",
        "limit": str(limit),
        "type": "link",
    }
    payload = get_json(
        f"{REDDIT_SEARCH_ENDPOINT}?{urlencode(params)}",
        {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": REDDIT_USER_AGENT,
        },
    )

    mentions: list[Mention] = []
    for item in payload.get("data", {}).get("children", []):
        post = item.get("data", {})
        title = clean_text(post.get("title"))
        permalink = clean_text(post.get("permalink"))
        raw_text = clean_text(post.get("selftext"))
        subreddit = clean_text(post.get("subreddit_name_prefixed"))

        if not title or not permalink:
            continue

        mentions.append(
            Mention(
                source=f"Reddit: {subreddit or 'Unknown'}",
                headline=title,
                url=f"https://www.reddit.com{permalink}",
                published_at=parse_unix_datetime(post.get("created_utc")),
                raw_text=raw_text,
            )
        )

    return mentions


def store_mentions(database_url: str, mentions: list[Mention]) -> int:
    import psycopg

    if not mentions:
        return 0

    sql = """
        INSERT INTO mentions (source, headline, url, published_at, raw_text)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (url) DO UPDATE SET
            source = EXCLUDED.source,
            headline = EXCLUDED.headline,
            published_at = EXCLUDED.published_at,
            raw_text = EXCLUDED.raw_text
    """

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.executemany(
                sql,
                [
                    (
                        mention.source,
                        mention.headline,
                        mention.url,
                        mention.published_at,
                        mention.raw_text,
                    )
                    for mention in mentions
                ],
            )
        connection.commit()

    return len(mentions)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest NASA media mentions.")
    parser.add_argument("--query", default=MENTION_QUERY)
    parser.add_argument("--news-limit", type=int, default=50)
    parser.add_argument("--reddit-limit", type=int, default=50)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    newsapi_mentions = fetch_newsapi_mentions(args.query, args.news_limit)
    reddit_mentions = fetch_reddit_mentions(args.query, args.reddit_limit)
    mentions = newsapi_mentions + reddit_mentions

    stored_count = store_mentions(DATABASE_URL, mentions)
    print(
        f"Fetched {len(newsapi_mentions)} NewsAPI mentions, "
        f"{len(reddit_mentions)} Reddit mentions, stored {stored_count} records."
    )


if __name__ == "__main__":
    main()
