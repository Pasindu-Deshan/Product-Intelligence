-- =============================================================================
-- 004_indexes.sql  -- chosen from expected query patterns, rationale inline.
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_worklog_work_item_id ON worklog_record (work_item_id);
CREATE INDEX IF NOT EXISTS idx_worklog_user_id      ON worklog_record (user_id);
CREATE INDEX IF NOT EXISTS idx_worklog_memo_code    ON worklog_record (memo_code);
CREATE INDEX IF NOT EXISTS idx_worklog_time_code    ON worklog_record (time_code);
CREATE INDEX IF NOT EXISTS idx_worklog_work_date    ON worklog_record (work_date);
CREATE INDEX IF NOT EXISTS idx_worklog_date_memo    ON worklog_record (work_date, memo_code);
CREATE INDEX IF NOT EXISTS idx_worklog_sync_status  ON worklog_record (sync_status);
CREATE INDEX IF NOT EXISTS idx_work_item_iteration_path ON work_item (iteration_path);
CREATE INDEX IF NOT EXISTS idx_work_item_type           ON work_item (work_item_type);
