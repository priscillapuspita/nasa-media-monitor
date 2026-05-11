import unittest
from datetime import datetime, timezone

from alerting import SpikeCheck, build_spike_message


class AlertingTest(unittest.TestCase):
    def test_spike_detection_requires_more_than_2x_baseline(self):
        check = SpikeCheck(
            window_start=datetime(2026, 5, 11, 10, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 11, 11, tzinfo=timezone.utc),
            current_volume=21,
            baseline_volume=10,
            threshold_multiplier=2.0,
        )

        self.assertTrue(check.is_spike)

    def test_equal_to_threshold_is_not_a_spike(self):
        check = SpikeCheck(
            window_start=datetime(2026, 5, 11, 10, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 11, 11, tzinfo=timezone.utc),
            current_volume=20,
            baseline_volume=10,
            threshold_multiplier=2.0,
        )

        self.assertFalse(check.is_spike)

    def test_zero_baseline_is_not_a_spike(self):
        check = SpikeCheck(
            window_start=datetime(2026, 5, 11, 10, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 11, 11, tzinfo=timezone.utc),
            current_volume=5,
            baseline_volume=0,
            threshold_multiplier=2.0,
        )

        self.assertFalse(check.is_spike)

    def test_build_spike_message_includes_current_and_baseline(self):
        check = SpikeCheck(
            window_start=datetime(2026, 5, 11, 10, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 11, 11, tzinfo=timezone.utc),
            current_volume=21,
            baseline_volume=10,
            threshold_multiplier=2.0,
        )

        message = build_spike_message(check)

        self.assertIn("21 mentions", message)
        self.assertIn("10.00", message)
        self.assertIn("2.0x", message)


if __name__ == "__main__":
    unittest.main()
