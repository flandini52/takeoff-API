# employee_deadlines_certificates

Small ELT pipeline that pulls employee certificates/deadlines (Wiki module)
from Takeoff CRM into a local SQLite DB, via a JSON staging layer designed
to be loaded into a cloud DB later with no changes.

## Pipeline

```
Takeoff CRM API
      │  extract_to_json.py
      ▼
data/raw/<contact_id>_wiki_folders.json      (untouched API response, per contact — lineage/debug)
data/staging/subjects.jsonl                  (normalized, one JSON object per line)
data/staging/deadlines_certificates.jsonl    (normalized, one JSON object per line)
data/staging/_manifest.json                  (run metadata: when, which contacts, row counts)
      │  load_sqlite.py
      ▼
db/employee_deadlines_certificates.db        (local SQLite — subjects + deadlines_certificates tables)
      │  app/main.py (read-only, Streamlit)
      ▼
   http://localhost:8501
```

- **Extract** (`extract_to_json.py`) is the only part that talks to the API.
- **Staging JSONL** is the contract between extract and load: NDJSON (one
  record per line) is what every cloud loader consumes natively (`bq load`,
  Snowflake `COPY INTO`, Postgres/Mongo bulk import, S3 → Athena/Glue, ...).
- **Load** (`load_sqlite.py`) is the only SQLite-specific part. To move to a
  cloud DB, replace this one script with an equivalent loader for that
  target — extraction doesn't change.

## Data model

- `subjects`: one row per Wiki folder. Usually an employee (`subject_category
  = 'Personale'`, `is_employee = 1`), but Takeoff also uses folders for other
  things (e.g. `VEICOLI` for vehicle deadlines) — kept rather than dropped,
  filter on `is_employee` to scope to people only.
- `deadlines_certificates`: one row per Wiki element (a certificate,
  training, or deadline), linked to its `subject_id`. `expiry_date` and
  `document_filename` are pulled out of the API's generic properties list
  and normalized (dates to ISO 8601); `raw_properties` keeps the original
  properties JSON as an escape hatch for anything not modeled in a column.

See [schema.sql](schema.sql) for exact columns/types.

## Usage

```bash
# from the employee_deadlines_certificates/ directory
uv run python extract_to_json.py "LANDINI SRL" --exact
uv run python load_sqlite.py
```

Re-running both steps is safe/idempotent: extraction overwrites the JSON
files, and loading uses `INSERT OR REPLACE` keyed on the Takeoff ids.

## Dashboard

```bash
uv run streamlit run app/main.py
```

Opens at http://localhost:8501. Shows, for each person: their certificates
and deadlines with a status (Scaduto / Entro 30 giorni / Entro 90 giorni /
Valido / Senza scadenza), plus KPIs, a status-distribution chart, and an
upcoming-expirations table. Filters in the sidebar (person search, category,
status, employees-only toggle) and a "🔄 Aggiorna dati" panel that re-runs
`extract_to_json.py` + `load_sqlite.py` for a given company name without
leaving the browser.

It only reads from `db/employee_deadlines_certificates.db` (except for that
refresh button) — re-run the extract/load steps above to update the data it
shows.

## Querying the local DB

```bash
sqlite3 db/employee_deadlines_certificates.db
```

```sql
-- Upcoming expirations for employees only, soonest first
SELECT s.subject_name, d.element_name, d.expiry_date, d.document_filename
FROM deadlines_certificates d
JOIN subjects s ON s.subject_id = d.subject_id
WHERE s.is_employee = 1 AND d.expiry_date IS NOT NULL
ORDER BY d.expiry_date;
```

## Note

`data/` and `db/` contain real personal data (employee names, document
filenames, expiry dates) and are gitignored — don't remove that entry.
