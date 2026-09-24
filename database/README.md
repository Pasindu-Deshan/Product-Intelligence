# Database

`migrations/` is the source of truth for what gets applied. `views/` and
`indexes/` contain copies of the same definitions split out by kind, purely for
browsing — do not edit them independently of the migration that owns them.

| File | Purpose |
|---|---|
| `001_existing_schema.sql` | Local-dev reproduction of the widget's tables (`memo_code_master`, `time_code_master`, `worklog_record`). **Skip against real environments** — the widget's own migration process owns them. |
| `002_work_item.sql` | `work_item` metadata, owned by this application's sync. No hard FK from `worklog_record`; see the inline rationale and the `NOT VALID` promotion path. |
| `003_capability_taxonomy.sql` | `capability`, `sub_capability`, `work_item_capability` with human-review/override columns. |
| `004_indexes.sql` | Indexes derived from real query shapes, each with its rationale. |
| `005_analytics_view.sql` | `vw_worklog_analysis` — **capability grain**, one row per (worklog, capability). |
| `006_data_quality.sql` | `vw_data_quality_issues` — 11 live checks. |
| `007_base_view.sql` | `vw_worklog_base` — one row per worklog. All non-capability aggregation reads this. |
| `008_readonly_role.sql` | Read-only application role and narrower classifier role. Needs elevated privileges. |

```bash
ADMIN_DATABASE_URL=postgresql://postgres@localhost/product_intelligence \
  ../scripts/init_db.sh --with-roles --seed
```

## The grain trap

`vw_worklog_analysis` fans out: a work item classified into two capabilities
appears twice per worklog. `SUM(hours)` over it double-counts. Use
`vw_worklog_base` for anything that is not explicitly capability analysis, and
apply capability *filters* as an `EXISTS` subquery rather than a join.

## Seed data

`seed/dev_seed.sql` contains six deliberately malformed rows (orphaned work
item, inactive codes, zero hours, blank comment, blank user, sync failure) so
the data-quality view has something to find and the test suite has known
expected values. Do not load it outside dev/test.
