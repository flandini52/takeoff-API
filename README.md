# Landini Dashboard

Dashboard aziendale in Streamlit collegata al gestionale (Takeoff CRM) tramite un livello ETL Python e un database PostgreSQL intermedio. Streamlit non interroga mai il gestionale direttamente: legge solo da PostgreSQL.

## Architettura

```text
GESTIONALE
    │
    │ API
    ▼
Python ETL (etl/)
    │
    ▼
PostgreSQL (database/)
    │
    ▼
Streamlit (streamlit/)
    │
    ▼
Utenti aziendali
```

- **ETL**: unico componente che parla con l'API del gestionale. Estrae, trasforma e carica i dati in PostgreSQL. Eseguibile indipendentemente dalla dashboard (`docker compose run --rm etl`).
- **PostgreSQL**: livello intermedio persistente tra gestionale e dashboard. Nessuno schema di business definitivo ancora — verrà aggiunto quando l'API del gestionale sarà documentata.
- **Streamlit**: legge solo da PostgreSQL, tramite `streamlit/app/services/database.py`. Nessuna chiamata diretta al gestionale per pagina/utente (per ora — vedi sotto).

Chiamate API dirette da Streamlit per dati real-time potranno essere introdotte in futuro, solo dove necessario — non sono presenti in questa prima fase.

**Fase attuale**: solo infrastruttura. Nessuno schema di business (clienti, commesse, attività, tecnici, fatture, ...) e nessuna pagina/grafico di business — solo una pagina che verifica che Streamlit riesca a connettersi a PostgreSQL. Il client API del gestionale (`etl/app/api/client.py`) usa dati mock chiaramente etichettati come tali, in attesa della documentazione dell'API reale.

## Struttura delle cartelle

```text
docker-compose.yml       # postgres + streamlit + etl
.env / .env.example
database/
└── init/                # script eseguiti da Postgres al primo avvio
streamlit/
├── Dockerfile
├── requirements.txt
└── app/
    ├── main.py           # entry point, pagina di verifica infrastruttura
    ├── pages/             # pagine business (vuota per ora)
    ├── components/        # componenti UI riutilizzabili (vuota per ora)
    ├── services/
    │   └── database.py    # unico punto di accesso a PostgreSQL
    └── utils/             # helper generici (vuota per ora)
etl/
├── Dockerfile
├── requirements.txt
└── app/
    ├── main.py           # entry point, esegue extract → transform → load
    ├── api/
    │   └── client.py      # unico punto di contatto con il gestionale
    ├── transform/         # trasformazioni dati (vuota per ora)
    └── load/
        └── postgres.py    # scrittura in PostgreSQL
```

Il repo contiene anche un toolkit di estrazione dati standalone precedente a questa architettura — vedi [Toolkit di estrazione dati (standalone)](#toolkit-di-estrazione-dati-standalone) più sotto.

## Prerequisiti

- Docker e Docker Compose

## Configurazione `.env`

```bash
cp .env.example .env
```

Variabili principali (vedi `.env.example` per l'elenco completo):

```text
DB_HOST
DB_PORT
DB_NAME
DB_USER
DB_PASSWORD

GESTIONALE_API_URL
GESTIONALE_API_KEY
```

`DB_HOST` viene sovrascritto a `postgres` da `docker-compose.yml` per i container streamlit/etl (nome del servizio sulla rete Docker) — cambialo solo se esegui quelle app fuori da Docker. `.env` non va mai committato (è in `.gitignore`); nessuna credenziale va scritta nel codice.

## Avviare Docker Compose

```bash
docker compose up -d --build
```

Avvia `postgres`, `streamlit` (con hot-reload: `streamlit/app/` è montato come volume) ed esegue anche `etl` una volta come parte dello startup. Per fermare tutto:

```bash
docker compose down
```

I dati di PostgreSQL sopravvivono a stop/riavvio/ricreazione dei container grazie al volume persistente `postgres_data` (si perdono solo con `docker compose down -v`).

## Verificare Streamlit

Apri [http://localhost:8501](http://localhost:8501). La pagina iniziale mostra: titolo, stato della connessione a PostgreSQL, numero di tabelle nello schema `public`, e host/database a cui è connessa. Se la connessione fallisce, mostra l'errore.

## Verificare PostgreSQL

```bash
docker compose exec postgres psql -U $DB_USER -d $DB_NAME -c "SELECT version();"
```

oppure, da un client esterno, connettersi a `localhost:${DB_PORT}` (default `5432`) con le credenziali in `.env`.

## Eseguire l'ETL

```bash
docker compose run --rm etl
```

Esegue `etl/app/main.py`: estrae dati mock dal client del gestionale (`api/client.py`), e verifica che l'ETL possa connettersi a PostgreSQL (`load/postgres.py`). Logga ogni step; errori loggati con stack trace. Nessuna tabella di destinazione esiste ancora — verrà aggiunta insieme al primo caricamento reale, quando l'API del gestionale sarà documentata.

---

# Toolkit di estrazione dati (standalone)

Toolkit per l'estrazione dati da [TakeOff CRM](https://webapi.takeoffcrm.com) (TakeOff Integrators API), precedente all'architettura Landini Dashboard sopra e non ancora integrato con l'ETL/PostgreSQL. Usato per esplorazione dati e per due mini-dashboard SQLite standalone.

Swagger spec: https://webapi.takeoffcrm.com/swagger/v1/swagger.json (UI: https://webapi.takeoffcrm.com/swagger/index.html)

## Struttura
- `config.py`: single source of truth for configuration and secrets (`Settings`, via `pydantic-settings`). Loads `.env` automatically and fails fast with a clear error if authentication isn't set.
- `takeoff_client.py`: minimal HTTP client (`TakeoffClient`), handles authentication and raises `TakeoffApiError` on errors. `TakeoffClient.from_settings()` builds it by reading `config.py`.
- `extract_data.py`: generic CLI to export paginated entity lists to JSONL/CSV.
- `maintenance_activities/` and `employee_deadlines_certificates/`: standalone ELT pipelines + Streamlit dashboards on local SQLite — see their own READMEs.
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
