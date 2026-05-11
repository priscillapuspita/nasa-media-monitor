import unittest
from datetime import datetime, timezone

from streamlit_dashboard import build_alerts, extract_trending_keywords, format_timestamp


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

    def test_format_timestamp_handles_missing_values(self):
        self.assertEqual(format_timestamp(None), "No date")


if __name__ == "__main__":
    unittest.main()
