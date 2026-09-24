# Architecture

## 1. Layers

```
┌──────────────────────────────────────────────────────────────┐
│ React frontend            dashboard  ·  chat  ·  evidence    │
└───────────────────────────┬──────────────────────────────────┘
                            │ HTTP/JSON, same origin in prod
┌───────────────────────────▼──────────────────────────────────┐
│ FastAPI                   routers, Pydantic contracts,       │
│                           error handling, correlation ids    │
└───────────────────────────┬──────────────────────────────────┘
          ┌─────────────────┴──────────────────┐
          │                                    │
┌─────────▼──────────┐              ┌──────────▼───────────────┐
│ Analytics service  │              │ Agent                    │
│ composition only   │              │ guardrail → tools → text │
└─────────┬──────────┘              └──────────┬───────────────┘
          │                                    │ tools only
          │             ┌──────────────────────┘
┌─────────▼─────────────▼──────────────────────────────────────┐
│ Repository layer     all SQL · all arithmetic · row limits   │
└───────────────────────────┬──────────────────────────────────┘
                            │ read-only role
┌───────────────────────────▼──────────────────────────────────┐
│ PostgreSQL          vw_worklog_base · vw_worklog_analysis    │
│                     vw_data_quality_issues                   │
└──────────────────────────────────────────────────────────────┘

                            ▲ write-capable role, separate connection
                 ┌──────────┴───────────┐
                 │ Capability classifier│
                 └──────────────────────┘
```

Each boundary exists for a reason:

- **Routers hold no business logic.** They parse, delegate and return. Swapping
  the transport would not touch anything below.
- **The analytics service holds no SQL.** It composes repository calls into
  API-shaped results.
- **The repository holds all SQL and all arithmetic.** There is exactly one
  place to look when a number is wrong.
- **The agent holds no database access.** It can only reach data through
  registered tools, which reach the database through the same repository the
  REST API uses. The dashboard and the chat therefore cannot disagree.
- **The classifier is the only writer**, on its own connection and role.

---

## 2. The two views

`vw_worklog_analysis` joins `work_item_capability`. A work item classified into
*n* capabilities produces *n* rows per worklog. That is correct for capability
analysis and wrong for everything else — `SUM(hours)` over it double-counts.

`vw_worklog_base` (migration 007) is the deduplicated companion: exactly one row
per `worklog_id`, plus a `has_capability` flag for classification-coverage
reporting. Every total, breakdown, comparison and iteration summary reads from
it.

Capability *filters* on those queries are applied as an `EXISTS` subquery
against `work_item_capability`, not by switching views, so filtering by
capability narrows the row set without multiplying it.

One consequence is surfaced in the UI and in the agent prompt: capability totals
can overlap and must not be summed into a grand total.

### Why `work_item` has no hard foreign key

The widget writes `worklog_record` and is not part of this project. Work-item
sync is asynchronous, so a worklog can legitimately exist before its work item
has been synced. A hard FK would make the widget's writes fail on a race we do
not control, and this application is read-only so it cannot be the enforcer
anyway.

Instead the relationship is logical: views `LEFT JOIN`, so a worklog is never
hidden because its metadata is late, and `vw_data_quality_issues` reports it as
`MISSING_WORK_ITEM`. Migration 002 documents the `NOT VALID` promotion path for
when the widget team can guarantee ordering.

---

## 3. Grounding: how a number reaches the user

1. The user asks a question.
2. `detect_intent` runs deterministic patterns first. Forecasts, personnel
   judgements, cost questions and bare superlatives are caught here — before any
   model call — and produce a refusal or a clarifying question.
3. Otherwise the agent loop starts. The model sees the system prompt, a note
   describing the carried-over filters, a short transcript window and the new
   question, plus the tool schemas.
4. The model chooses a tool. `execute_tool` validates the arguments against a
   Pydantic model with `extra="forbid"`, merges conversation context, resolves
   any relative date phrase into explicit dates, and calls the analytics
   service.
5. PostgreSQL computes the sums, counts, percentages and differences. The
   repository rounds and returns structured JSON.
6. The result is appended to the conversation as a `tool` message, and also
   recorded in the response's `analytics` block and `evidence`.
7. The model writes prose around those figures.

The model never sees a database connection, never receives raw SQL and never
produces a number that is not already in a tool result. If a tool fails, the
error text it receives is deliberately non-technical — no view names, no SQL —
so a failure cannot leak schema detail into the answer.

### Why no text-to-SQL

A generic "chat with your database" implementation would let the model generate
arbitrary queries. That fails on three counts here: correctness (it would
happily sum the capability-grain view), security (an escape hatch for arbitrary
SQL on a shared database), and reproducibility (the same question could produce
different SQL on different days). Fourteen fixed tools cover the question space
in the evaluation set while keeping every query path reviewable.

---

## 4. Conversation context

Two things are kept per conversation:

- **Structured context** — resolved filter values only (`ConversationContext`).
  This is what makes *"how much of that was QA?"* work: the new `memo_code` is
  merged over the existing `capability`, and the tool re-queries the database.
- **A short transcript window** — six turns, for pronoun resolution.

Tool *results* are deliberately not retained beyond the turn that produced them.
Every answer re-queries, so a stale number can never be recycled into a later
answer.

Explicit arguments always beat carried context. One special case: naming an
iteration clears an inherited date window, since otherwise *"and in Sprint 23?"*
after *"last week"* would silently return only the overlap.

---

## 5. Capability classification

The taxonomy lives in the database, not in code, so it can be curated without a
deploy. `Taxonomy.validate` is the only gate:

| Model output | Outcome |
|---|---|
| Approved capability and sub-capability | Accepted, canonicalised for case |
| Approved capability, invented sub-capability | Sub dropped, parent kept — the coarse label is still correct |
| Invented capability | Rejected, confidence forced to 0, nothing persisted |
| `UNCLASSIFIED` | Abstention honoured |
| Work item with too little signal | Never sent to the model at all |

The prompt's capability list is generated from the same database rows used for
validation, so the prompt and the constraint cannot drift apart.

Persistence upserts with `WHERE is_human_reviewed = false`, so a re-run cannot
undo a human correction. `override_capability` / `override_sub_capability` store
the correction without discarding what the model originally said, which keeps
the classifier's accuracy measurable over time.

---

## 6. Data quality

Eleven checks live in a view, not in Python, so results are always live and
there is no second implementation to drift. A worklog can appear more than once
if it triggers several checks.

Problems are reported, never corrected, and never folded into the analytics
numbers. If 2 hours are logged against a work item that has not synced, the
total includes those 2 hours and the data-quality endpoint explains why the
title is missing. Silently excluding them would understate reality.

---

## 7. Performance

Indexes were chosen from the query shapes the application actually issues, and
each carries its rationale in migration 004: the five single-column indexes on
`worklog_record` cover the filter dimensions; `(work_date, memo_code)` covers the
common "date range grouped by memo" shape behind the time-distribution chart;
`work_item(iteration_path)` and `work_item(work_item_type)` cover the iteration
picker and type breakdown.

Result sets are capped in the repository, not only at the API edge, so a tool
call cannot bypass the limit. `date_trunc` units come from a whitelist.
Statement timeout is set per connection.

Caching is intentionally not implemented yet. The risk it creates — a user
logging time and not seeing it — outweighs the benefit at this data volume. When
it is needed, the safe candidates are the iteration list, the master data and
the taxonomy, none of which change with time entry. Dashboard summaries should
only be cached with an explicit, short TTL, and capability classifications
invalidated on `classified_date`.
