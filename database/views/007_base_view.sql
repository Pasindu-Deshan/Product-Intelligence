-- =============================================================================
-- 007_base_view.sql
--
-- vw_worklog_base is the deduplicated companion to vw_worklog_analysis: exactly
-- one row per worklog_id, with no capability fan-out. Every non-capability
-- aggregation (total hours, by user, by memo, by date, by work item, iteration
-- summary, period comparison) reads from HERE so that SUM(hours) is correct
-- regardless of how many capabilities a work item is classified into.
--
-- has_capability lets the UI/data-quality layer report classification coverage
-- without needing the fanned-out view.
-- =============================================================================
CREATE OR REPLACE VIEW vw_worklog_base AS
SELECT
    w.worklog_id,
    w.work_item_id,
    wi.title,
    wi.description,
    w.work_item_type,
    wi.state,
    wi.assigned_to,
    w.user_id,
    wi.iteration_path,
    wi.area_path,
    w.memo_code,
    mc.description AS memo_description,
    w.time_code,
    tc.name        AS time_code_name,
    w.time_code_source,
    w.hours,
    w.work_date,
    w.comment,
    w.created_date,
    w.modified_date,
    w.sync_status,
    w.last_sync_date,
    EXISTS (SELECT 1 FROM work_item_capability c WHERE c.work_item_id = w.work_item_id)
        AS has_capability
FROM worklog_record w
INNER JOIN memo_code_master mc ON mc.code = w.memo_code
INNER JOIN time_code_master tc ON tc.code = w.time_code
LEFT JOIN work_item wi ON wi.work_item_id = w.work_item_id;

COMMENT ON VIEW vw_worklog_base IS
    'One row per worklog_id. Authoritative source for all non-capability aggregation.';
