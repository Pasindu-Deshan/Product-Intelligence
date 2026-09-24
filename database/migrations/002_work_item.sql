-- =============================================================================
-- 002_work_item.sql
-- Azure DevOps work-item metadata, owned by Product Intelligence's sync process.
-- =============================================================================
CREATE TABLE IF NOT EXISTS work_item (
    work_item_id    INTEGER PRIMARY KEY,
    title           VARCHAR(1000),
    description     TEXT,
    work_item_type  VARCHAR(100),
    state           VARCHAR(100),
    assigned_to     VARCHAR(255),
    iteration_path  VARCHAR(1000),
    area_path       VARCHAR(1000),
    created_date    TIMESTAMP WITH TIME ZONE,
    modified_date   TIMESTAMP WITH TIME ZONE,
    last_sync_date  TIMESTAMP WITH TIME ZONE
);

COMMENT ON TABLE work_item IS
    'Azure DevOps work-item metadata, synced independently of worklog_record.';

-- worklog_record.work_item_id is a LOGICAL relationship, not a hard FK, because
-- the widget may insert a worklog before the work item has synced. Enforced via
-- LEFT JOINs in the views + the MISSING_WORK_ITEM data-quality check.
-- To promote once the widget team confirms ordering guarantees:
--   ALTER TABLE worklog_record ADD CONSTRAINT fk_worklog_work_item
--       FOREIGN KEY (work_item_id) REFERENCES work_item(work_item_id) NOT VALID;
--   ALTER TABLE worklog_record VALIDATE CONSTRAINT fk_worklog_work_item;
