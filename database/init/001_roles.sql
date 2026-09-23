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

\getenv etl_writer_password ETL_WRITER_PASSWORD
\getenv dashboard_reader_password DASHBOARD_READER_PASSWORD

CREATE ROLE etl_writer WITH LOGIN PASSWORD :'etl_writer_password';
CREATE ROLE dashboard_reader WITH LOGIN PASSWORD :'dashboard_reader_password';

GRANT USAGE ON SCHEMA public TO etl_writer, dashboard_reader;
