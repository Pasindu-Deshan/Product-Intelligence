-- =============================================================================
-- 003_capability_taxonomy.sql
-- Controlled taxonomy. The classifier may only assign values that exist here.
-- =============================================================================
CREATE TABLE IF NOT EXISTS capability (
    capability_id SERIAL PRIMARY KEY,
    name          VARCHAR(255) NOT NULL UNIQUE,
    description   TEXT,
    is_active     BOOLEAN NOT NULL DEFAULT true,
    created_date  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sub_capability (
    sub_capability_id SERIAL PRIMARY KEY,
    capability_id     INTEGER NOT NULL REFERENCES capability(capability_id),
    name              VARCHAR(255) NOT NULL,
    description       TEXT,
    is_active         BOOLEAN NOT NULL DEFAULT true,
    created_date      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (capability_id, name)
);

CREATE TABLE IF NOT EXISTS work_item_capability (
    work_item_id            INTEGER NOT NULL REFERENCES work_item(work_item_id),
    capability              VARCHAR(255) NOT NULL,
    sub_capability          VARCHAR(255),
    confidence              NUMERIC(5,4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    model_version           VARCHAR(100) NOT NULL,
    classified_date         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_human_reviewed       BOOLEAN NOT NULL DEFAULT false,
    reviewed_by             VARCHAR(255),
    reviewed_date           TIMESTAMP WITH TIME ZONE,
    override_capability     VARCHAR(255),
    override_sub_capability VARCHAR(255),
    PRIMARY KEY (work_item_id, capability),
    CONSTRAINT fk_wic_capability FOREIGN KEY (capability) REFERENCES capability(name)
);

CREATE INDEX IF NOT EXISTS idx_wic_capability ON work_item_capability (capability);
CREATE INDEX IF NOT EXISTS idx_wic_confidence ON work_item_capability (confidence);
