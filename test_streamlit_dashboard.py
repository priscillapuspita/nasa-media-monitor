import unittest
from datetime import date, datetime, timezone

import pandas as pd

from streamlit_dashboard import (
    build_alerts,
    build_article_table,
    build_daily_volume,
    build_keyword_pill_html,
    build_sentiment_summary,
    build_top_sources,
    clean_source_name,
    extract_trending_keywords,
    filter_rows_by_date_range,
    format_timestamp,
    truncate_text,
)


class StreamlitDashboardTest(unittest.TestCase):
    def test_extract_trending_keywords_counts_cleaned_terms(self):
        rows = [
            {"headline": "NASA Artemis launch update", "raw_text": "Artemis mission mission"},
            {"headline": "James Webb observes galaxy", "raw_text": "NASA science mission"},
        ]

        keywords = dict(extract_trending_keywords(rows, limit=5))

        self.assertEqual(keywords["mission"], 3)
        self.assertEqual(keywords["artemis"], 2)
        self.assertNotIn("nasa", keywords)

    def test_extract_trending_keywords_filters_common_stopwords(self):
        rows = [
            {
                "headline": "NASA said the mission will continue",
                "raw_text": "chars for the them and that with this from have been will are its was but not you all can her his they our said telescope telescope",
            }
        ]

        keywords = dict(extract_trending_keywords(rows, limit=10))

        self.assertEqual(keywords["telescope"], 2)
        for stopword in [
            "chars",
            "for",
            "the",
            "them",
            "and",
            "that",
            "with",
            "this",
            "from",
            "have",
            "been",
            "will",
            "are",
            "its",
            "was",
            "but",
            "not",
            "you",
            "all",
            "can",
            "her",
            "his",
            "they",
            "our",
            "said",
        ]:
            self.assertNotIn(stopword, keywords)

    def test_build_keyword_pill_html_uses_clickable_links(self):
        html = build_keyword_pill_html([("artemis", 3), ("james webb", 2)])

        self.assertIn('class="keyword-pill"', html)
        self.assertIn("artemis", html)
        self.assertIn("3", html)
        self.assertIn("https://www.google.com/search?q=NASA+artemis+news", html)
        self.assertIn("NASA+james+webb+news", html)

    def test_build_sentiment_summary_formats_percentages(self):
        counts = pd.DataFrame(
            [
                {"sentiment_label": "positive", "size": 40},
                {"sentiment_label": "neutral", "size": 55},
                {"sentiment_label": "negative", "size": 4},
                {"sentiment_label": "unscored", "size": 1},
            ]
        )

        summary = build_sentiment_summary(counts)

        self.assertEqual(
            summary,
            "<strong>Positive</strong> 40% / <strong>Neutral</strong> 55% / <strong>Negative</strong> 4%",
        )

    def test_build_alerts_includes_high_confidence_negative_mentions(self):
        rows = [
            {
                "headline": "NASA story",
                "source": "NewsAPI: Example",
                "url": "https://example.com",
                "published_at": datetime(2026, 5, 11, tzinfo=timezone.utc),
                "sentiment_label": "negative",
                "sentiment_confidence": 0.91,
            }
        ]

        alerts = build_alerts(rows)

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["severity"], "Negative coverage")
        self.assertEqual(alerts[0]["source"], "Example")

    def test_clean_source_name_removes_newsapi_prefix(self):
        self.assertEqual(clean_source_name("NewsAPI: Slashdot"), "Slashdot")
        self.assertEqual(clean_source_name("NewsAPI: New York Times"), "New York Times")

    def test_build_top_sources_counts_and_uses_latest_article(self):
        rows = [
            {
                "source": "NewsAPI: Slashdot",
                "url": "https://example.com/old",
                "published_at": "2026-05-10T10:00:00+00:00",
            },
            {
                "source": "NewsAPI: Slashdot",
                "url": "https://example.com/new",
                "published_at": "2026-05-11T10:00:00+00:00",
            },
            {
                "source": "NewsAPI: New York Times",
                "url": "https://example.com/nyt",
                "published_at": "2026-05-11T09:00:00+00:00",
            },
        ]

        sources = build_top_sources(rows)

        self.assertEqual(sources[0]["Source"], "Slashdot")
        self.assertEqual(sources[0]["Mentions"], 2)
        self.assertEqual(sources[0]["Latest Article"], "https://example.com/new")
        self.assertEqual(sources[1]["Source"], "New York Times")

    def test_build_daily_volume_groups_by_date(self):
        rows = [
            {
                "published_at": "2026-05-11T09:00:00+00:00",
                "headline": "NASA link one",
                "url": "https://example.com/one",
            },
            {
                "published_at": "2026-05-11T17:30:00+00:00",
                "headline": "NASA link two",
                "url": "https://example.com/two",
            },
            {
                "published_at": "2026-05-12T01:00:00+00:00",
                "headline": "NASA link three",
                "url": "https://example.com/three",
            },
            {"published_at": None},
        ]

        volume = build_daily_volume(rows, end_date=date(2026, 5, 12))

        self.assertEqual(len(volume), 7)
        self.assertEqual(volume[-2]["Date"], date(2026, 5, 11))
        self.assertEqual(volume[-2]["Mentions"], 2)
        self.assertIn("NASA link one", volume[-2]["Article links"])
        self.assertIn("https://example.com/one", volume[-2]["Article links"])
        self.assertEqual(volume[-1]["Date"], date(2026, 5, 12))
        self.assertEqual(volume[-1]["Mentions"], 1)

    def test_filter_rows_by_date_range_keeps_selected_dates(self):
        rows = [
            {"published_at": "2026-05-10T09:00:00+00:00"},
            {"published_at": "2026-05-11T17:30:00+00:00"},
            {"published_at": "2026-05-12T01:00:00+00:00"},
            {"published_at": None},
        ]

        filtered = filter_rows_by_date_range(rows, date(2026, 5, 11), date(2026, 5, 12))

        self.assertEqual(len(filtered), 2)

    def test_build_article_table_formats_articles_for_display(self):
        long_headline = "A" * 90
        rows = [
            {
                "published_at": "2026-05-11T09:00:00+00:00",
                "headline": long_headline,
                "source": "NewsAPI: Slashdot",
                "sentiment_label": "neutral",
                "url": "https://example.com/article",
            }
        ]

        articles = build_article_table(rows)

        self.assertEqual(articles[0]["Published date"], "2026-05-11 09:00")
        self.assertEqual(len(articles[0]["Headline"]), 80)
        self.assertTrue(articles[0]["Headline"].endswith("..."))
        self.assertEqual(articles[0]["Source"], "Slashdot")
        self.assertEqual(articles[0]["Sentiment label"], "neutral")
        self.assertEqual(articles[0]["URL"], "https://example.com/article")

    def test_truncate_text_keeps_short_text_unchanged(self):
        self.assertEqual(truncate_text("Short headline", 80), "Short headline")

    def test_format_timestamp_handles_missing_values(self):
        self.assertEqual(format_timestamp(None), "No date")


if __name__ == "__main__":
    unittest.main()
