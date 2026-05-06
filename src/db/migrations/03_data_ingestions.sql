-- Migration: data_ingestions table
-- Purpose: Track CSV/Excel/ERP uploads used for auto-detecting scoping parameters

CREATE TABLE IF NOT EXISTS data_ingestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    engagement_id UUID REFERENCES foundation_engagements(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL CHECK (source_type IN ('csv', 'excel', 'erp')),
    raw_filename TEXT,
    row_count INTEGER,
    column_count INTEGER,
    detected_params JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_data_ingestions_engagement_id ON data_ingestions(engagement_id);
CREATE INDEX idx_data_ingestions_source_type ON data_ingestions(source_type);
