-- =============================================================================
-- 006_data_quality.sql -- one row per detected problem, always live.
-- =============================================================================
CREATE OR REPLACE VIEW vw_data_quality_issues AS
SELECT w.worklog_id, 'INVALID_WORK_ITEM_ID' AS issue_type, 'high' AS severity,
       format('work_item_id %s is not a valid positive identifier', w.work_item_id) AS detail
FROM worklog_record w WHERE w.work_item_id <= 0
UNION ALL
SELECT w.worklog_id, 'MISSING_WORK_ITEM', 'high',
       format('no work_item row found for work_item_id %s', w.work_item_id)
FROM worklog_record w LEFT JOIN work_item wi ON wi.work_item_id = w.work_item_id
WHERE wi.work_item_id IS NULL AND w.work_item_id > 0
UNION ALL
SELECT w.worklog_id, 'INACTIVE_MEMO_CODE', 'medium',
       format('memo_code %s is marked inactive', w.memo_code)
FROM worklog_record w INNER JOIN memo_code_master mc ON mc.code = w.memo_code
WHERE mc.is_active = false
UNION ALL
SELECT w.worklog_id, 'INACTIVE_TIME_CODE', 'medium',
       format('time_code %s is marked inactive', w.time_code)
FROM worklog_record w INNER JOIN time_code_master tc ON tc.code = w.time_code
WHERE tc.is_active = false
UNION ALL
SELECT w.worklog_id, 'NEGATIVE_HOURS', 'high', format('hours value %s is negative', w.hours)
FROM worklog_record w WHERE w.hours < 0
UNION ALL
SELECT w.worklog_id, 'ZERO_HOURS', 'low', 'hours value is zero'
FROM worklog_record w WHERE w.hours = 0
UNION ALL
SELECT w.worklog_id, 'DUPLICATE_WORKLOG', 'medium',
       format('possible duplicate for user %s / work item %s / date %s', w.user_id, w.work_item_id, w.work_date)
FROM worklog_record w
WHERE EXISTS (SELECT 1 FROM worklog_record w2
              WHERE w2.worklog_id <> w.worklog_id AND w2.user_id = w.user_id
                AND w2.work_item_id = w.work_item_id AND w2.work_date = w.work_date
                AND w2.memo_code = w.memo_code AND w2.time_code = w.time_code
                AND w2.hours = w.hours)
UNION ALL
SELECT w.worklog_id, 'MISSING_COMMENT', 'low', 'comment is blank'
FROM worklog_record w WHERE trim(w.comment) = ''
UNION ALL
SELECT w.worklog_id, 'INVALID_DATE', 'medium', format('work_date %s is in the future', w.work_date)
FROM worklog_record w WHERE w.work_date > CURRENT_DATE
UNION ALL
SELECT w.worklog_id, 'MISSING_USER', 'high', 'user_id is blank'
FROM worklog_record w WHERE trim(w.user_id) = ''
UNION ALL
SELECT w.worklog_id, 'SYNC_FAILURE', 'medium', format('sync_status is "%s"', w.sync_status)
FROM worklog_record w WHERE w.sync_status ILIKE 'fail%' OR w.sync_status ILIKE 'error%';

COMMENT ON VIEW vw_data_quality_issues IS
    'Deterministic, always-live data-quality findings. Never mutates data.';
