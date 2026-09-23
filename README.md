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
- **Streamlit**: legge solo da PostgreSQL, tramite `streamlit/app/services/database.py` (connesso come `dashboard_reader`, sola lettura). Nessuna chiamata diretta al gestionale per pagina/utente (per ora — vedi sotto). Il bottone "🔄 Aggiorna dati" in sidebar è l'unica eccezione: chiama `etl.main.run()` **in-process** (non uno shell-out), incluso nell'immagine Streamlit apposta (vedi `streamlit/Dockerfile`).

Chiamate API dirette da Streamlit per dati real-time potranno essere introdotte in futuro, solo dove necessario — non sono presenti in questa prima fase.

**Stato**: migrazione completa per le due entità esistenti. `etl/app/` estrae `activities` e `deadlines` da Takeoff CRM e le carica in PostgreSQL con upsert idempotenti. `streamlit/app/` ha tre pagine (`st.navigation`): Home (stato infrastruttura + storico `etl_runs`), Manutenzioni e Scadenze dipendenti (porting 1:1 delle vecchie dashboard SQLite). Nessuno schema di business oltre a queste due entità (clienti, commesse, tecnici, fatture, ...) — verrà aggiunto quando servirà, seguendo lo stesso pattern (`extract/` → tabella SQL → `load/` → pagina).

Non c'è ancora autenticazione: `streamlit/app/utils/access.py` espone `require_access()`, chiamata da ogni pagina ma per ora un no-op — il punto in cui aggiungere `st.login()` in futuro senza toccare le pagine.

## Struttura delle cartelle

```text
docker-compose.yml       # postgres + streamlit + etl
.env / .env.example
database/
└── init/                    # script eseguiti da Postgres al primo avvio sul volume
    ├── 001_roles.sql          # ruoli etl_writer / dashboard_reader
    ├── 002_activities.sql     # tabella activities
    ├── 003_deadlines.sql      # tabelle subjects / deadlines_certificates
    └── 004_etl_runs.sql       # tabella etl_runs (log dei run ETL)
streamlit/
├── Dockerfile             # build context = repo root, include anche etl/app (vedi sotto)
├── requirements.txt
└── app/
    ├── main.py            # entry point: st.set_page_config + st.navigation
    ├── pages/
    │   ├── home.py         # stato infrastruttura + ultimi etl_runs
    │   ├── manutenzioni.py  # porting di maintenance_activities/app
    │   └── scadenze.py      # porting di employee_deadlines_certificates/app
    ├── components/         # solo le parti davvero uguali tra le due pagine business
    │   ├── kpi.py            # riga di metriche, parametrizzata
    │   ├── charts.py          # bar chart orizzontale, parametrizzata
    │   └── sidebar.py          # bottone "Aggiorna dati" + "ultimo aggiornamento"
    ├── services/
    │   ├── database.py     # unico punto di accesso a PostgreSQL (letture, dashboard_reader)
    │   └── etl.py            # bridge a etl.main.run(), chiamato dal bottone "Aggiorna dati"
    └── utils/
        ├── status.py        # stato Manutenzioni/Scadenze (dipende da "oggi")
        └── access.py          # require_access() — seam per l'autenticazione futura
etl/
├── Dockerfile
├── requirements.txt
└── app/
    ├── main.py           # CLI (python -m app.main ...) + run(entity, **params) importabile
    ├── config.py          # credenziali Takeoff CRM (pydantic-settings)
    ├── api/
    │   └── client.py      # TakeoffClient — unico punto di contatto con il gestionale
    ├── extract/
    │   ├── activities.py  # manutenzioni pianificate
    │   └── deadlines.py   # scadenze/certificati dipendenti (Wiki)
    ├── transform/         # trasformazioni dati (vuota per ora)
    ├── load/
    │   └── postgres.py    # upsert per tabella, lock per entity, log in etl_runs
    └── tools/              # CLI di esplorazione (extract_data.py, extract_wiki.py)
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
DB_USER / DB_PASSWORD                         (admin/bootstrap — nessun servizio applicativo lo usa)
ETL_WRITER_PASSWORD                            (ruolo etl_writer, letto da etl/app)
DASHBOARD_READER_PASSWORD                       (ruolo dashboard_reader, letto da streamlit/app)

TAKEOFF_BASE_URL
TAKEOFF_API_KEY / TAKEOFF_TOKEN   (set one of the two)
```

`DB_HOST` viene sovrascritto a `postgres` da `docker-compose.yml` per i container streamlit/etl (nome del servizio sulla rete Docker) — cambialo solo se esegui quelle app fuori da Docker. `.env` non va mai committato (è in `.gitignore`); nessuna credenziale va scritta nel codice.

### Ruoli PostgreSQL

`database/init/001_roles.sql` crea due ruoli, uno per consumatore:

- `etl_writer` — lettura/scrittura, usato dall'ETL (`SELECT`/`INSERT`/`UPDATE` sulle tabelle, mai `DELETE`)
- `dashboard_reader` — sola lettura, usato da Streamlit

Nessuno dei due servizi si connette come utente admin (`DB_USER`). Le password vengono lette dall'ambiente dallo script di init tramite `\getenv` — non sono mai scritte nello script.

### Ricreare il database in sviluppo

Gli script in `database/init/` vengono eseguiti da Postgres **solo al primo avvio di un volume vuoto** — modificarli non ha effetto su un volume già inizializzato. Per applicarli di nuovo in sviluppo:

```bash
docker compose down -v   # rimuove anche il volume postgres_data: i dati vengono persi
docker compose up -d --build
```

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

Apri [http://localhost:8501](http://localhost:8501). Tre pagine in sidebar:

- **Home**: stato della connessione a PostgreSQL, numero di tabelle nello schema `public`, storico degli ultimi run ETL (`etl_runs`).
- **Manutenzioni**: KPI, % completamento per operaio, dettaglio mancanti, mappa — dati da `activities`.
- **Scadenze dipendenti**: KPI, distribuzione per stato, dettaglio per persona — dati da `subjects`/`deadlines_certificates`.

Entrambe le pagine business hanno, in sidebar, un pannello "🔄 Aggiorna dati da Takeoff CRM" con gli stessi input di prima (mese/tipi per Manutenzioni, ragione sociale/corrispondenza esatta per Scadenze) e la data dell'ultimo aggiornamento riuscito. Il bottone esegue l'ETL in-process (non uno shell-out): se un run per la stessa entity è già in corso, mostra "Aggiornamento già in corso" invece di lanciarne uno secondo.

## Verificare PostgreSQL

```bash
docker compose exec postgres psql -U $DB_USER -d $DB_NAME -c "\dt"    # tabelle create dagli script di init
docker compose exec postgres psql -U $DB_USER -d $DB_NAME -c "\du"    # ruoli (landini, etl_writer, dashboard_reader)
```

oppure, da un client esterno, connettersi a `localhost:${DB_PORT}` (default `5432`) con le credenziali in `.env`.

## Eseguire l'ETL

```bash
docker compose run --rm etl python -m app.main activities --month 2026-09
docker compose run --rm etl python -m app.main deadlines "LANDINI SRL"
docker compose run --rm etl python -m app.main all
```

Ogni run: estrae da Takeoff CRM (`api/client.py` + `extract/`), fa upsert idempotente in PostgreSQL (`load/postgres.py`, `INSERT ... ON CONFLICT DO UPDATE` sulle stesse chiavi usate in passato da `INSERT OR REPLACE`), e registra inizio/fine/righe caricate/eventuale errore in `etl_runs` (sostituisce il vecchio `_manifest.json`). Un lock Postgres per entity (`pg_try_advisory_lock`) evita run concorrenti sulla stessa entity: se una è già in corso, la seconda esce subito con un messaggio chiaro invece di lanciarsi in parallelo.

Tool di esplorazione generici (non parte delle pipeline activities/deadlines):

```bash
docker compose run --rm etl python -m app.tools.extract_data contacts --format csv
docker compose run --rm etl python -m app.tools.extract_wiki "Landini Srl" --exact
```

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
