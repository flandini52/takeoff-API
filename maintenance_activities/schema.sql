-- Schema for the maintenance_activities local staging DB.
--
-- Source: Takeoff CRM "Activities" module (GET /api/activities, filtered by
-- activityType and a date range). One row = one planned maintenance
-- activity assigned to one worker at one client site.
--
-- Flat by design: unlike the Wiki module (folder -> element -> properties),
-- an Activity is already a single record with everything needed (worker,
-- site, planned dates, completion flag), so one table is enough. Plain
-- types and explicit columns so it maps 1:1 onto Postgres/BigQuery/
-- Snowflake later.

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

    address              TEXT,
    city                 TEXT,
    province              TEXT,
    postal_code           TEXT,
    full_address          TEXT,
    latitude              REAL,
    longitude             REAL,

    planned_start        TEXT,                  -- ISO 8601 datetime
    planned_end          TEXT,                  -- ISO 8601 datetime
    duration_minutes     INTEGER,

    completed            INTEGER NOT NULL,       -- boolean (0/1)
    confirmed            INTEGER NOT NULL,
    approved             INTEGER NOT NULL,

    source_system        TEXT NOT NULL DEFAULT 'takeoff_crm',
    extracted_at          TEXT NOT NULL          -- ISO 8601 UTC timestamp of the extraction run
);

CREATE INDEX IF NOT EXISTS idx_activities_assigned_user ON activities(assigned_user_id);
CREATE INDEX IF NOT EXISTS idx_activities_planned_start ON activities(planned_start);
CREATE INDEX IF NOT EXISTS idx_activities_completed ON activities(completed);
CREATE INDEX IF NOT EXISTS idx_activities_city ON activities(city);
