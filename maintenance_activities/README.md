# maintenance_activities

Small ELT pipeline + Streamlit dashboard tracking planned "Manutenzione
ordinaria programmata" (ordinary scheduled maintenance) activities from
Takeoff CRM: what's planned for the month, what's been done as of today,
the completion % per worker, what's still missing, and where.

## Pipeline

```
Takeoff CRM API
      │  extract_to_json.py --month YYYY-MM
      ▼
data/raw/<month>_activities.json         (untouched API response for the month — lineage/debug)
data/staging/activities.jsonl            (normalized, one JSON object per line)
data/staging/_manifest.json              (run metadata: when, month, types, row counts)
      │  load_sqlite.py
      ▼
db/maintenance_activities.db             (local SQLite — activities table)
      │  app/main.py (read-only, Streamlit)
      ▼
   http://localhost:8501
```

Same extract/staging-JSONL/load split as the sibling
[employee_deadlines_certificates](../employee_deadlines_certificates)
pipeline, for the same reason: the staging JSONL is the only thing a future
cloud-loading step needs to read, so swapping `load_sqlite.py` for a cloud
loader later doesn't touch extraction.

## Data model

One row per Activity (`activities` table) — already flat in the source API,
no folder/element nesting like the Wiki module. Key columns: `assigned_user_name`
(the worker), `company_name` / `city` / `address` / `latitude` / `longitude`
(the client site), `planned_start` / `planned_end`, `completed`. See
[schema.sql](schema.sql) for all columns.

Activity type defaults to id `16602` ("Manutenzione ordinaria programmata",
confirmed via `GET /api/activitytypes` on the live API) — pass `--types` to
extend to others (e.g. `16441` "Manutenzione a contratto").

Status per activity, computed in the dashboard (not stored — it depends on
"today"):
- **Completata** — `completed = true`
- **In ritardo** — not completed and its planned end date has already passed
- **Da fare** — not completed and its planned date hasn't arrived yet

## Usage

```bash
# from the maintenance_activities/ directory
uv run python extract_to_json.py --month 2026-09
uv run python load_sqlite.py
uv run streamlit run app/main.py
```

Re-running extract + load is safe/idempotent (`INSERT OR REPLACE` keyed on
`activity_id`) — re-run them (or use the dashboard's sidebar "🔄 Aggiorna
dati" panel) whenever activities change in the CRM (e.g. marked completed).

## Dashboard

Opens at http://localhost:8501.

- KPIs: pianificate, completate, % completamento, in ritardo, da fare
- Bar chart + table: % completamento per operaio (colored red/yellow/green
  by completion band), sorted worst-first
- Expandable detail per operaio: exactly which activities are missing, at
  which client/address/city
- "Attività mancanti per posto": table grouped by city + a map of missing
  activities (colored by status) when coordinates are available

Filters in the sidebar: worker search/select, city select.

## Note

`data/` and `db/` contain real client data (company names, addresses) and
are gitignored — don't remove that entry.
