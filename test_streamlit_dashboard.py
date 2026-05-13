import unittest
from datetime import datetime, timezone

from streamlit_dashboard import (
    build_alerts,
    build_top_sources,
    clean_source_name,
    extract_trending_keywords,
    format_timestamp,
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

    def test_format_timestamp_handles_missing_values(self):
        self.assertEqual(format_timestamp(None), "No date")


if __name__ == "__main__":
    unittest.main()
