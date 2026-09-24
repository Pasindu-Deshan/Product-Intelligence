-- =============================================================================
-- 008_readonly_role.sql
--
-- Architectural Rule 8: the analytics application connects with a role that
-- physically cannot write. Run this as a superuser/owner ONCE per environment.
-- Replace the password with a value from your secret store; never commit it.
--
--   psql "$ADMIN_DATABASE_URL" \
--        -v pi_password="$(read-from-keyvault)" -f 008_readonly_role.sql
-- =============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'product_intelligence_ro') THEN
        CREATE ROLE product_intelligence_ro LOGIN;
    END IF;
END
$$;

-- Connect + read only. No INSERT/UPDATE/DELETE/TRUNCATE/CREATE/EXECUTE.
GRANT CONNECT ON DATABASE CURRENT_CATALOG TO product_intelligence_ro;
GRANT USAGE ON SCHEMA public TO product_intelligence_ro;

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM product_intelligence_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO product_intelligence_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO product_intelligence_ro;

-- Belt and braces: block DDL and function execution.
REVOKE CREATE ON SCHEMA public FROM product_intelligence_ro;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM product_intelligence_ro;

-- The classifier needs to WRITE work_item_capability. It therefore uses a
-- SEPARATE, narrower role and a separate connection string
-- (CLASSIFIER_DATABASE_URL) - the API/agent connection stays read-only.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'product_intelligence_classifier') THEN
        CREATE ROLE product_intelligence_classifier LOGIN;
    END IF;
END
$$;
GRANT CONNECT ON DATABASE CURRENT_CATALOG TO product_intelligence_classifier;
GRANT USAGE ON SCHEMA public TO product_intelligence_classifier;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO product_intelligence_classifier;
GRANT INSERT, UPDATE ON work_item_capability TO product_intelligence_classifier;
