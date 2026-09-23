-- Initial database setup.
--
-- No business schema yet (clienti, commesse, attività, tecnici, fatture, ...)
-- by design: it will be added once the gestionale API and the data it
-- exposes are documented (see README, "Importante: non fare assunzioni
-- sul gestionale"). This file exists so docker-entrypoint-initdb.d has
-- something to run on first startup, and so future migrations have a
-- place to live (e.g. 002_customers.sql, 003_jobs.sql, ...).

SELECT 'database initialized' AS status;
