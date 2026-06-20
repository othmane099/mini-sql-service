# mini-sql-service

## Overview

mini-sql-service lets you connect to a database and interact with it using plain English. Ask questions, get SQL, and generate interactive charts — all through a REST API and a conversational AI agent.

A ready-made frontend is available at **[mini-sql-service-frontend](https://github.com/othmane099/mini-sql-service-frontend)**.

![AI SQL Agent - chart generation](img/ai_sql_agent1.png)
![AI SQL Agent - query interface](img/ai_sql_agent2.png)

## Architecture

The service is built around three layers:

1. **Connections** — store and manage database credentials; schema introspection happens here.
2. **Queries** — translate natural language into SQL, execute it, explain it, and log the history.
3. **Chart Agent** — a multi-agent pipeline driven by a WebSocket. It orchestrates two sub-agents:
   - **SQL sub-agent**: generates SQL → executes it → reflects on errors (up to 3 retries).
   - **Chart sub-agent**: plans a chart type → generates Chart.js HTML → validates it → writes it to disk (up to 2 retries).

Agent state is persisted per `session_id` using a checkpointer, so conversations survive reconnections.

## Tech Stack

| Layer | Technology |
|---|---|
| Web framework | FastAPI |
| Agent orchestration | LangGraph |
| LLM | Azure OpenAI (gpt-4o) |
| ORM / async DB | SQLAlchemy + asyncpg |
| Migrations | Alembic |
| Dependency injection | dependency-injector |
| Logging | structlog |
| Server | Gunicorn + Uvicorn |
| Charts | Chart.js v4 |

## Prerequisites

- Docker & Docker Compose **or** Python 3.14+ with [uv](https://github.com/astral-sh/uv) and [just](https://github.com/casey/just)
- An Azure OpenAI deployment (or any OpenAI-compatible endpoint)

## Getting Started

### 1. Configure environment

Copy the example and fill in your values:

```bash
cp .env.example .env   # or create .env manually
```

Required variables:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/postgres
LLM_API_KEY=<your-api-key>
LLM_ENDPOINT=<your-azure-openai-endpoint>
LLM_API_VERSION=2024-10-21
LLM_MODEL=gpt-4o
```

### 2. Run with Docker Compose (recommended)

```bash
docker compose up
```

This starts PostgreSQL on port `5433` and the API on port `8000`. Migrations run automatically on startup.

### 3. Run locally (development)

```bash
just install   # install dependencies
just migrate   # apply database migrations
just dev       # start uvicorn with hot reload on 0.0.0.0:8000
```

---

## API Usage Guide

Base URL: `http://localhost:8000/api/v1`

### Step 1 — Create a database connection

```bash
curl -s -X POST http://localhost:8000/api/v1/connections \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-db",
    "host": "db.example.com",
    "port": 5432,
    "database": "myapp",
    "username": "alice",
    "password": "secret"
  }'
```

**Response:**

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "my-db",
  "db_type": "postgresql",
  "host": "db.example.com",
  "port": 5432,
  "database": "myapp",
  "username": "alice",
  "created_at": "2026-06-14T10:00:00Z",
  "updated_at": "2026-06-14T10:00:00Z"
}
```

Save the `id` — you'll use it in all subsequent requests.

### Step 2 — Test the connection

```bash
curl -s -X POST http://localhost:8000/api/v1/connections/<connection_id>/test
```

**Response:**

```json
{ "success": true, "message": "Connection successful" }
```

### Step 3 — Generate charts with the AI agent

Connect via WebSocket and start a conversation. The agent will ask which database to use, what data to visualize, and then produce a chart automatically.

```bash
# Install wscat if needed: npm install -g wscat
wscat -c ws://localhost:8000/api/v1/agent/chart
```

**Send a message:**

```json
{ "session_id": "my-session-1", "message": "Show me monthly revenue for 2025" }
```

**The server streams events:**

```json
{ "type": "message",    "content": "Which connection should I use?" }
{ "type": "tool_start", "name": "run_sql" }
{ "type": "tool_end",   "name": "run_sql",   "content": "{\"columns\":[...],\"rows\":[...]}" }
{ "type": "tool_start", "name": "generate_chart" }
{ "type": "tool_end",   "name": "generate_chart", "content": "{\"chart_id\":\"abc123\",\"url\":\"...\"}" }
{ "type": "message",    "content": "Chart ready: http://localhost:8000/api/v1/agent/charts/abc123" }
{ "type": "done" }
```

| Event type | Meaning |
|---|---|
| `message` | Agent text reply |
| `tool_start` | A tool is being invoked |
| `tool_end` | Tool completed successfully |
| `tool_error` | Tool failed |
| `error` | Protocol or connection error |
| `done` | Turn complete |

**List all generated charts:**

```bash
curl http://localhost:8000/api/v1/agent/charts
```

**Open a chart in the browser:**

```
http://localhost:8000/api/v1/agent/charts/<chart_id>
```

---

## Other Features

### Explore database schema

Returns all tables, columns, primary keys, and foreign keys for a connection.

```bash
curl http://localhost:8000/api/v1/connections/<connection_id>/schema
```

### Generate SQL from natural language

Translates a plain-English question into a SELECT statement using the LLM.

```bash
curl -s -X POST http://localhost:8000/api/v1/connections/<connection_id>/query \
  -H "Content-Type: application/json" \
  -d '{ "question": "How many orders were placed last month?" }'
```

### Execute SQL directly

Runs a SQL statement against the target database. Only `SELECT` statements are accepted; execution runs in a read-only transaction with a 30-second timeout and a 1000-row cap.

```bash
curl -s -X POST http://localhost:8000/api/v1/connections/<connection_id>/execute \
  -H "Content-Type: application/json" \
  -d '{ "sql": "SELECT id, name FROM users LIMIT 10" }'
```

### Explain a SQL query

Asks the LLM to describe in plain English what a given SQL statement does.

```bash
curl -s -X POST http://localhost:8000/api/v1/connections/<connection_id>/explain \
  -H "Content-Type: application/json" \
  -d '{ "sql": "SELECT COUNT(*) FROM orders WHERE status = '\''shipped'\''" }'
```

### View generated charts

Charts are served as self-contained HTML files:

```bash
# List all charts (sorted by newest first)
curl http://localhost:8000/api/v1/agent/charts

# Open a specific chart
curl http://localhost:8000/api/v1/agent/charts/<chart_id>
```

### Query history

Retrieve a paginated log of all `GENERATE`, `EXECUTE`, and `EXPLAIN` events for a connection.

```bash
curl "http://localhost:8000/api/v1/connections/<connection_id>/history?event_type=GENERATE"
```

### Request correlation IDs

Every response includes an `X-Request-ID` header containing a UUID. Use it to correlate structured log entries (emitted by structlog) with specific API calls.

---

## Configuration Reference

All settings are loaded from `.env`. Required fields have no default.

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | — | SQLAlchemy async DSN for the service's own PostgreSQL database |
| `LLM_API_KEY` | — | Azure OpenAI API key |
| `LLM_ENDPOINT` | — | Azure OpenAI endpoint URL |
| `LLM_API_VERSION` | — | API version (e.g. `2024-10-21`) |
| `LLM_MODEL` | `gpt-4o` | Deployment name |
| `LLM_TIMEOUT` | `30` | LLM request timeout (seconds) |
| `LLM_MAX_TOKENS_SQL` | `512` | Max tokens for SQL generation |
| `LLM_MAX_TOKENS_AGENT` | `1024` | Max tokens for agent replies |
| `QUERY_MAX_ROWS` | `1000` | Row cap per query execution |
| `QUERY_STATEMENT_TIMEOUT` | `30` | Query timeout (seconds) |
| `BASE_URL` | `http://localhost:8000` | Public base URL (used in chart URLs) |
| `DEBUG` | `TRUE` | Enables private-IP connections when `TRUE` |
| `LOG_LEVEL` | `INFO` | Log level |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `DATABASE_POOL_SIZE` | `5` | SQLAlchemy connection pool size |
| `DATABASE_POOL_TTL` | `1200` | Pool connection TTL (seconds) |
| `DATABASE_POOL_PRE_PING` | `true` | Test connections before use |

---

## Project Structure

```
mini-sql-service/
├── src/
│   ├── main.py              # App factory, middleware, routers
│   ├── config.py            # Settings (pydantic-settings)
│   ├── connections/         # Connection CRUD, schema introspection
│   ├── queries/             # SQL generation, execution, explanation
│   ├── history/             # Query audit log
│   └── chart_agent/
│       ├── api.py           # WebSocket + chart serving endpoints
│       ├── graph.py         # Main ReAct agent graph
│       ├── tools.py         # Agent tools
│       └── agents/
│           ├── sql_agent.py   # SQL sub-agent (generate → execute → reflect)
│           └── chart_agent.py # Chart sub-agent (plan → generate → validate → write)
├── alembic/                 # Database migrations
├── charts/                  # Generated chart HTML files
├── Dockerfile
├── docker-compose.yml
└── justfile                 # Dev task runner
```
