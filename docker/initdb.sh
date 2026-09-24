#!/bin/sh
# Applied once, on first container start, by the postgres entrypoint.
set -e
for f in /docker-entrypoint-initdb.d/migrations/0*.sql; do
  case "$f" in
    *008_readonly_role.sql) echo "skipping $f (role setup is environment-specific)"; continue ;;
  esac
  echo "applying $f"
  psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$f"
done

if [ "${SEED_DEV_DATA:-true}" = "true" ] && [ -f /seed/dev_seed.sql ]; then
  echo "seeding dev data"
  psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /seed/dev_seed.sql
fi
