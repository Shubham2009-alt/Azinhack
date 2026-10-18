# Database migrations

The backend uses Alembic revisions for schema evolution.

## Local development

From `backend/`:

```bash
python -m pip install -r requirements.txt
alembic upgrade head
```

The development server applies migrations automatically by default. Set `RUN_MIGRATIONS_ON_STARTUP=true` only for a single-instance environment.

## Production deployment

Set `APP_ENV=production` and a PostgreSQL `DATABASE_URL`. Before starting or scaling application replicas, run this once as a release step:

```bash
cd backend
alembic upgrade head
```

Do not run the migration command concurrently from multiple API replicas. Back up production data before the first migration. The initial baseline adopts existing MVP databases by adding the known legacy columns and creates missing tables; review it against a staging copy before applying it to a database with valuable data.

Use a non-owner database role for the running API where practical, with migration privileges restricted to the release job. Avoid printing the connection URL because it can contain credentials.
