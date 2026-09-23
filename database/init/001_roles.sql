-- Two roles, one per consumer of this database:
--   etl_writer        — read/write, used by the ETL (etl/app/load/postgres.py)
--   dashboard_reader   — read-only, used by Streamlit (streamlit/app/services/database.py)
--
-- Neither service connects as the Postgres admin user (DB_USER/DB_PASSWORD,
-- i.e. POSTGRES_USER/POSTGRES_PASSWORD below). Passwords come from the
-- environment (ETL_WRITER_PASSWORD / DASHBOARD_READER_PASSWORD in .env),
-- never hardcoded — docker-compose.yml passes the whole .env to the
-- postgres service so psql's \getenv can read them here.
--
-- Table-level grants (SELECT/INSERT/UPDATE for etl_writer, SELECT for
-- dashboard_reader) live next to each CREATE TABLE, in 002/003/004.
--
-- Idempotent (CREATE ROLE has no IF NOT EXISTS in Postgres, unlike CREATE
-- TABLE/INDEX): this file runs both from Docker's init (once, on a fresh
-- volume) and from deploy/windows/init_db.ps1 (which must be safe to
-- re-run against an already-initialized database).

\getenv etl_writer_password ETL_WRITER_PASSWORD
\getenv dashboard_reader_password DASHBOARD_READER_PASSWORD

-- Note: :'var' password substitution does NOT happen inside a dollar-quoted
-- DO $$ ... $$ block (psql treats it as an opaque string), so the
-- idempotency check uses \gset + \if instead of a plpgsql IF, keeping the
-- CREATE ROLE statement itself at the top level where substitution works.

SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'etl_writer') AS etl_writer_exists \gset
\if :etl_writer_exists
\else
    CREATE ROLE etl_writer WITH LOGIN PASSWORD :'etl_writer_password';
\endif

SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dashboard_reader') AS dashboard_reader_exists \gset
\if :dashboard_reader_exists
\else
    CREATE ROLE dashboard_reader WITH LOGIN PASSWORD :'dashboard_reader_password';
\endif

GRANT USAGE ON SCHEMA public TO etl_writer, dashboard_reader;
