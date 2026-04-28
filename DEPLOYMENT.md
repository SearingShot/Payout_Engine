# Free Deployment Guide

This project can run on free tiers with:

- Render Free Web Service for Django, React, Celery worker, and Celery beat in one container.
- Supabase Free project for Postgres.
- Upstash Redis Free database for Celery broker/result backend.

Current deployment:

```text
https://payout-engine-pehx.onrender.com/
```

## 1. Create the free data services

Create a Supabase project and copy a **pooler** Postgres connection string, not the direct connection string.

Do not use a URL like this on Render:

```text
postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres
```

Supabase direct database hosts are IPv6-only on free projects, and Render free web services cannot reach them. Use the Supabase pooler URL instead. It should look like one of these:

```text
postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require
postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require
```

Prefer the session pooler on port `5432` for Django if Supabase gives you both options. The transaction pooler on port `6543` can also work for simple app traffic.

Create an Upstash Redis database and copy the Redis URL. Use the TLS URL if provided.

## 2. Deploy on Render

Push this repo to GitHub, then in Render create a new Blueprint from the repo. Render will read `render.yaml` and create one free Docker web service.

Set these environment variables on the Render service:

- `DATABASE_URL`: your Supabase Postgres connection string
- `REDIS_URL`: your Upstash Redis URL

Keep:

- `DEBUG=False`
- `POSTGRES_SSL_REQUIRE=True`
- `ALLOWED_HOSTS=.onrender.com`
- `CSRF_TRUSTED_ORIGINS=https://*.onrender.com`

## 3. First deploy behavior

On container start, `scripts/start.sh` runs migrations and seeds demo data only if the database has no merchants. It then starts:

- Gunicorn web server
- Celery worker
- Celery beat scheduler

This keeps the app within one free Render web service. For production, split Celery worker and beat into separate services.

## Free-tier caveats

Render free web services can spin down after inactivity and have monthly usage limits. Supabase Free has a 500 MB database limit. Upstash Redis Free has command and storage limits. This setup is suitable for demos and portfolio use, not production money movement.
