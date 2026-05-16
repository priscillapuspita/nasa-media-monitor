"""Streamlit dashboard for NASA media monitoring."""

from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from html import escape
from typing import Any
from urllib.parse import quote_plus

from config import ConfigError, get_supabase_client
from ingest_mentions import clean_text


NASA_BLUE = "#0b3d91"
NASA_RED = "#fc3d21"

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


def fetch_spike_alert_count(supabase_client, days: int = 7) -> int:
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    try:
        response = (
            supabase_client.table("alert_events")
            .select("id")
            .eq("alert_type", "mention_spike")
            .gte("sent_at", cutoff.isoformat())
            .execute()
        )
    except Exception:
        return 0

    return len(response.data or [])


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


def build_article_hover(rows: list[dict[str, Any]], limit: int = 8) -> str:
    links: list[str] = []

    for row in rows[:limit]:
        headline = escape(truncate_text(row.get("headline"), 70))
        url = escape(clean_text(row.get("url")))
        if url:
            links.append(f'<a href="{url}" target="_blank">{headline}</a>')
        elif headline:
            links.append(headline)

    if len(rows) > limit:
        links.append(f"+ {len(rows) - limit} more articles")

    return "<br>".join(links) if links else "No articles"


def build_daily_volume(
    rows: list[dict[str, Any]],
    days: int = 7,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    end_day = end_date or datetime.now(tz=timezone.utc).date()
    start_day = end_day - timedelta(days=days - 1)
    rows_by_day: dict[date, list[dict[str, Any]]] = {
        start_day + timedelta(days=offset): [] for offset in range(days)
    }

    for row in rows:
        published_at = parse_timestamp(row.get("published_at"))
        if not published_at:
            continue
        published_day = published_at.date()
        if start_day <= published_day <= end_day:
            rows_by_day[published_day].append(row)

    return [
        {
            "Date": date_value,
            "Mentions": len(day_rows),
            "Article links": build_article_hover(day_rows),
        }
        for date_value, day_rows in sorted(rows_by_day.items())
    ]


def truncate_text(value: str | None, max_chars: int = 80) -> str:
    text = clean_text(value)
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 3].rstrip()}..."


def build_article_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    articles: list[dict[str, Any]] = []

    for row in rows:
        published_at = parse_timestamp(row.get("published_at"))
        articles.append(
            {
                "Published date": format_timestamp(published_at),
                "Headline": truncate_text(row.get("headline"), 80),
                "Source": clean_source_name(row.get("source")),
                "Sentiment label": row.get("sentiment_label") or "unscored",
                "URL": row.get("url") or "",
                "_published_at": published_at or datetime.min.replace(tzinfo=timezone.utc),
            }
        )

    articles.sort(key=lambda article: article["_published_at"], reverse=True)
    for article in articles:
        article.pop("_published_at", None)
    return articles


def filter_rows_by_date_range(
    rows: list[dict[str, Any]],
    start_date: date,
    end_date: date,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []

    for row in rows:
        published_at = parse_timestamp(row.get("published_at"))
        if not published_at:
            continue
        published_day = published_at.date()
        if start_date <= published_day <= end_date:
            filtered.append(row)

    return filtered


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
                "source": clean_source_name(row.get("source")),
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


def inject_dashboard_styles(st) -> None:
    st.markdown(
        f"""
        <style>
            :root {{
                --nasa-blue: {NASA_BLUE};
                --nasa-red: {NASA_RED};
            }}

            .stApp {{
                background: #f7f9fc;
            }}

            section[data-testid="stSidebar"] {{
                border-right: 1px solid rgba(11, 61, 145, 0.12);
            }}

            .nasa-hero {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 1.5rem;
                padding: 1rem 0 1.35rem;
                border-bottom: 1px solid rgba(11, 61, 145, 0.14);
                margin-bottom: 1.2rem;
            }}

            .nasa-title-wrap {{
                display: flex;
                align-items: center;
                gap: 1rem;
            }}

            .nasa-logo-badge {{
                width: 64px;
                height: 64px;
                border-radius: 999px;
                background: radial-gradient(circle at 38% 35%, #1d5fc4 0 34%, var(--nasa-blue) 35% 100%);
                color: #ffffff;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 800;
                font-size: 0.92rem;
                letter-spacing: 0;
                box-shadow: 0 12px 26px rgba(11, 61, 145, 0.22);
                position: relative;
                flex: 0 0 auto;
            }}

            .nasa-logo-badge::after {{
                content: "";
                position: absolute;
                width: 76%;
                height: 2px;
                background: var(--nasa-red);
                transform: rotate(-23deg);
                border-radius: 999px;
            }}

            .nasa-logo-badge span {{
                position: relative;
                z-index: 1;
            }}

            .nasa-title {{
                color: #172033;
                font-size: 2rem;
                line-height: 1.1;
                font-weight: 760;
                margin: 0;
            }}

            .nasa-subtitle {{
                color: #526174;
                margin-top: 0.24rem;
                font-size: 1rem;
            }}

            .spike-counter {{
                min-width: 154px;
                border: 1px solid rgba(11, 61, 145, 0.18);
                border-left: 5px solid var(--nasa-red);
                border-radius: 8px;
                background: #ffffff;
                padding: 0.75rem 0.9rem;
                box-shadow: 0 10px 22px rgba(23, 32, 51, 0.06);
            }}

            .spike-counter-label {{
                color: #526174;
                font-size: 0.8rem;
                font-weight: 650;
                text-transform: uppercase;
                letter-spacing: 0;
            }}

            .spike-counter-value {{
                color: var(--nasa-blue);
                font-size: 1.65rem;
                line-height: 1;
                font-weight: 760;
                margin-top: 0.25rem;
            }}

            .metric-card {{
                border: 1px solid rgba(11, 61, 145, 0.14);
                border-left: 5px solid var(--nasa-blue);
                border-radius: 8px;
                background: #ffffff;
                padding: 0.85rem 1rem;
                box-shadow: 0 10px 24px rgba(23, 32, 51, 0.05);
            }}

            .metric-card.red {{
                border-left-color: var(--nasa-red);
            }}

            .metric-card-label {{
                color: #526174;
                font-size: 0.82rem;
                font-weight: 650;
                text-transform: uppercase;
                letter-spacing: 0;
            }}

            .metric-card-value {{
                color: #172033;
                font-size: 1.45rem;
                line-height: 1.2;
                font-weight: 750;
                margin-top: 0.35rem;
            }}

            .keyword-pill-wrap {{
                display: flex;
                flex-wrap: wrap;
                gap: 0.5rem;
                margin-top: 0.25rem;
            }}

            .keyword-pill {{
                display: inline-flex;
                align-items: center;
                gap: 0.35rem;
                background: rgba(11, 61, 145, 0.1);
                border: 1px solid rgba(11, 61, 145, 0.18);
                color: var(--nasa-blue);
                border-radius: 999px;
                padding: 0.34rem 0.62rem;
                font-weight: 680;
                font-size: 0.86rem;
                line-height: 1;
                text-decoration: none;
                transition: background 120ms ease, border-color 120ms ease;
            }}

            .keyword-pill:hover {{
                background: rgba(11, 61, 145, 0.16);
                border-color: rgba(11, 61, 145, 0.32);
                color: var(--nasa-blue);
                text-decoration: none;
            }}

            .keyword-pill-count {{
                color: #526174;
                font-weight: 650;
            }}

            div[data-testid="stMetric"] {{
                background: transparent;
            }}

            h1, h2, h3 {{
                color: #172033;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(st, spike_alert_count: int) -> None:
    st.markdown(
        f"""
        <div class="nasa-hero">
            <div class="nasa-title-wrap">
                <div class="nasa-logo-badge"><span>NASA</span></div>
                <div>
                    <h1 class="nasa-title">NASA Media Monitor</h1>
                    <div class="nasa-subtitle">Mission coverage intelligence</div>
                </div>
            </div>
            <div class="spike-counter">
                <div class="spike-counter-label">Spike alerts</div>
                <div class="spike-counter-value">{spike_alert_count:,}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(st, label: str, value: str, accent: str = "blue") -> None:
    accent_class = " red" if accent == "red" else ""
    st.markdown(
        f"""
        <div class="metric-card{accent_class}">
            <div class="metric-card-label">{escape(label)}</div>
            <div class="metric-card-value">{escape(value)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_keyword_pill_html(keywords: list[tuple[str, int]]) -> str:
    pills: list[str] = []
    for keyword, count in keywords:
        safe_keyword = escape(keyword)
        query = quote_plus(f"NASA {keyword} news")
        pills.append(
            '<a class="keyword-pill" '
            f'href="https://www.google.com/search?q={query}" '
            'target="_blank" rel="noopener noreferrer">'
            f"{safe_keyword} "
            f'<span class="keyword-pill-count">{count}</span>'
            "</a>"
        )
    return f'<div class="keyword-pill-wrap">{"".join(pills)}</div>'


def render_keyword_pills(st, keywords: list[tuple[str, int]]) -> None:
    st.markdown(build_keyword_pill_html(keywords), unsafe_allow_html=True)


def render_dashboard() -> None:
    import pandas as pd
    import plotly.express as px
    import streamlit as st

    st.set_page_config(page_title="NASA Media Monitor", layout="wide")
    inject_dashboard_styles(st)

    with st.sidebar:
        st.header("Filters")
        days = st.slider("Lookback window", min_value=1, max_value=90, value=30)
        limit = st.slider("Rows to load", min_value=100, max_value=5000, value=1000, step=100)
        refresh = st.button("Refresh data")

    try:
        database_client = get_database_client()
        rows = fetch_rows(database_client, days=days, limit=limit)
        spike_alert_count = fetch_spike_alert_count(database_client)
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

    render_header(st, spike_alert_count)

    metric_a, metric_b, metric_c = st.columns(3)
    with metric_a:
        render_metric_card(st, "Mentions", f"{total_mentions:,}")
    with metric_b:
        render_metric_card(st, "Scored mentions", f"{scored_mentions:,}")
    with metric_c:
        render_metric_card(
            st,
            "Latest mention",
            format_timestamp(latest_timestamp.to_pydatetime() if pd.notna(latest_timestamp) else None),
            accent="red",
        )

    chart_left, chart_right = st.columns([2, 1])

    daily_records = build_daily_volume(rows)
    daily_volume = pd.DataFrame(daily_records)
    with chart_left:
        st.subheader("Daily Mention Volume")
        if daily_volume.empty:
            st.info("No dated mentions available for the selected window.")
        else:
            y_max = max(int(daily_volume["Mentions"].max()), 1)
            fig = px.line(
                daily_volume,
                x="Date",
                y="Mentions",
                markers=True,
                labels={"Date": "Date", "Mentions": "Number of mentions"},
            )
            fig.update_traces(
                customdata=daily_volume[["Article links"]],
                line=dict(color=NASA_BLUE, width=3),
                marker=dict(color=NASA_BLUE, size=8),
                hovertemplate=(
                    "<b>%{x|%Y-%m-%d}</b><br>"
                    "Number of mentions: %{y}<br><br>"
                    "%{customdata[0]}<extra></extra>"
                ),
                mode="lines+markers",
            )
            fig.update_xaxes(tickformat="%Y-%m-%d", title_text="Date")
            fig.update_yaxes(
                range=[0, y_max + 1],
                rangemode="tozero",
                title_text="Number of mentions",
                gridcolor="rgba(11, 61, 145, 0.08)",
            )
            fig.update_layout(
                margin=dict(t=10, b=10, l=10, r=10),
                plot_bgcolor="#ffffff",
                paper_bgcolor="#ffffff",
                hoverlabel=dict(bgcolor="#ffffff", font_color="#172033"),
            )
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Articles")
        date_options = [record["Date"] for record in daily_records]
        if date_options:
            selected_dates = st.date_input(
                "Filter articles by date",
                value=(date_options[0], date_options[-1]),
                min_value=date_options[0],
                max_value=date_options[-1],
            )
            if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
                table_start_date, table_end_date = selected_dates
            elif isinstance(selected_dates, tuple) and len(selected_dates) == 1:
                table_start_date = table_end_date = selected_dates[0]
            elif isinstance(selected_dates, tuple):
                table_start_date, table_end_date = date_options[0], date_options[-1]
            else:
                table_start_date = table_end_date = selected_dates
            table_rows = filter_rows_by_date_range(rows, table_start_date, table_end_date)
        else:
            table_rows = rows

        articles = build_article_table(table_rows)
        if not articles:
            st.info("No articles available for the selected window.")
        else:
            st.dataframe(
                pd.DataFrame(articles),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "URL": st.column_config.LinkColumn(
                        "URL",
                        display_text="Open article",
                    )
                },
            )

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
            render_keyword_pills(st, keywords)

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
