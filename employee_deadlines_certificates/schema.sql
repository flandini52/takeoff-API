-- Schema for the employee_deadlines_certificates local staging DB.
--
-- Source: Takeoff CRM "Wiki" module (GET /api/wiki/folders?contactId=...).
-- A Wiki "folder" is a subject (usually an employee, sometimes an asset like
-- a vehicle); a "element" inside it is a certificate/training/deadline; its
-- "properties" carry the expiry date and the attached document.
--
-- Kept intentionally simple and portable (plain types, explicit FKs, no
-- SQLite-only features) so it maps 1:1 onto Postgres/BigQuery/Snowflake
-- later: same two tables, `CREATE TABLE` syntax barely changes.

CREATE TABLE IF NOT EXISTS subjects (
    subject_id       INTEGER PRIMARY KEY,   -- Takeoff wiki folder id
    contact_id       INTEGER NOT NULL,      -- Takeoff contact id (the company, e.g. Landini Srl)
    company_name     TEXT NOT NULL,
    subject_name     TEXT NOT NULL,         -- folder name, e.g. "Arnone Fabrizio" or "VEICOLI"
    subject_category TEXT NOT NULL,         -- folder typology, e.g. "Personale" | "Scadenze varie"
    is_employee      INTEGER NOT NULL,      -- 1 if subject_category = 'Personale', else 0 (boolean, SQLite has no BOOL)
    source_system    TEXT NOT NULL DEFAULT 'takeoff_crm',
    extracted_at     TEXT NOT NULL          -- ISO 8601 UTC timestamp of the extraction run
);

CREATE TABLE IF NOT EXISTS deadlines_certificates (
    element_id         INTEGER PRIMARY KEY,  -- Takeoff wiki element id
    subject_id         INTEGER NOT NULL REFERENCES subjects(subject_id),
    element_name       TEXT NOT NULL,        -- e.g. "Antincendio", "BOLLO DUCATO AB385DX"
    element_category   TEXT,                 -- element typology, e.g. "Formazione" | "Scadenza"
    expiry_date        TEXT,                 -- normalized ISO 8601 date (YYYY-MM-DD), nullable
    document_filename  TEXT,                 -- attached file name, nullable
    raw_properties     TEXT NOT NULL,        -- full properties array as JSON text (escape hatch for anything not modeled above)
    source_system       TEXT NOT NULL DEFAULT 'takeoff_crm',
    extracted_at        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_deadlines_subject_id ON deadlines_certificates(subject_id);
CREATE INDEX IF NOT EXISTS idx_deadlines_expiry_date ON deadlines_certificates(expiry_date);
CREATE INDEX IF NOT EXISTS idx_subjects_is_employee ON subjects(is_employee);
