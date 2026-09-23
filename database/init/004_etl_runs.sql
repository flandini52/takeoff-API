-- etl_runs: one row per ETL run (per entity), replacing the old
-- data/staging/_manifest.json files. Written by etl/app/load/postgres.py
-- (start_run/finish_run), read by the Streamlit Home page ("Ultimo
-- aggiornamento").

CREATE TABLE IF NOT EXISTS etl_runs (
    id           BIGSERIAL PRIMARY KEY,
    entity       TEXT NOT NULL,                       -- 'activities' | 'deadlines'
    params       JSONB NOT NULL DEFAULT '{}'::jsonb,   -- resolved run params (month, type_ids, company_name, ...)
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at  TIMESTAMPTZ,
    status       TEXT NOT NULL DEFAULT 'running',       -- 'running' | 'success' | 'error'
    rows_loaded  INTEGER,
    error        TEXT
);

CREATE INDEX IF NOT EXISTS idx_etl_runs_entity_started ON etl_runs(entity, started_at DESC);

GRANT SELECT, INSERT, UPDATE ON etl_runs TO etl_writer;
GRANT USAGE, SELECT ON SEQUENCE etl_runs_id_seq TO etl_writer;
GRANT SELECT ON etl_runs TO dashboard_reader;
