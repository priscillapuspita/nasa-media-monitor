CREATE TABLE IF NOT EXISTS mentions (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    headline TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    published_at TIMESTAMPTZ,
    raw_text TEXT,
    sentiment_label TEXT CHECK (
        sentiment_label IS NULL
        OR sentiment_label IN ('negative', 'neutral', 'positive')
    ),
    sentiment_confidence NUMERIC(5, 4) CHECK (
        sentiment_confidence IS NULL
        OR (sentiment_confidence >= 0 AND sentiment_confidence <= 1)
    ),
    sentiment_analyzed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_mentions_source ON mentions (source);
CREATE INDEX IF NOT EXISTS idx_mentions_published_at ON mentions (published_at DESC);
CREATE INDEX IF NOT EXISTS idx_mentions_sentiment_label ON mentions (sentiment_label);

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
