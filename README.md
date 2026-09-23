# Landini Dashboard

Dashboard aziendale in Streamlit collegata al gestionale (Takeoff CRM) tramite un livello ETL Python e un database PostgreSQL intermedio. Streamlit non interroga mai il gestionale direttamente: legge solo da PostgreSQL.

## Architettura

```text
GESTIONALE
    │
    │ API
    ▼
Python ETL (src/landini_etl/)
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

- **ETL**: unico componente che parla con l'API del gestionale. Estrae, trasforma e carica i dati in PostgreSQL. Eseguibile indipendentemente dalla dashboard (`docker compose run --rm etl` in sviluppo, un'attività pianificata notturna in produzione).
- **PostgreSQL**: livello intermedio persistente tra gestionale e dashboard. Nessuno schema di business definitivo ancora — verrà aggiunto quando l'API del gestionale sarà documentata.
- **Streamlit**: legge solo da PostgreSQL, tramite `streamlit/app/services/database.py` (connesso come `dashboard_reader`, sola lettura). Nessuna chiamata diretta al gestionale per pagina/utente (per ora — vedi sotto). Il bottone "🔄 Aggiorna dati" in sidebar è l'unica eccezione: chiama `landini_etl.main.run()` **in-process** (non uno shell-out) — `landini_etl` è una dipendenza installata del progetto (vedi `pyproject.toml`), non un pacchetto solo-Docker.

**Deploy**: produzione = Windows Server nativo, senza Docker (vedi [DEPLOY_WINDOWS.md](DEPLOY_WINDOWS.md)). Docker/`docker-compose*.yml` restano per lo sviluppo locale e per una futura migrazione a un server Linux in cloud (vedi [Migrazione al cloud](#migrazione-al-cloud)) — stesso codice, stessa configurazione, stessi comandi in entrambi i casi.

Chiamate API dirette da Streamlit per dati real-time sono introdotte solo dove necessario. Prima eccezione: il download dei certificati PDF nella pagina Scadenze dipendenti (`services/documents.py`) — l'URL del file su Takeoff (Azure Blob SAS) scade dopo ~24h, quindi non può essere estratto una volta dall'ETL e salvato in Postgres; va richiesto in tempo reale al momento del download (`GET /api/wiki/{elementId}`), poi il file viene scaricato e zippato al volo.

**Stato**: migrazione completa per le due entità esistenti. `src/landini_etl/` estrae `activities` e `deadlines` da Takeoff CRM e le carica in PostgreSQL con upsert idempotenti. `streamlit/app/` ha tre pagine (`st.navigation`, le prime due sempre attive, la terza dietro `ENABLE_SCADENZE`): Home (stato infrastruttura + storico `etl_runs`), Manutenzioni e Scadenze dipendenti (porting 1:1 delle vecchie dashboard SQLite). Nessuno schema di business oltre a queste due entità (clienti, commesse, tecnici, fatture, ...) — verrà aggiunto quando servirà, seguendo lo stesso pattern (`extract/` → tabella SQL → `load/` → pagina).

Non c'è ancora autenticazione: `streamlit/app/utils/access.py` espone `require_access()`, chiamata da ogni pagina ma per ora un no-op — il punto in cui aggiungere `st.login()` in futuro senza toccare le pagine.

## Struttura delle cartelle

```text
pyproject.toml / uv.lock    # unica sorgente delle dipendenze (ETL + Streamlit), gestita con uv
docker-compose.yml          # postgres + streamlit (+ etl sotto profilo) — sviluppo locale / cloud
docker-compose.override.yml # solo hot-reload di streamlit/app, solo sviluppo (mai sul server, mai in cloud)
.env / .env.example
deploy/windows/             # script PowerShell per la produzione Windows Server — vedi DEPLOY_WINDOWS.md
database/
└── init/                    # script SQL: usati sia dall'init di Postgres in Docker sia da deploy/windows/init_db.ps1
    ├── 001_roles.sql          # ruoli etl_writer / dashboard_reader
    ├── 002_activities.sql     # tabella activities
    ├── 003_deadlines.sql      # tabelle subjects / deadlines_certificates
    └── 004_etl_runs.sql       # tabella etl_runs (log dei run ETL)
src/landini_etl/            # pacchetto ETL installato dal pyproject — importabile ovunque (Docker, nativo)
├── main.py                  # CLI (python -m landini_etl.main ...) + run(entity, **params) importabile
├── config.py                 # unico modulo di config (DB + Takeoff CRM), usato anche da Streamlit
├── api/
│   └── client.py             # TakeoffClient — unico punto di contatto con il gestionale
├── extract/
│   ├── activities.py         # manutenzioni pianificate
│   └── deadlines.py          # scadenze/certificati dipendenti (Wiki)
├── transform/                # trasformazioni dati (vuota per ora)
├── load/
│   └── postgres.py           # upsert per tabella, lock per entity, log in etl_runs
└── tools/                     # CLI di esplorazione (extract_data.py, extract_wiki.py)
streamlit/
├── Dockerfile              # build context = repo root; installa da pyproject/uv.lock (vedi sopra)
└── app/
    ├── main.py             # entry point: st.set_page_config + st.navigation
    ├── pages/
    │   ├── home.py          # stato infrastruttura + ultimi etl_runs
    │   ├── manutenzioni.py   # porting di maintenance_activities/app
    │   └── scadenze.py       # porting di employee_deadlines_certificates/app (dietro ENABLE_SCADENZE)
    ├── components/          # solo le parti davvero uguali tra le due pagine business
    │   ├── kpi.py             # riga di metriche, parametrizzata
    │   ├── charts.py           # bar chart orizzontale, parametrizzata
    │   └── sidebar.py           # bottone "Aggiorna dati" + "ultimo aggiornamento"
    ├── services/
    │   ├── database.py      # unico punto di accesso a PostgreSQL (letture, dashboard_reader)
    │   ├── etl.py             # bridge a landini_etl.main.run(), chiamato dal bottone "Aggiorna dati"
    │   └── documents.py        # download PDF live da Takeoff CRM (unica eccezione "real-time")
    └── utils/
        ├── status.py         # stato Manutenzioni/Scadenze (dipende da "oggi")
        └── access.py           # require_access() — seam per l'autenticazione futura
etl/
└── Dockerfile               # build context = repo root; installa da pyproject/uv.lock (vedi sopra)
```

## Prerequisiti

- **Sviluppo con Docker**: Docker e Docker Compose.
- **Sviluppo/produzione nativi (senza Docker)**: Python 3.11–3.13, [uv](https://docs.astral.sh/uv/), PostgreSQL 16 in ascolto su `localhost:5435` (vedi [Produzione: Windows Server](#produzione-windows-server) per l'installazione guidata).

## Configurazione `.env`

```bash
cp .env.example .env
```

Variabili principali (vedi `.env.example` per l'elenco completo, con i commenti su cosa cambia tra sviluppo e produzione):

```text
DASHBOARD_ENV                                  (development | production)
ENABLE_SCADENZE                                 (mostra la pagina Scadenze dipendenti; default false)

DB_HOST
DB_PORT
DB_NAME
DB_USER / DB_PASSWORD                         (admin/bootstrap — nessun servizio applicativo lo usa)
ETL_WRITER_PASSWORD                            (ruolo etl_writer, letto da src/landini_etl)
DASHBOARD_READER_PASSWORD                       (ruolo dashboard_reader, letto da streamlit/app)

TAKEOFF_BASE_URL
TAKEOFF_API_KEY / TAKEOFF_TOKEN   (impostane una delle due)
```

`.env` viene letto in due modi, a seconda di come giri il progetto (stesso file, stesso codice — vedi `src/landini_etl/config.py`):

- **Docker**: `docker-compose.yml` inietta le variabili nei container come vere variabili d'ambiente (`env_file: .env`); `DB_HOST`/`DB_PORT` vengono comunque sovrascritti a `postgres`/`5432` per i container streamlit/etl (rete Docker interna), indipendentemente da cosa c'è scritto in `.env`.
- **Nativo** (sviluppo locale senza Docker, o produzione Windows): nessun orchestratore inietta variabili, quindi `config.py` legge `.env` direttamente dal filesystem alla root del repo.

`.env` non va mai committato (è in `.gitignore`); nessuna credenziale va scritta nel codice.

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

Avvia solo `postgres` e `streamlit`. L'ETL **non** parte automaticamente (è sotto `profiles: ["etl"]` in `docker-compose.yml`, vedi [Eseguire l'ETL](#eseguire-letl)) — resta lanciabile a mano indipendentemente dagli altri due servizi. In sviluppo, `docker-compose.override.yml` viene unito automaticamente e monta `streamlit/app/` come volume (hot-reload senza rebuild); sul server si deploya solo `docker-compose.yml` (senza l'override), quindi l'immagine gira col codice così com'è stato buildato. Per fermare tutto:

```bash
docker compose down
```

I dati di PostgreSQL sopravvivono a stop/riavvio/ricreazione dei container grazie al volume persistente `postgres_data` (si perdono solo con `docker compose down -v`). Postgres non è esposto all'esterno: la porta è bindata su `127.0.0.1` (vedi [Verificare PostgreSQL](#verificare-postgresql)); solo Streamlit (8501) è raggiungibile da fuori l'host.

## Verificare Streamlit

Apri [http://localhost:8501](http://localhost:8501). Pagine in sidebar:

- **Home**: stato della connessione a PostgreSQL, numero di tabelle nello schema `public`, storico degli ultimi run ETL (`etl_runs`).
- **Manutenzioni**: KPI, % completamento per operaio, dettaglio mancanti, mappa — dati da `activities`.
- **Scadenze dipendenti** (solo se `ENABLE_SCADENZE=true` in `.env` — spenta di default, anche in sviluppo): KPI, distribuzione per stato, dettaglio per persona — dati da `subjects`/`deadlines_certificates`. Include "Download certificati": tabella filtrabile per persona/tipologia con selezione multi-riga, bottone che scarica dal vivo i PDF da Takeoff CRM e li impacchetta in un unico ZIP.

Entrambe le pagine business hanno, in sidebar, un pannello "🔄 Aggiorna dati da Takeoff CRM" con gli stessi input di prima (mese/tipi per Manutenzioni, ragione sociale/corrispondenza esatta per Scadenze) e la data dell'ultimo aggiornamento riuscito. Il bottone esegue l'ETL in-process (non uno shell-out): se un run per la stessa entity è già in corso, mostra "Aggiornamento già in corso" invece di lanciarne uno secondo.

## Verificare PostgreSQL

```bash
docker compose exec postgres psql -U $DB_USER -d $DB_NAME -c "\dt"    # tabelle create dagli script di init
docker compose exec postgres psql -U $DB_USER -d $DB_NAME -c "\du"    # ruoli (landini, etl_writer, dashboard_reader)
```

oppure, da un client esterno **sulla stessa macchina** (la porta è bindata su `127.0.0.1`, non raggiungibile da remoto), connettersi a `localhost:${DB_PORT}` (default `5435`, stesso numero della produzione Windows — vedi [DEPLOY_WINDOWS.md](DEPLOY_WINDOWS.md)) con le credenziali in `.env`.

## Eseguire l'ETL

L'ETL è sotto `profiles: ["etl"]`, quindi non parte con `docker compose up`; nominarlo esplicitamente lo esegue comunque:

```bash
docker compose run --rm etl uv run python -m landini_etl.main activities --month 2026-09
docker compose run --rm etl uv run python -m landini_etl.main deadlines "LANDINI SRL"
docker compose run --rm etl uv run python -m landini_etl.main all
```

Ogni run: estrae da Takeoff CRM (`api/client.py` + `extract/`), fa upsert idempotente in PostgreSQL (`load/postgres.py`, `INSERT ... ON CONFLICT DO UPDATE` sulle stesse chiavi usate in passato da `INSERT OR REPLACE`), e registra inizio/fine/righe caricate/eventuale errore in `etl_runs` (sostituisce il vecchio `_manifest.json`). Un lock Postgres per entity (`pg_try_advisory_lock`) evita run concorrenti sulla stessa entity: se una è già in corso, la seconda esce subito con un messaggio chiaro invece di lanciarsi in parallelo.

Tool di esplorazione generici (non parte delle pipeline activities/deadlines):

```bash
docker compose run --rm etl uv run python -m landini_etl.tools.extract_data contacts --format csv
docker compose run --rm etl uv run python -m landini_etl.tools.extract_wiki "Landini Srl" --exact
```

## Sviluppo locale nativo (senza Docker)

Stesso codice, stessa configurazione, stessi comandi della produzione Windows (vedi sotto) — utile per sviluppare/debuggare senza Docker, o per riprodurre un problema visto sul server:

```bash
uv sync --frozen
cp .env.example .env   # DB_HOST=localhost, DB_PORT=5435 (vedi i commenti nel file)

# serve un Postgres reale su localhost:5435 — o quello di Docker
# (docker compose up -d postgres, già pubblicato su 5435, vedi sopra),
# o un'installazione nativa (vedi Produzione: Windows Server)

uv run streamlit run streamlit/app/main.py --server.address 0.0.0.0 --server.port 8501 --server.headless true
uv run python -m landini_etl.main activities --month 2026-09
uv run python -m landini_etl.main deadlines "LANDINI SRL"
```

## Test

```bash
uv run pytest
```

Test rapidi, senza rete né database: import di tutti i moduli, parsing della configurazione, calcolo degli stati (Completata/In ritardo/Da fare, Scaduto/Entro 30/90 giorni/Valido), trasformazioni dell'extract su JSON di esempio (nessun dato reale) — vedi `tests/`.

## Produzione: Windows Server

La V1 di produzione gira **nativa su Windows Server 2019** (domain controller aziendale), senza Docker: Streamlit tenuto attivo dall'Utilità di pianificazione di Windows, aggiornamenti tramite un deploy "pull" (attività pianificata ogni 3 minuti che aggiorna da `main` e riavvia, con rollback automatico se l'health check fallisce), ETL e backup del database come attività pianificate notturne. Nessun NSSM, nessun servizio Windows custom, nessun GitHub Actions self-hosted runner.

Guida completa passo-passo (prerequisiti, `.env`, inizializzazione del database, account di servizio, firewall, attività pianificate, verifica, rollback, disinstallazione, e cosa **non** toccare sul server): **[DEPLOY_WINDOWS.md](DEPLOY_WINDOWS.md)**.

Script in [`deploy/windows/`](deploy/windows/): `init_db.ps1`, `migrate.ps1`, `start_dashboard.ps1`, `deploy.ps1`, `etl_nightly.ps1`, `backup_db.ps1`, `register_tasks.ps1` / `unregister_tasks.ps1`, `firewall.ps1`, più `_lib.ps1` con le funzioni condivise (lettura `.env`, controllo di sicurezza che blocca qualunque connessione fuori da `localhost:5435`, ecc.).

## Workflow dev → main

- `dev`: sviluppo. Ogni modifica va qui prima.
- `main`: produzione. `deploy.ps1` sul server segue solo `origin/main` — un push su `main` arriva in produzione entro ~3 minuti (con rollback automatico se l'health check fallisce dopo il deploy).
- Il merge `dev` → `main` è manuale (mai automatico): dopo aver provato le modifiche in sviluppo, chi decide di rilasciare fa il merge (via PR o `git merge`) e lo pusha su `main`.

## Migrazione al cloud

Lo stesso codice, la stessa immagine Docker e lo stesso `docker-compose.yml` usati per lo sviluppo locale sono pensati per diventare, senza modifiche, il deploy su un server Linux in cloud quando la V1 nativa Windows verrà dismessa. Passi previsti:

1. Server Linux con Docker + Docker Compose installati.
2. `git clone` del repo (pubblico, nessuna chiave necessaria).
3. `.env` di produzione cloud (stesse variabili di `.env.example`, password diverse da quelle usate su Windows).
4. Backup del Postgres nativo Windows e ripristino su quello del container:
   ```bash
   # sul server Windows (porta 5435, utente admin di quell'installazione — vedi .env)
   & "C:\Program Files\PostgreSQL\16\bin\pg_dump.exe" -h localhost -p 5435 -U postgres -Fc landini_dashboard > landini_dashboard.dump

   # sul server Linux, dopo "docker compose up -d postgres"
   docker compose cp landini_dashboard.dump postgres:/tmp/landini_dashboard.dump
   docker compose exec postgres pg_restore -U landini -d landini_dashboard --clean --if-exists /tmp/landini_dashboard.dump
   ```
5. `docker compose up -d --build` (senza `docker-compose.override.yml`, che resta solo per lo sviluppo locale).
6. Disattivazione delle attività pianificate di Windows (`deploy/windows/unregister_tasks.ps1`) e dismissione del server Windows solo dopo aver verificato il nuovo ambiente.

Non c'è ancora una data per questa migrazione: per ora la produzione è la V1 nativa Windows Server, vedi [DEPLOY_WINDOWS.md](DEPLOY_WINDOWS.md).
