# Deployment database decision

## Current behavior

SQLite is the local development database. The FastAPI app selects `backend/arena.db` locally (or `ARENA_DB_PATH`) and `/tmp/arena.db` when `VERCEL` is set. Vercel function instances do not provide a durable shared filesystem contract for this database. `/tmp` data can disappear between cold starts and is not shared by concurrent instances. A deployed demo can therefore lose shopper sessions, associate claims, and receipts; do not treat it as production persistence.

## Production recommendation

Use managed PostgreSQL provisioned through the Vercel Marketplace. Neon is a suitable first evaluation because Vercel documents its Postgres integration and automatic project environment-variable configuration. Supabase and AWS Aurora PostgreSQL are also available Marketplace choices. Select the region near the Vercel function, configure pooled connections, and keep separate development/preview/production databases.

This repository has **not** been switched to PostgreSQL. Its current connection and SQL layer uses SQLite-specific question-mark parameters, `sqlite3.Row`, `INSERT OR IGNORE`, and SQLite schema setup. Before enabling a production database, introduce and test a PostgreSQL adapter/migrations, provision credentials, and validate concurrency/transaction behavior. Do not point the current app at a PostgreSQL URL and expect it to work.

References: [Vercel Postgres](https://vercel.com/docs/postgres), [Vercel Marketplace storage](https://vercel.com/docs/marketplace-storage).
