-- subjects / deadlines_certificates tables, migrated from
-- employee_deadlines_certificates/schema.sql (SQLite) to PostgreSQL.
--
-- Source: Takeoff CRM "Wiki" module (GET /api/wiki/folders?contactId=...).
-- A Wiki "folder" is a subject (usually an employee, sometimes an asset
-- like a vehicle); an "element" inside it is a certificate/training/
-- deadline; its "properties" carry the expiry date and attached document.
--
-- Type changes vs the SQLite version ("tipi corretti"): is_employee is
-- BOOLEAN (was 0/1 INTEGER); expiry_date is DATE (was TEXT ISO date —
-- already normalized by extract/deadlines.py, so this is a clean cast);
-- extracted_at is TIMESTAMPTZ (was TEXT). raw_properties is JSONB instead
-- of TEXT: SQLite has no native JSON type so it was stored as a serialized
-- string escape hatch; Postgres does, so JSONB is the "correct type" here
-- (and stays queryable, unlike an opaque TEXT blob).

CREATE TABLE IF NOT EXISTS subjects (
    subject_id       INTEGER PRIMARY KEY,   -- Takeoff wiki folder id
    contact_id       INTEGER NOT NULL,      -- Takeoff contact id (the company, e.g. Landini Srl)
    company_name     TEXT NOT NULL,
    subject_name     TEXT NOT NULL,         -- folder name, e.g. "Arnone Fabrizio" or "VEICOLI"
    subject_category TEXT NOT NULL,         -- folder typology, e.g. "Personale" | "Scadenze varie"
    is_employee      BOOLEAN NOT NULL,      -- true if subject_category = 'Personale'
    source_system    TEXT NOT NULL DEFAULT 'takeoff_crm',
    extracted_at     TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS deadlines_certificates (
    element_id         INTEGER PRIMARY KEY,  -- Takeoff wiki element id
    subject_id         INTEGER NOT NULL REFERENCES subjects(subject_id),
    element_name       TEXT NOT NULL,        -- e.g. "Antincendio", "BOLLO DUCATO AB385DX"
    element_category   TEXT,                 -- element typology, e.g. "Formazione" | "Scadenza"
    expiry_date        DATE,                 -- normalized from dd/mm/yyyy by extract/deadlines.py
    document_filename  TEXT,                 -- attached file name, nullable
    raw_properties     JSONB NOT NULL,       -- full properties array (escape hatch for anything not modeled above)
    source_system       TEXT NOT NULL DEFAULT 'takeoff_crm',
    extracted_at        TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_deadlines_subject_id ON deadlines_certificates(subject_id);
CREATE INDEX IF NOT EXISTS idx_deadlines_expiry_date ON deadlines_certificates(expiry_date);
CREATE INDEX IF NOT EXISTS idx_subjects_is_employee ON subjects(is_employee);

GRANT SELECT, INSERT, UPDATE ON subjects, deadlines_certificates TO etl_writer;
GRANT SELECT ON subjects, deadlines_certificates TO dashboard_reader;
