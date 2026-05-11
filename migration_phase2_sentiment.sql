ALTER TABLE mentions
ADD COLUMN IF NOT EXISTS sentiment_label TEXT CHECK (
    sentiment_label IS NULL
    OR sentiment_label IN ('negative', 'neutral', 'positive')
);

ALTER TABLE mentions
ADD COLUMN IF NOT EXISTS sentiment_confidence NUMERIC(5, 4);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'mentions_sentiment_confidence_range'
    ) THEN
        ALTER TABLE mentions
        ADD CONSTRAINT mentions_sentiment_confidence_range
        CHECK (
            sentiment_confidence IS NULL
            OR (sentiment_confidence >= 0 AND sentiment_confidence <= 1)
        );
    END IF;
END $$;

ALTER TABLE mentions
ADD COLUMN IF NOT EXISTS sentiment_analyzed_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_mentions_sentiment_label ON mentions (sentiment_label);
