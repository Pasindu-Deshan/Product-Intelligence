-- =============================================================================
-- 001_existing_schema.sql
--
-- Reproduces the EXISTING tables owned by the Azure DevOps time-logging widget.
-- Local dev / CI only. SKIP against real prod/staging.
-- =============================================================================
CREATE TABLE IF NOT EXISTS memo_code_master (
    code        VARCHAR(100) PRIMARY KEY,
    description TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS time_code_master (
    code      VARCHAR(100) PRIMARY KEY,
    name      VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS worklog_record (
    worklog_id         VARCHAR(100) PRIMARY KEY,
    work_item_id       INTEGER NOT NULL,
    work_item_type     VARCHAR(100) NOT NULL,
    user_id            VARCHAR(100) NOT NULL,
    memo_code          VARCHAR(100) NOT NULL REFERENCES memo_code_master(code),
    time_code          VARCHAR(100) NOT NULL REFERENCES time_code_master(code),
    time_code_source   VARCHAR(100) NOT NULL,
    hours              NUMERIC(5, 2) NOT NULL,
    work_date          DATE NOT NULL,
    comment            TEXT NOT NULL,
    created_date       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_date      TIMESTAMP WITH TIME ZONE,
    external_system    VARCHAR(100),
    external_record_id VARCHAR(100),
    sync_status        VARCHAR(100) NOT NULL DEFAULT 'Not Synced',
    last_sync_date     TIMESTAMP WITH TIME ZONE
);

COMMENT ON TABLE worklog_record IS
    'Owned by the Azure DevOps time-logging widget. Product Intelligence has READ-ONLY access.';
