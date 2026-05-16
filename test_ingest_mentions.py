import unittest
from datetime import timezone

from ingest_mentions import clean_text, is_relevant_mention, parse_datetime, parse_unix_datetime


class IngestMentionsTest(unittest.TestCase):
    def test_clean_text_normalizes_html_and_whitespace(self):
        raw = " NASA&nbsp;<strong>Artemis</strong>\n\ncoverage "

        self.assertEqual(clean_text(raw), "NASA Artemis coverage")

    def test_parse_datetime_handles_newsapi_utc_value(self):
        parsed = parse_datetime("2026-05-11T10:15:30Z")

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.isoformat(), "2026-05-11T10:15:30+00:00")

    def test_parse_unix_datetime_returns_utc_value(self):
        parsed = parse_unix_datetime(0)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.tzinfo, timezone.utc)
        self.assertEqual(parsed.isoformat(), "1970-01-01T00:00:00+00:00")

    def test_is_relevant_mention_allows_core_space_terms(self):
        self.assertTrue(is_relevant_mention("NASA confirms Artemis launch", "Mission update"))
        self.assertTrue(is_relevant_mention("Telescope news", "James Webb detects a galaxy"))
        self.assertTrue(is_relevant_mention("JPL shares rover update", ""))
        self.assertTrue(is_relevant_mention("Budget update", "Space agency requests funding"))

    def test_is_relevant_mention_rejects_unrelated_articles(self):
        self.assertFalse(is_relevant_mention("Apple Cider Vinegar benefits", "Kitchen guide"))
        self.assertFalse(is_relevant_mention("Mother's Day gifts", "Shopping roundup"))
        self.assertFalse(is_relevant_mention("Zodiac signs forecast", "Lifestyle article"))


if __name__ == "__main__":
    unittest.main()
