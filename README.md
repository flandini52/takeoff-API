# Takeoff CRM API extraction

Toolkit for extracting data from [TakeOff CRM](https://webapi.takeoffcrm.com) (TakeOff Integrators API) during the migration, exporting to JSONL or CSV.

Swagger spec: https://webapi.takeoffcrm.com/swagger/v1/swagger.json (UI: https://webapi.takeoffcrm.com/swagger/index.html)

## Structure
- `config.py`: single source of truth for configuration and secrets (`Settings`, via `pydantic-settings`). Loads `.env` automatically and fails fast with a clear error if authentication isn't set.
- `takeoff_client.py`: minimal HTTP client (`TakeoffClient`), handles authentication and raises `TakeoffApiError` on errors. `TakeoffClient.from_settings()` builds it by reading `config.py`.
- `extract_data.py`: generic CLI to export paginated entity lists to JSONL/CSV.
- `pyproject.toml` / `uv.lock`: dependencies and environment, managed with [uv](https://docs.astral.sh/uv/).

## Authentication and secrets
The API accepts one of these methods (see `securitySchemes` in the swagger):
- header `x-api-key: <key>`
- query string `apikey=<key>`
- header `Authorization: Bearer <jwt>`

This client uses `x-api-key` (if you set `TAKEOFF_API_KEY`) or `Bearer` (if you set `TAKEOFF_TOKEN`).

Keys must **never be committed**: they only live in `.env` (already in `.gitignore`), read automatically by `config.py`. In CI/production, replace `.env` with environment variables injected by the orchestrator/secrets manager (e.g. GitHub Actions secrets, Azure Key Vault, AWS Secrets Manager) — `config.py` reads them the same way, no code changes needed.

## Setup
1. Install dependencies and create the virtual environment (`uv` reads `pyproject.toml`/`uv.lock`):
   ```
   uv sync
   ```
2. Copy `.env.example` to `.env` and set:
   - `TAKEOFF_BASE_URL` (default `https://webapi.takeoffcrm.com`)
   - `TAKEOFF_API_KEY` or `TAKEOFF_TOKEN`

## Verify the connection
```
uv run python takeoff_client.py
```
Calls `GET /api/me/infos` and prints the authenticated user: if this works, your credentials are correct.

## Data extraction
```
uv run python extract_data.py <entity> [--take 100] [--max-records N] [--format jsonl|csv] [--output path] [--filter '{"key": "value"}']
```

Supported entities: `contacts`, `jobs`, `activities`, `estimates`, `tasks`, `contracts`, `invoices`.

Examples:
```bash
uv run python extract_data.py contacts --format csv --output contacts.csv
uv run python extract_data.py jobs --max-records 500
uv run python extract_data.py activities --filter '{"lastUpdate": "2026-01-01"}'
```

`--filter` accepts a JSON object that gets merged into the query params (for contacts/jobs/activities/estimates/tasks) or the request body (for contracts/invoices), letting you apply the entity-specific filters documented in the swagger.

## Adding more entities
The API exposes ~195 endpoints (Activities, Contracts, Estimates, Invoices, Tasks, Wiki, Warehouses, etc.). To export more of them, add an entry to the `ENTITIES` dict in `extract_data.py` with `method`, `path`, and `pagination` (`"query"` if skip/take are GET params and the response is `{"value": [...]}`, `"body"` if they're in the POST body and the response is `{"value": {"data": [...]}}`).
