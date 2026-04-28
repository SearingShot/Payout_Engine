# Playto Payout Engine

Minimal payout engine for the Playto Founding Engineer Challenge 2026.

## Stack

- Django 5 + Django REST Framework
- PostgreSQL
- Celery + Redis
- React + Tailwind + Vite
- Docker / docker-compose

## Core behavior

- Merchant balance is derived from immutable ledger entries in paise.
- Payout creation is idempotent by merchant-scoped `Idempotency-Key`.
- Concurrent payout requests for the same merchant are serialized with PostgreSQL `SELECT ... FOR UPDATE`.
- Background workers move payouts through `pending -> processing -> completed/failed`.
- Failed payouts atomically return held funds through a reversal ledger credit.

## Local setup with Docker

```bash
docker compose up --build
```

The web service runs migrations and seeds demo data automatically.

Open:

```text
http://localhost:8000
```

API base:

```text
http://localhost:8000/api/v1
```

## Local setup without Docker

Start Postgres and Redis, then create a `.env` file:

```env
DATABASE_URL=postgres://postgres:postgres@localhost:5432/payout_engine
REDIS_URL=redis://localhost:6379/0
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOW_ALL_ORIGINS=True
```

Backend:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

Worker processes:

```bash
celery -A payout_engine worker -l info
celery -A payout_engine beat -l info
```

Frontend in development:

```bash
cd frontend
npm install
npm run dev
```

## Tests

```bash
python manage.py test
```

The important tests are:

- `ConcurrencyTest.test_concurrent_payouts_no_overdraw`
- `IdempotencyTest.test_same_key_returns_same_response`
- `IdempotencyAPITest.test_post_payout_idempotent_via_api`

For the concurrency test, PostgreSQL is the meaningful database because the implementation relies on row-level locks.

## Deployment

See `DEPLOYMENT.md` for the free Render + Supabase + Upstash deployment path.
