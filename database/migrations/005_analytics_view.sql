-- =============================================================================
-- 005_analytics_view.sql
-- vw_worklog_analysis: unified semantic dataset.
-- GRAIN WARNING: one row per (worklog_id, capability). A work item classified
-- into N capabilities fans its worklogs out N times. Use this view ONLY for
-- capability-scoped analysis. For all other aggregation use vw_worklog_base
-- (migration 007), which is one row per worklog_id.
-- =============================================================================
CREATE OR REPLACE VIEW vw_worklog_analysis AS
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
    mc.description        AS memo_description,
    w.time_code,
    tc.name               AS time_code_name,
    w.time_code_source,
    w.hours,
    w.work_date,
    w.comment,
    w.created_date,
    w.modified_date,
    w.sync_status,
    w.last_sync_date,
    COALESCE(wic.override_capability, wic.capability)         AS capability,
    COALESCE(wic.override_sub_capability, wic.sub_capability) AS sub_capability,
    wic.confidence        AS capability_confidence,
    wic.is_human_reviewed AS capability_human_reviewed
FROM worklog_record w
INNER JOIN memo_code_master mc ON mc.code = w.memo_code
INNER JOIN time_code_master tc ON tc.code = w.time_code
LEFT JOIN work_item wi ON wi.work_item_id = w.work_item_id
LEFT JOIN work_item_capability wic ON wic.work_item_id = w.work_item_id;

COMMENT ON VIEW vw_worklog_analysis IS
    'Capability-grain read model: one row per (worklog_id, capability). Do not SUM(hours) without a capability filter - use vw_worklog_base instead.';
