# Database migrations

Schema is managed by [Alembic](https://alembic.sqlalchemy.org/). The app refuses
to start if the `alembic_version` table is missing — so every new environment
starts the same way.

All commands run from `backend/` with the venv activated.

## First-time setup (fresh DB)

```bash
alembic upgrade head
```

This creates every table defined in `app.models`. The app's startup seed then
populates the Syngene org, departments, agents, and bootstrap super admin.

## After changing a model

```bash
# 1. Generate a migration from the diff between models and the DB
alembic revision --autogenerate -m "add foo to agents"

# 2. Review the generated file in alembic/versions/ — autogenerate is good,
#    not perfect (e.g. column renames look like drop+add).

# 3. Apply it
alembic upgrade head
```

## Other useful commands

```bash
alembic current                 # which revision is the DB at?
alembic history                 # show full revision graph
alembic downgrade -1            # undo the last migration
alembic stamp head              # mark DB as up-to-date without running SQL
                                # (used when the schema was created out-of-band)
```

## How this is wired

- `alembic.ini` leaves `sqlalchemy.url` blank.
- `alembic/env.py` imports `app.core.config.settings` and injects the runtime
  `DATABASE_URL` — so Alembic always matches the app. It also imports
  `app.models` so every model is registered on `Base.metadata` before
  autogenerate runs.
- `env.py` sets `compare_type=True` + `compare_server_default=True`, so column
  type changes are detected (not just adds/drops).

## DATABASE_URL override

Need to point Alembic at a different DB for a one-off (e.g. CI, a test DB)?

```bash
DATABASE_URL="postgresql+psycopg2://user:pw@host/otherdb" alembic upgrade head
```

Pydantic settings picks up the env var and `env.py` passes it to Alembic.
