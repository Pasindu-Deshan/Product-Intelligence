# Product Intelligence

Analytics and conversational intelligence over the time-logging data produced by
the Azure DevOps time-logging widget.

This is a **separate application**. It is not embedded in the widget and never
writes to the widget's tables. PostgreSQL is the source of truth; the LLM
interprets questions and explains results but never touches the database and
never calculates an authoritative number.

---

## What it does

| | |
|---|---|
| **Dashboard** | Hours, work items, users and worklog counts, filtered by iteration, date range, user, work item type, memo code, time code and capability. |
| **Capability analysis** | Work items are classified into a curated product capability taxonomy, so effort can be reported by product area rather than only by ticket. |
| **Conversational agent** | Natural-language questions answered from the database via a fixed set of controlled tools, with the supporting work items shown alongside every answer. |
| **Data quality** | Eleven deterministic checks surfaced through their own endpoint, reported and never silently corrected. |

---

## Architecture at a glance

```
Azure DevOps ──> time-logging widget ──> PostgreSQL <── work-item sync
                                              │
                          ┌───────────────────┴───────────────────┐
                    vw_worklog_base                   vw_worklog_analysis
                (one row per worklog)              (capability grain)
                          └───────────────────┬───────────────────┘
                                     Repository layer  (all SQL, all arithmetic)
                                              │
                          ┌───────────────────┴───────────────────┐
                   Analytics service                     Capability classifier
                          │                                       │
                   FastAPI endpoints  <── Agent tools <── Agent ──┘
                                              │
                                      React dashboard + chat
```

Full detail, and the reasoning behind each boundary, is in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Quick start (Docker)

```bash
cp .env.example .env          # set LLM_API_KEY if you want the chat to work
docker compose up --build
```

- Dashboard: <http://localhost:8080>
- API docs: <http://localhost:8000/docs>
- Health: <http://localhost:8000/api/health>

The database container applies every migration and seeds demo data on first
start. The chat panel is the only feature that needs an LLM key — everything
else works without one.

---

## Quick start (local, no Docker)

```bash
# 1. Database
createdb product_intelligence
ADMIN_DATABASE_URL=postgresql://localhost/product_intelligence \
  ./scripts/init_db.sh --seed

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env        # edit DATABASE_URL
uvicorn app.main:app --reload

# 3. Frontend
cd ../frontend
npm install
npm run dev                    # http://localhost:5173
```

---

## Database migrations

Apply in order. `database/migrations/` is authoritative; `views/` and
`indexes/` hold the same definitions split out for browsing only.

| File | Purpose |
|---|---|
| `001_existing_schema.sql` | Local-dev reproduction of the widget's tables. **Skip against real environments** — the widget owns them. |
| `002_work_item.sql` | `work_item` metadata table. Logical, not hard, FK from `worklog_record` (see the file's comments). |
| `003_capability_taxonomy.sql` | `capability`, `sub_capability`, `work_item_capability`, including human-review columns. |
| `004_indexes.sql` | Indexes chosen from the actual query patterns, each with rationale. |
| `005_analytics_view.sql` | `vw_worklog_analysis` — capability grain. |
| `006_data_quality.sql` | `vw_data_quality_issues` — 11 live checks. |
| `007_base_view.sql` | `vw_worklog_base` — one row per worklog. **All non-capability aggregation reads this.** |
| `008_readonly_role.sql` | Read-only and classifier roles. Needs elevated privileges; run once per environment. |

```bash
ADMIN_DATABASE_URL=... ./scripts/init_db.sh --with-roles
```

### Why two views

`vw_worklog_analysis` joins `work_item_capability`, so a work item classified
into two capabilities appears twice per worklog. Summing hours over it
double-counts. `vw_worklog_base` is the deduplicated companion, and every total,
breakdown and comparison reads from it. Capability filters are applied as an
`EXISTS` subquery rather than a join, for the same reason.

---

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Liveness, database and LLM configuration status. |
| `GET /api/iterations` | Distinct iteration paths. |
| `GET /api/filters` | Everything needed to populate the filter controls. |
| `GET /api/dashboard/summary` | KPIs, capability, memo, date and top-work-item breakdowns in one call. |
| `GET /api/analytics/time` | Total hours plus worklog/work item/user counts. |
| `GET /api/analytics/by-user` · `by-work-item` · `by-work-item-type` · `by-memo` · `by-time-code` · `by-capability` · `by-date` | Breakdowns. |
| `GET /api/analytics/compare` | Two periods, with absolute and percentage difference. |
| `GET /api/work-items/{id}` | Metadata, hours, capabilities and worklogs. |
| `GET /api/data-quality` | Data-quality findings, filterable by type and severity. |
| `POST /api/chat` | Conversational question answering. |

All analytics endpoints accept the same filter query string:
`iteration_path`, `date_from`, `date_to`, `user_id`, `work_item_id`,
`work_item_type`, `memo_code`, `time_code`, `capability`, `sub_capability`.

```bash
curl "localhost:8000/api/analytics/by-capability?iteration_path=Product\\Sprint%2024"

curl -X POST localhost:8000/api/chat -H 'content-type: application/json' \
  -d '{"message":"How much time did we spend on Authentication this sprint?"}'
```

---

## Capability classification

```bash
python scripts/classify.py --dry-run     # show what would be classified
python scripts/classify.py --limit 50    # classify and persist
```

The classifier may only assign capabilities that exist in the `capability`
table. Anything else is rejected, not created. It abstains when a work item has
too little signal, records a confidence score and the model version, and never
overwrites a human-reviewed classification. Bump `CLASSIFIER_MODEL_VERSION` to
force a re-run after changing the prompt or model.

Adding a capability is a deliberate act:

```sql
INSERT INTO capability (name, description) VALUES ('Billing', 'Invoicing and payments');
INSERT INTO sub_capability (capability_id, name)
  VALUES ((SELECT capability_id FROM capability WHERE name='Billing'), 'Invoice Generation');
```

---

## Testing

```bash
cd backend
pytest                                   # unit tests only
export TEST_DATABASE_URL=postgresql+psycopg://pi:pi@localhost:5432/pi_test
../scripts/init_test_db.sh
pytest                                   # full suite
pytest --cov=app --cov-report=term-missing
```

Tests needing PostgreSQL skip automatically when `TEST_DATABASE_URL` is unset —
the analytics SQL uses `date_trunc`, `FILTER (WHERE ...)` and `ILIKE`, so SQLite
is not a viable substitute. Expected values are hand-derived from
`database/seed/dev_seed.sql`, so a SQL regression shows up as a *wrong* number
rather than merely a different one. The agent tests use a scripted fake model:
they verify our orchestration, not the vendor's.

| File | Covers |
|---|---|
| `test_metrics.py` | Percentages, differences, rounding, relative date resolution. No database. |
| `test_analytics.py` | Every aggregation and filter against the seeded dataset. |
| `test_tools.py` | Parameter validation, context merging, absence of any raw-SQL tool. |
| `test_agent.py` | Guardrails, grounding, evidence, follow-up context, iteration limit, LLM outage. |
| `test_classifier.py` | Taxonomy enforcement, abstention, confidence handling. |
| `test_api.py` | Status codes, validation, pagination limits, no leakage of SQL or traces. |

### Evaluation

```bash
python evaluation/run_eval.py --intent-only    # no LLM calls, no cost
python evaluation/run_eval.py --verbose        # full run against a seeded DB
```

48 questions across simple aggregation, filtering, ranking, comparison,
capability, work item, user, date, follow-up, ambiguous and unsupported
categories. Scores intent, tool selection, numerical and evidence accuracy, and
exits non-zero below 90%.

---

## Security

- The API, analytics layer and every agent tool run on a **read-only**
  PostgreSQL role, and the session is additionally set read-only at connect
  time. The classifier uses a separate, narrower role and connection string.
- The LLM has no database access and no generic query tool. It may only call the
  fourteen registered tools, each of which validates its parameters through a
  Pydantic model that rejects unknown fields.
- All values reach SQL as bound parameters. The only interpolated tokens are
  whitelisted literals (for example the `date_trunc` unit).
- Every result set is capped; `MAX_ROWS_HARD_LIMIT` is enforced in the
  repository, not just in the API.
- Database errors, stack traces, connection strings and API keys never reach the
  client. Errors return a message plus a request id that correlates to the logs.
- Credentials come from environment variables only. `Settings` fails fast at
  startup rather than falling back to a default.

### Adding Entra ID

`AUTH_*` settings are in place but not yet enforced. To enable: validate the
bearer token in a FastAPI dependency, apply it to the routers in `main.py`, and
pass the caller's identity through to logging. No change to the analytics or
agent layers is required.

---

## Production deployment

Suggested Azure shape:

- **Azure Container Apps** for the backend image, with the frontend either as a
  second container behind the same ingress or on Azure Static Web Apps.
- **Azure Database for PostgreSQL Flexible Server**, with the read-only and
  classifier roles created by migration 008.
- **Key Vault** for `DATABASE_URL`, `CLASSIFIER_DATABASE_URL` and `LLM_API_KEY`,
  surfaced as Key Vault references in App Settings.
- **Azure OpenAI** by pointing `LLM_API_BASE` at the deployment's compatible
  endpoint.
- The classifier as a **scheduled job** running `scripts/classify.py`, not as
  part of the web process.
- Replace `InMemoryConversationStore` with a Redis-backed implementation of the
  same three-method protocol before scaling past one instance.

Before going live: run migrations (excluding 001), verify
`/api/health` reports the database up, and confirm the application's role
cannot write:

```sql
SET ROLE product_intelligence_ro;
INSERT INTO work_item (work_item_id) VALUES (1);  -- must fail
```
