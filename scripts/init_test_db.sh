#!/usr/bin/env bash
# Recreate the test database from scratch and seed it.
#   TEST_DATABASE_URL=postgresql+psycopg://pi:pi@localhost:5432/pi_test ./scripts/init_test_db.sh
set -euo pipefail
: "${TEST_DATABASE_URL:?set TEST_DATABASE_URL}"
ADMIN_DATABASE_URL="$TEST_DATABASE_URL" "$(dirname "$0")/init_db.sh" --seed
