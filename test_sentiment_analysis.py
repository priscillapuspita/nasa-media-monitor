import unittest

from sentiment_analysis import (
    MentionForSentiment,
    analyze_mentions,
    build_sentiment_text,
    normalize_model_label,
    normalize_api_response,
    pick_best_sentiment,
)


class FakeSentimentClient:
    def analyze_batch(self, texts):
        return [
            [
                {"label": "LABEL_0", "score": 0.05},
                {"label": "LABEL_1", "score": 0.9},
                {"label": "LABEL_2", "score": 0.05},
            ]
            for _ in texts
        ]


class SentimentAnalysisTest(unittest.TestCase):
    def test_normalize_model_label_maps_cardiff_labels(self):
        self.assertEqual(normalize_model_label("LABEL_0"), "negative")
        self.assertEqual(normalize_model_label("LABEL_1"), "neutral")
        self.assertEqual(normalize_model_label("LABEL_2"), "positive")

    def test_pick_best_sentiment_uses_highest_score(self):
        label, confidence = pick_best_sentiment(
            [
                {"label": "LABEL_0", "score": 0.1},
                {"label": "LABEL_1", "score": 0.2},
                {"label": "LABEL_2", "score": 0.70456},
            ]
        )

        self.assertEqual(label, "positive")
        self.assertEqual(confidence, 0.7046)

    def test_build_sentiment_text_combines_headline_and_raw_text(self):
        text = build_sentiment_text(" NASA <b>launch</b> ", " Artemis&nbsp;coverage ")

        self.assertEqual(text, "NASA launch. Artemis coverage")

    def test_normalize_api_response_handles_single_input_shape(self):
        payload = [
            {"label": "LABEL_0", "score": 0.05},
            {"label": "LABEL_1", "score": 0.9},
        ]

        self.assertEqual(normalize_api_response(payload), [payload])

    def test_normalize_api_response_handles_batch_shape(self):
        payload = [
            [
                {"label": "LABEL_0", "score": 0.05},
                {"label": "LABEL_1", "score": 0.9},
            ]
        ]

        self.assertEqual(normalize_api_response(payload), payload)

    def test_analyze_mentions_returns_result_per_mention(self):
        results = analyze_mentions(
            [MentionForSentiment(id=7, headline="NASA update", raw_text="Routine mission news")],
            FakeSentimentClient(),
            batch_size=1,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].mention_id, 7)
        self.assertEqual(results[0].label, "neutral")
        self.assertEqual(results[0].confidence, 0.9)

    def test_analyze_mentions_rejects_invalid_batch_size(self):
        with self.assertRaises(ValueError):
            analyze_mentions([], FakeSentimentClient(), batch_size=0)


if __name__ == "__main__":
    unittest.main()
