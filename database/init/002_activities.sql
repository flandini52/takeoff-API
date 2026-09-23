-- Activities table (planned maintenance activities), migrated from
-- maintenance_activities/schema.sql (SQLite) to PostgreSQL.
--
-- Source: Takeoff CRM "Activities" module (GET /api/activities, filtered
-- by activityType and a date range). One row = one planned maintenance
-- activity assigned to one worker at one client site.
--
-- Type changes vs the SQLite version ("tipi corretti"): completed /
-- confirmed / approved are BOOLEAN (were 0/1 INTEGER); latitude /
-- longitude are NUMERIC (were REAL); planned_start / planned_end /
-- extracted_at are TIMESTAMPTZ (were TEXT ISO strings). Takeoff CRM's
-- swagger doesn't document a timezone for planned_start/planned_end —
-- assumed to be Italian local time (Landini Srl) until confirmed
-- otherwise; extracted_at is unambiguous (written by the ETL in UTC).

CREATE TABLE IF NOT EXISTS activities (
    activity_id         INTEGER PRIMARY KEY,   -- Takeoff activity id
    activity_type_id    INTEGER NOT NULL,
    activity_type_name  TEXT NOT NULL,          -- e.g. "Manutenzione ordinaria programmata"

    assigned_user_id    INTEGER,
    assigned_user_name  TEXT,                   -- the worker ("operaio")

    contact_id          INTEGER,
    company_name        TEXT,                   -- client

    job_id               INTEGER,
    job_name              TEXT,

    address               TEXT,
    city                  TEXT,
    province              TEXT,
    postal_code           TEXT,
    full_address          TEXT,
    latitude              NUMERIC,
    longitude             NUMERIC,

    planned_start         TIMESTAMPTZ,
    planned_end            TIMESTAMPTZ,
    duration_minutes       INTEGER,

    completed              BOOLEAN NOT NULL,
    confirmed               BOOLEAN NOT NULL,
    approved                 BOOLEAN NOT NULL,

    source_system             TEXT NOT NULL DEFAULT 'takeoff_crm',
    extracted_at               TIMESTAMPTZ NOT NULL   -- UTC timestamp of the extraction run
);

CREATE INDEX IF NOT EXISTS idx_activities_assigned_user ON activities(assigned_user_id);
CREATE INDEX IF NOT EXISTS idx_activities_planned_start ON activities(planned_start);
CREATE INDEX IF NOT EXISTS idx_activities_completed ON activities(completed);
CREATE INDEX IF NOT EXISTS idx_activities_city ON activities(city);

GRANT SELECT, INSERT, UPDATE ON activities TO etl_writer;
GRANT SELECT ON activities TO dashboard_reader;
