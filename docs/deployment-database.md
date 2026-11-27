# Deployment database decision

## Current behavior

SQLite is the local development and test database. The FastAPI app selects `backend/arena.db` locally (or `ARENA_DB_PATH`). When `DATABASE_URL` is configured, it uses the psycopg 3 PostgreSQL adapter. On Vercel without that variable, it falls back to `/tmp/arena.db`; that storage is ephemeral and shared neither across function instances nor across cold starts. `/health` reports the database mode and whether persistence is expected.

## Production recommendation

Use managed PostgreSQL provisioned through the Vercel Marketplace. Neon is a suitable first evaluation because Vercel documents its Postgres integration and automatic project environment-variable configuration. Supabase and AWS Aurora PostgreSQL are also available Marketplace choices. Select the region near the Vercel function, configure pooled connections, and keep separate development/preview/production databases.

The repository now includes a PostgreSQL adapter, portable schema setup, and legacy SQLite handoff-token migration. Local tests exercise SQLite only; no PostgreSQL server or deployment credentials were available in this workspace, so production connection, migration, pool/concurrency behavior remain unverified. Configure a managed PostgreSQL `DATABASE_URL` and verify `/health` reports `database_mode: postgresql` and `database_persistent: true` before using a deployment for real sessions. Never rely on Vercel `/tmp` for customer or associate state.

For a deployment, configure the database URL from the managed PostgreSQL provider, keep `ARENA_DEMO_AUTH_ENABLED` false, set `ARENA_CORS_ORIGINS` to the actual customer origin, and use separate preview and production databases. Benchmark ingestion and signed result verification are disabled unless `ARENA_BENCHMARK_INGEST_TOKEN` and `ARENA_RUNNER_VERIFY_KEY` are configured. Those keys must be stored as platform secrets. No associate production identity provider is implemented; demo login is local-only by default.

References: [Vercel Postgres](https://vercel.com/docs/postgres), [Vercel Marketplace storage](https://vercel.com/docs/marketplace-storage).
