# Backend

FastAPI + SQLAlchemy over PostgreSQL. Python 3.12+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env        # set DATABASE_URL
uvicorn app.main:app --reload  # http://localhost:8000/docs
```

## Layout

```
app/
├── main.py             app wiring, error handlers, health
├── config.py           settings from environment; fails fast on missing secrets
├── api/                routers - parse, delegate, return. No business logic.
├── analytics/
│   ├── service.py      composition of repository calls
│   └── metrics.py      pure arithmetic + relative date resolution (no I/O)
├── database/
│   ├── connection.py   read-only engine + separate classifier engine
│   ├── models.py       ORM models mirroring the migrations
│   └── repositories.py ALL SQL and ALL aggregation
├── classification/
│   ├── taxonomy.py     the closed capability list and its validation gate
│   └── classifier.py   AI classifier; the only writer in the codebase
├── agent/
│   ├── agent.py        orchestration loop
│   ├── prompts.py      system prompts
│   ├── tools.py        the 14 controlled tools
│   ├── intent.py       deterministic guardrails + structured intent
│   ├── conversation.py structured context + short transcript window
│   └── llm.py          the only module that knows the model API
└── schemas/            Pydantic request/response contracts
```

## Rules this code follows

1. All SQL lives in `database/repositories.py`.
2. All arithmetic happens in SQL or `analytics/metrics.py` — never in the LLM.
3. Every user- or model-supplied value is a bound parameter.
4. The API/agent connection is read-only; only the classifier writes.
5. The agent reaches data only through `agent/tools.py`.
6. Database errors and stack traces never reach a response body.

## Tests

```bash
pytest                       # unit tests
TEST_DATABASE_URL=postgresql+psycopg://pi:pi@localhost:5432/pi_test \
  ../scripts/init_test_db.sh && pytest
```
