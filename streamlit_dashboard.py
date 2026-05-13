"""Streamlit dashboard for NASA media monitoring."""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from config import ConfigError, get_supabase_client
from ingest_mentions import clean_text


STOPWORDS = {
    "about",
    "after",
    "again",
    "against",
    "all",
    "also",
    "and",
    "are",
    "around",
    "because",
    "been",
    "before",
    "being",
    "but",
    "can",
    "chars",
    "could",
    "for",
    "from",
    "had",
    "has",
    "have",
    "her",
    "his",
    "into",
    "its",
    "more",
    "new",
    "not",
    "nasa",
    "over",
    "said",
    "says",
    "than",
    "that",
    "the",
    "their",
    "them",
    "they",
    "this",
    "through",
    "our",
    "was",
    "were",
    "when",
    "where",
    "will",
    "with",
    "would",
    "you",
    "your",
}


def get_database_client():
    try:
        return get_supabase_client()
    except ConfigError as error:
        raise RuntimeError(str(error)) from error


def parse_timestamp(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def fetch_rows(supabase_client, days: int, limit: int) -> list[dict[str, Any]]:
    response = (
        supabase_client.table("mentions")
        .select(
            "id, source, headline, url, published_at, raw_text, "
            "sentiment_label, sentiment_confidence, sentiment_analyzed_at"
        )
        .order("published_at", desc=True, nullsfirst=False)
        .order("id", desc=True)
        .limit(limit)
        .execute()
    )
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    rows: list[dict[str, Any]] = []
    for row in response.data:
        published_at = parse_timestamp(row.get("published_at"))
        if published_at is not None and published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        if published_at is None or published_at >= cutoff:
            rows.append(row)
    return rows


def extract_trending_keywords(rows: list[dict[str, Any]], limit: int = 15) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()

    for row in rows:
        text = clean_text(f"{row.get('headline') or ''} {row.get('raw_text') or ''}")
        words = re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}", text.lower())
        counter.update(word for word in words if word not in STOPWORDS)

    return counter.most_common(limit)


def clean_source_name(source: str | None) -> str:
    cleaned = clean_text(source)
    if cleaned.lower().startswith("newsapi:"):
        cleaned = cleaned.split(":", 1)[1].strip()
    return cleaned or "Unknown source"


def build_top_sources(rows: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}

    for row in rows:
        source_name = clean_source_name(row.get("source"))
        published_at = parse_timestamp(row.get("published_at"))
        existing = sources.get(source_name)

        if not existing:
            sources[source_name] = {
                "Source": source_name,
                "Mentions": 1,
                "Latest Article": row.get("url") or "",
                "_latest_at": published_at,
            }
            continue

        existing["Mentions"] += 1
        existing_latest = existing.get("_latest_at")
        if published_at and (not existing_latest or published_at > existing_latest):
            existing["Latest Article"] = row.get("url") or existing["Latest Article"]
            existing["_latest_at"] = published_at

    sorted_sources = sorted(
        sources.values(),
        key=lambda item: (item["Mentions"], item.get("_latest_at") or datetime.min),
        reverse=True,
    )
    return [
        {
            "Source": item["Source"],
            "Mentions": item["Mentions"],
            "Latest Article": item["Latest Article"],
        }
        for item in sorted_sources[:limit]
    ]


def build_daily_volume(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[Any] = Counter()

    for row in rows:
        published_at = parse_timestamp(row.get("published_at"))
        if not published_at:
            continue
        counter[published_at.date()] += 1

    return [
        {"Date": date_value, "Mentions": count}
        for date_value, count in sorted(counter.items())
    ]


def build_alerts(rows: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []

    for row in rows:
        sentiment = row.get("sentiment_label")
        confidence = float(row.get("sentiment_confidence") or 0)

        if sentiment == "negative" and confidence >= 0.6:
            severity = "Negative coverage"
        elif sentiment == "positive" and confidence >= 0.85:
            severity = "High-confidence positive"
        elif row.get("published_at") is None:
            severity = "Undated mention"
        else:
            continue

        alerts.append(
            {
                "severity": severity,
                "headline": row.get("headline") or "Untitled mention",
                "source": row.get("source") or "Unknown source",
                "url": row.get("url"),
                "published_at": row.get("published_at"),
                "sentiment_label": sentiment or "unscored",
                "sentiment_confidence": confidence,
            }
        )

    return alerts[:limit]


def format_timestamp(value: Any) -> str:
    if not value:
        return "No date"
    if isinstance(value, datetime):
        display_value = value
        if not display_value.tzinfo:
            display_value = display_value.replace(tzinfo=timezone.utc)
        return display_value.strftime("%Y-%m-%d %H:%M")
    return str(value)


def render_dashboard() -> None:
    import pandas as pd
    import plotly.express as px
    import streamlit as st

    st.set_page_config(page_title="NASA Media Monitor", layout="wide")
    st.title("NASA Media Monitor")

    with st.sidebar:
        st.header("Filters")
        days = st.slider("Lookback window", min_value=1, max_value=90, value=30)
        limit = st.slider("Rows to load", min_value=100, max_value=5000, value=1000, step=100)
        refresh = st.button("Refresh data")

    try:
        rows = fetch_rows(get_database_client(), days=days, limit=limit)
    except Exception as error:
        st.error(f"Could not load dashboard data: {error}")
        st.stop()

    if refresh:
        st.cache_data.clear()

    if not rows:
        st.info("No mentions found yet. Run `python ingest_mentions.py` first.")
        st.stop()

    df = pd.DataFrame(rows)
    df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce", utc=True)
    df["sentiment_label"] = df["sentiment_label"].fillna("unscored")
    df["sentiment_confidence"] = pd.to_numeric(df["sentiment_confidence"], errors="coerce")

    total_mentions = len(df)
    scored_mentions = int(df["sentiment_confidence"].notna().sum())
    latest_timestamp = df["published_at"].dropna().max()

    metric_a, metric_b, metric_c = st.columns(3)
    metric_a.metric("Mentions", f"{total_mentions:,}")
    metric_b.metric("Scored mentions", f"{scored_mentions:,}")
    metric_c.metric("Latest mention", format_timestamp(latest_timestamp.to_pydatetime() if pd.notna(latest_timestamp) else None))

    chart_left, chart_right = st.columns([2, 1])

    daily_volume = pd.DataFrame(build_daily_volume(rows))
    with chart_left:
        st.subheader("Daily Mention Volume")
        if daily_volume.empty:
            st.info("No dated mentions available for the selected window.")
        else:
            y_max = max(int(daily_volume["Mentions"].max()), 1)
            fig = px.bar(
                daily_volume,
                x="Date",
                y="Mentions",
                labels={"Date": "Date", "Mentions": "Mentions"},
            )
            fig.update_yaxes(range=[0, y_max + 1], rangemode="tozero")
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)

    sentiment_counts = df.groupby("sentiment_label", as_index=False).size()
    with chart_right:
        st.subheader("Sentiment")
        fig = px.pie(
            sentiment_counts,
            values="size",
            names="sentiment_label",
            hole=0.55,
            color="sentiment_label",
            color_discrete_map={
                "positive": "#2E7D32",
                "neutral": "#546E7A",
                "negative": "#C62828",
                "unscored": "#9E9E9E",
            },
        )
        fig.update_layout(showlegend=True, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top Sources")
    top_sources = build_top_sources(rows)
    if not top_sources:
        st.info("No source data available yet.")
    else:
        source_df = pd.DataFrame(top_sources)
        st.dataframe(
            source_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Latest Article": st.column_config.LinkColumn(
                    "Latest Article",
                    display_text="Open article",
                )
            },
        )

    lower_left, lower_right = st.columns([1, 2])

    with lower_left:
        st.subheader("Trending Keywords")
        keywords = extract_trending_keywords(rows)
        if not keywords:
            st.info("No keywords available yet.")
        else:
            keyword_df = pd.DataFrame(keywords, columns=["keyword", "mentions"])
            st.dataframe(keyword_df, use_container_width=True, hide_index=True)

    with lower_right:
        st.subheader("Live Alert Feed")
        alerts = build_alerts(rows)
        if not alerts:
            st.info("No active alerts in the selected window.")
        else:
            for alert in alerts:
                label = alert["sentiment_label"]
                confidence = alert["sentiment_confidence"]
                st.markdown(
                    f"**{alert['severity']}** · {alert['source']} · "
                    f"{format_timestamp(alert['published_at'])} · {label} {confidence:.2f}"
                )
                if alert.get("url"):
                    st.markdown(f"[{alert['headline']}]({alert['url']})")
                else:
                    st.write(alert["headline"])
                st.divider()


if __name__ == "__main__":
    render_dashboard()
