# Transfer Availability & Booking Service

Backend service for a DMC that manages airport transfer bookings. Built with FastAPI, MySQL, SQLAlchemy, and Alembic.

## Project structure

```
app/
├── main.py                     # FastAPI app, middleware, error handlers
├── config.py                   # Pydantic Settings (DB, logging, app)
├── database.py                 # SQLAlchemy engine + session factory
├── enums.py                    # Domain enums (no ORM dependency)
├── models.py                   # SQLAlchemy ORM models
├── schemas.py                  # Pydantic request/response models
├── domain.py                   # Pure business rules (status transitions)
├── exceptions.py               # Domain exceptions (NotFound, Conflict, etc.)
├── error_handlers.py           # Maps domain exceptions → HTTP responses
├── middleware.py               # Request logging middleware
├── routers/
│   ├── vehicles.py             # Vehicle + availability endpoints
│   └── transfers.py            # Transfer lifecycle endpoints
└── services/
    ├── vehicle_service.py      # Vehicle DB logic + availability queries
    ├── transfer_service.py     # Booking lifecycle + status management
    └── notification_service.py # Background confirmation notifications
alembic/versions/
├── 001_initial_schema.py       # Tables + indexes
└── 002_add_transfer_driver_fields.py
tests/
├── unit/
│   ├── test_domain.py          # Status transition rules (no DB)
│   └── test_services.py        # Service layer (domain exceptions)
└── integration/
    └── test_api.py             # Full HTTP stack against real MySQL
```

## How to run locally

### Prerequisites

- Docker and Docker Compose

### Start the full stack

```bash
docker compose up --build
```

This starts MySQL (port 3306), a test MySQL instance (port 3307), runs Alembic migrations, and starts the API on **http://localhost:8000**.

API docs: http://localhost:8000/docs

### Run tests

With the `db-test` container running:

```bash
# Install dev dependencies
pip install -e ".[test]"

# Unit tests (no DB required)
pytest -m unit

# Integration tests (requires the test MySQL on port 3307)
pytest -m integration

# All tests
pytest
```

## Architecture decisions

### Layered architecture

```
Routers → Services → Domain logic
   ↕          ↕
Schemas    Models/DB
```

- **Routers** are thin: parse HTTP, call a service, return a response.
- **Services** own all DB interaction and orchestration. They raise domain exceptions (`NotFoundError`, `ConflictError`, `ValidationError`), never `HTTPException`.
- **Domain** (`domain.py`) contains pure business rules with no dependencies — testable without DB or HTTP.
- **Error handlers** map domain exceptions to structured HTTP responses, keeping HTTP concerns out of business logic.

This means the same service code works behind a CLI, a message consumer, or any other entry point.

### Background tasks

When a transfer is confirmed, a `BackgroundTask` logs a notification. The notification service uses the existing `SessionLocal` factory rather than creating a new engine per invocation (which would leak connection pools under load).

## Index choices and reasoning

### 1. `ix_transfer_vehicle_pickup_status` — composite index on `(vehicle_id, pickup_time, status)`

**Query pattern:** The availability check (`GET /availability`) executes a raw SQL query that filters transfers by `status IN ('CONFIRMED', 'IN_PROGRESS')` and `pickup_time` within a 2-hour window. The booking endpoint (`POST /transfers`) runs a similar per-vehicle conflict check.

**Why this index:** A composite B-tree index with `vehicle_id` as the leading column lets MySQL do an equality match on the vehicle, then a range scan on `pickup_time`, and finally filter on `status` — all within the index. This avoids a full table scan and is significantly faster than three separate single-column indexes that MySQL would need to intersect.

**Why not index on `(status, pickup_time)`?** The status column has very low cardinality (5 values), making it a poor leading column. Starting with `vehicle_id` gives much better selectivity.

### 2. `ix_transfer_pickup_time` — single-column index on `pickup_time`

**Query pattern:** `GET /transfers?date=YYYY-MM-DD` lists all transfers for a given date, filtering only on `pickup_time`.

**Why a separate index:** The composite index above has `vehicle_id` as its leftmost column. Due to MySQL's leftmost-prefix rule, queries that don't filter by `vehicle_id` cannot use that composite index. A standalone index on `pickup_time` ensures the date-listing query uses an index range scan instead of a full table scan.

## Live migration strategy (Part 2)

The migration in `002_add_transfer_driver_fields.py` adds three nullable columns (`driver_name`, `estimated_duration_minutes`, `notes`) to the `transfers` table.

### How to apply safely on a live 24/7 production system

1. **Use online DDL (pt-online-schema-change or gh-ost).** On large tables, a plain `ALTER TABLE ... ADD COLUMN` in MySQL 8.0 is an online operation for adding nullable columns, but it still acquires a metadata lock briefly. For tables with heavy write traffic, tools like `gh-ost` (GitHub's online schema migration tool) perform the change without blocking writes by creating a shadow table, copying rows, and then swapping atomically.

2. **Deploy the migration before the code.** Since all three new columns are nullable, the existing application code — which doesn't reference these columns — will continue to work unchanged after the migration runs. This is the standard "expand then contract" pattern:
   - **Step 1:** Run the Alembic migration to add the columns (backward-compatible — old code ignores them).
   - **Step 2:** Deploy the new application code that reads/writes the new columns.
   - This ordering ensures there's never a moment where the code expects columns that don't exist yet.

3. **Test the migration on a staging replica first.** Run the migration against a copy of the production database to verify timing, lock behavior, and that the application still works correctly before and after.

4. **Monitor.** Watch for metadata lock waits and replication lag during the migration. If using `gh-ost`, monitor its progress and the cutover step.

## API endpoints summary

| Method | Path | Description |
|--------|------|-------------|
| POST | `/vehicles` | Register a new vehicle |
| GET | `/availability?date=&pax_count=&pickup_time=` | Check available vehicles |
| POST | `/transfers` | Create a transfer booking |
| GET | `/transfers/{id}` | Get transfer with status history |
| PATCH | `/transfers/{id}/status` | Update transfer status |
| GET | `/transfers?date=` | List transfers for a date |

## Status transition rules

```
PENDING → CONFIRMED → IN_PROGRESS → COMPLETED
  ↓           ↓
CANCELLED  CANCELLED
```

- Cancellation is only allowed from PENDING or CONFIRMED.
- Transitioning to IN_PROGRESS requires `driver_name` in the request body.
- Every status change is logged in the `transfer_status_history` table.
- When a transfer is confirmed, a background task logs a notification to the `notifications` table.

## Configuration

All settings are configurable via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `mysql+pymysql://app:apppass@localhost:3306/transfers` | SQLAlchemy connection string |
| `DB_POOL_SIZE` | `5` | Connection pool size |
| `DB_MAX_OVERFLOW` | `10` | Max overflow connections |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `DEBUG` | `false` | Debug mode |
