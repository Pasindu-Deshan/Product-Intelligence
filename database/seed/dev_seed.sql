-- Dev/test seed data. Includes deliberately "bad" rows so the data-quality view
-- has something to find. Do NOT use in real environments.

INSERT INTO memo_code_master (code, description, is_active) VALUES
    ('DEV', 'Development', true),
    ('QA', 'Quality Assurance', true),
    ('REVIEW', 'Code Review', true),
    ('SUPPORT', 'Support', true),
    ('LEGACY', 'Legacy memo code, no longer used', false)
ON CONFLICT (code) DO NOTHING;

INSERT INTO time_code_master (code, name, is_active) VALUES
    ('REG', 'Regular', true),
    ('OT', 'Overtime', true),
    ('OLD', 'Deprecated time code', false)
ON CONFLICT (code) DO NOTHING;

INSERT INTO work_item (work_item_id, title, description, work_item_type, state, assigned_to, iteration_path, area_path, created_date, modified_date, last_sync_date) VALUES
    (1234, 'Implement SSO', 'Add single sign-on support via SAML', 'User Story', 'Closed', 'alice@example.com', 'Product\Sprint 24', 'Product\Auth', now() - interval '20 days', now() - interval '2 days', now()),
    (1250, 'Password Reset flow', 'Self-service password reset', 'User Story', 'Closed', 'bob@example.com', 'Product\Sprint 24', 'Product\Auth', now() - interval '18 days', now() - interval '3 days', now()),
    (1288, 'MFA support', 'Add TOTP-based MFA', 'User Story', 'Active', 'alice@example.com', 'Product\Sprint 24', 'Product\Auth', now() - interval '10 days', now() - interval '1 day', now()),
    (1300, 'Appointment creation bug', 'Double-booking under load', 'Bug', 'Closed', 'carol@example.com', 'Product\Sprint 24', 'Product\Scheduling', now() - interval '9 days', now() - interval '1 day', now()),
    (1301, 'Rescheduling UI', 'Allow drag-and-drop rescheduling', 'User Story', 'Active', 'carol@example.com', 'Product\Sprint 23', 'Product\Scheduling', now() - interval '40 days', now() - interval '25 days', now())
ON CONFLICT (work_item_id) DO NOTHING;

INSERT INTO worklog_record (worklog_id, work_item_id, work_item_type, user_id, memo_code, time_code, time_code_source, hours, work_date, comment, sync_status) VALUES
    ('WL-1',  1234, 'User Story', 'alice@example.com', 'DEV',    'REG', 'Manual', 8.0,  CURRENT_DATE - 10, 'SAML integration work', 'Synced'),
    ('WL-2',  1234, 'User Story', 'alice@example.com', 'DEV',    'REG', 'Manual', 4.5,  CURRENT_DATE - 9,  'SAML integration work continued', 'Synced'),
    ('WL-3',  1234, 'User Story', 'bob@example.com',   'QA',     'REG', 'Manual', 7.0,  CURRENT_DATE - 8,  'Tested SSO flows', 'Synced'),
    ('WL-4',  1234, 'User Story', 'alice@example.com', 'REVIEW', 'REG', 'Manual', 4.0,  CURRENT_DATE - 7,  'Reviewed SSO PR', 'Synced'),
    ('WL-5',  1250, 'User Story', 'bob@example.com',   'DEV',    'REG', 'Manual', 8.0,  CURRENT_DATE - 6,  'Password reset backend', 'Synced'),
    ('WL-6',  1288, 'User Story', 'alice@example.com', 'DEV',    'REG', 'Manual', 6.0,  CURRENT_DATE - 3,  'MFA TOTP implementation', 'Synced'),
    ('WL-7',  1300, 'Bug',        'carol@example.com', 'DEV',    'REG', 'Manual', 3.0,  CURRENT_DATE - 4,  'Fixed double-booking race condition', 'Synced'),
    ('WL-8',  1301, 'User Story', 'carol@example.com', 'DEV',    'REG', 'Manual', 12.0, CURRENT_DATE - 30, 'Drag-and-drop rescheduling', 'Synced'),
    -- Deliberately bad rows:
    ('WL-9',  9999, 'Bug',        'dave@example.com',  'DEV',    'REG', 'Manual', 2.0,  CURRENT_DATE - 1, 'work on unknown item', 'Synced'),
    ('WL-10', 1234, 'User Story', 'alice@example.com', 'LEGACY', 'REG', 'Manual', 1.0,  CURRENT_DATE - 1, 'misc', 'Synced'),
    ('WL-11', 1234, 'User Story', 'alice@example.com', 'DEV',    'OLD', 'Manual', 1.0,  CURRENT_DATE - 1, 'misc', 'Synced'),
    ('WL-12', 1288, 'User Story', 'alice@example.com', 'DEV',    'REG', 'Manual', 0.0,  CURRENT_DATE - 1, 'placeholder entry', 'Synced'),
    ('WL-13', 1288, 'User Story', 'alice@example.com', 'DEV',    'REG', 'Manual', 3.0,  CURRENT_DATE - 1, '  ', 'Synced'),
    ('WL-14', 1288, 'User Story', '  ',                'DEV',    'REG', 'Manual', 1.0,  CURRENT_DATE - 1, 'no user recorded', 'Failed to sync')
ON CONFLICT (worklog_id) DO NOTHING;

INSERT INTO capability (name, description) VALUES
    ('Authentication', 'Login, SSO, password reset, MFA'),
    ('Scheduling', 'Appointment creation, cancellation, rescheduling'),
    ('Patient Management', 'Registration, demographics, merge/delete'),
    ('Reporting', 'Reports, exports, dashboards')
ON CONFLICT (name) DO NOTHING;

INSERT INTO sub_capability (capability_id, name) VALUES
    ((SELECT capability_id FROM capability WHERE name = 'Authentication'), 'Login'),
    ((SELECT capability_id FROM capability WHERE name = 'Authentication'), 'SSO'),
    ((SELECT capability_id FROM capability WHERE name = 'Authentication'), 'Password Reset'),
    ((SELECT capability_id FROM capability WHERE name = 'Authentication'), 'MFA'),
    ((SELECT capability_id FROM capability WHERE name = 'Scheduling'), 'Appointment Creation'),
    ((SELECT capability_id FROM capability WHERE name = 'Scheduling'), 'Rescheduling')
ON CONFLICT DO NOTHING;

INSERT INTO work_item_capability (work_item_id, capability, sub_capability, confidence, model_version) VALUES
    (1234, 'Authentication', 'SSO', 0.95, 'gpt-classifier-v1'),
    (1250, 'Authentication', 'Password Reset', 0.92, 'gpt-classifier-v1'),
    (1288, 'Authentication', 'MFA', 0.88, 'gpt-classifier-v1'),
    (1300, 'Scheduling', 'Appointment Creation', 0.81, 'gpt-classifier-v1'),
    (1301, 'Scheduling', 'Rescheduling', 0.90, 'gpt-classifier-v1')
ON CONFLICT (work_item_id, capability) DO NOTHING;
