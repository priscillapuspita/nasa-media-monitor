CREATE TABLE IF NOT EXISTS alert_events (
    id SERIAL PRIMARY KEY,
    alert_type TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    current_volume INTEGER NOT NULL,
    baseline_volume NUMERIC(10, 2) NOT NULL,
    threshold_multiplier NUMERIC(5, 2) NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (alert_type, window_start, window_end)
);

CREATE INDEX IF NOT EXISTS idx_alert_events_sent_at ON alert_events (sent_at DESC);
