# Deploy su Windows Server (produzione)

Guida passo-passo per installare la V1 della Landini Dashboard sul server Windows Server 2019 aziendale (domain controller), **senza Docker**. Docker/`docker-compose*.yml` restano solo per lo sviluppo locale e per un'eventuale futura migrazione a un server Linux in cloud (vedi il [README](README.md#migrazione-al-cloud)).

> **Prima di iniziare, leggi la sezione [Cosa NON toccare](#cosa-non-toccare)**: questo server ospita anche altri database critici (SILOG, TeamPortal) che non vanno mai sfiorati.

## Indice

1. [Prerequisiti (già installati)](#1-prerequisiti-già-installati)
2. [Clone del repo](#2-clone-del-repo)
3. [Configurazione `.env`](#3-configurazione-env)
4. [Inizializzazione del database](#4-inizializzazione-del-database)
5. [Firewall](#5-firewall)
6. [Account di servizio](#6-account-di-servizio)
7. [Permessi NTFS](#7-permessi-ntfs)
8. [Registrazione delle attività pianificate](#8-registrazione-delle-attività-pianificate)
9. [Verifica finale](#9-verifica-finale)
10. [Rollback manuale](#10-rollback-manuale)
11. [Applicare una migrazione dello schema](#11-applicare-una-migrazione-dello-schema)
12. [Disinstallazione completa](#12-disinstallazione-completa)
13. [Cosa NON toccare](#cosa-non-toccare)

---

## 1. Prerequisiti (già installati)

Sul server sono già presenti:

- **Python 3.13** in `C:\Program Files\Python313` (per tutti gli utenti)
- **uv** (gestore pacchetti/ambienti Python)
- **Git**
- **PostgreSQL 16** in `C:\Program Files\PostgreSQL\16`, servizio `postgresql-x64-16`, **porta 5435**, `listen_addresses='localhost'`

Verifica rapida che tutto risponda prima di procedere:

```powershell
& "C:\Program Files\Python313\python.exe" --version
uv --version
git --version
Get-Service postgresql-x64-16
```

## 2. Clone del repo

Il repo è **pubblico**: nessuna chiave SSH/token necessaria.

```powershell
git clone https://github.com/flandini52/takeoff-API.git C:\landini-dashboard
cd C:\landini-dashboard
git checkout main
```

## 3. Configurazione `.env`

```powershell
Copy-Item .env.example .env
notepad .env
```

Compila (vedi i commenti in `.env.example` per il dettaglio di ogni variabile):

```text
DASHBOARD_ENV=production
ENABLE_SCADENZE=false          # resta false finché non c'è il login (V2)

DB_HOST=localhost
DB_PORT=5435
DB_NAME=landini_dashboard
DB_USER=postgres               # o l'utente admin scelto in fase di installazione di PostgreSQL
DB_PASSWORD=                   # non serve: init_db.ps1/migrate.ps1 la chiedono a runtime, non la salvano qui

ETL_WRITER_PASSWORD=<scegli una password forte>
DASHBOARD_READER_PASSWORD=<scegli un'altra password forte>

TAKEOFF_BASE_URL=https://webapi.takeoffcrm.com
TAKEOFF_API_KEY=<chiave reale Takeoff CRM>

BACKUP_DIR=Z:\lavori\backup-dashboard\
```

`.env` **non va mai committato** (è in `.gitignore`) — resta solo su questo server.

## 4. Inizializzazione del database

```powershell
cd C:\landini-dashboard
.\deploy\windows\init_db.ps1
```

Chiede la password dell'utente `postgres` (non viene mai salvata), poi crea il database `landini_dashboard` e i ruoli `etl_writer`/`dashboard_reader` eseguendo in ordine gli script di `database\init\`. Lo script si ferma subito se `.env` non punta a `localhost:5435` — è una misura di sicurezza esplicita per non rischiare mai di toccare gli altri database del server. È idempotente: rilanciarlo su un database già inizializzato non cancella nulla.

Poi installa le dipendenze Python:

```powershell
uv sync --frozen
```

## 5. Firewall

```powershell
.\deploy\windows\firewall.ps1
```

Apre la porta TCP 8501 in ingresso, **solo per il profilo Dominio** (non raggiungibile da fuori la rete aziendale). Idempotente.

## 6. Account di servizio

Le attività pianificate (sezione 8) girano tutte sotto uno **stesso account di servizio non amministratore** — un utente di dominio standard dedicato (es. `LANDINI\svc-dashboard`) o un gMSA (group Managed Service Account).

### Diritto necessario: "Accedi come processo batch"

Le attività pianificate con credenziali salvate (come queste, configurate per girare "indipendentemente dal fatto che l'utente abbia eseguito l'accesso") richiedono che l'account abbia il diritto utente **"Accedi come processo batch"** (*Log on as a batch job*, `SeBatchLogonRight`) — **non** "Accesso come servizio" (*Log on as a service*, `SeServiceLogonRight`, che serve solo per i Servizi Windows veri e propri, e qui non ne usiamo nessuno: niente NSSM, niente servizi custom, solo Utilità di pianificazione).

Su un domain controller, i diritti utente si assegnano tramite Group Policy (le Local Security Policy locali vengono ignorate sui DC). Passi:

1. Apri **Gestione Criteri di Gruppo** (`gpmc.msc`).
2. Modifica la **Default Domain Controllers Policy** (o una GPO dedicata collegata all'OU dei domain controller, se preferibile non toccare quella di default).
3. `Configurazione computer` → `Impostazioni Windows` → `Impostazioni sicurezza` → `Criteri locali` → `Assegnazione diritti utente`.
4. Apri **"Accedi come processo batch"**, aggiungi l'account di servizio (o il gruppo a cui appartiene).
5. `gpupdate /force` sul domain controller, poi verifica con `whoami /priv` (da una sessione di quell'account) che `SeBatchLogonRight` sia presente.

Non serve nessun altro diritto: l'account non deve essere amministratore, non deve poter fermare/avviare altri servizi, non deve avere accesso a nient'altro che questa cartella (vedi sezione 7). `deploy.ps1` riavvia Streamlit terminando il proprio processo (che possiede): il supervisore `start_dashboard.ps1` lo rilancia dopo circa 5 secondi. Non gestisce un'altra attività pianificata, quindi non servono permessi speciali sulle attività stesse.

## 7. Permessi NTFS

L'account di servizio deve poter leggere/scrivere **solo** dentro `C:\landini-dashboard` (per `git reset --hard`, `uv sync`, scrivere `logs\`, ed eventualmente `logs\backups\` come fallback):

```powershell
$acct = "LANDINI\svc-dashboard"   # sostituisci con l'account scelto
icacls "C:\landini-dashboard" /grant "${acct}:(OI)(CI)M" /T
```

`M` (Modify) basta: non serve `F` (Full control). Se `BACKUP_DIR` punta a un percorso di rete (`Z:\lavori\backup-dashboard\`), assicurati separatamente che lo stesso account abbia scrittura lì.

## 8. Registrazione delle attività pianificate

```powershell
.\deploy\windows\register_tasks.ps1 -ServiceAccount "LANDINI\svc-dashboard"
```

Chiede la password dell'account (non viene mai salvata da questo script — la usa solo per registrare le attività). Crea/aggiorna 4 attività pianificate:

| Nome | Cosa fa | Trigger |
|---|---|---|
| `LandiniDashboard` | Supervisore di Streamlit (`start_dashboard.ps1`): lo avvia e lo rilancia dopo ~5 s se termina | All'avvio del server (ritardo 1 min); nessun limite di durata; una sola istanza. RestartOnFailure solo come rete di sicurezza se l'attività non riesce a partire |
| `LandiniDashboard-Deploy` | Pull da `main` + riavvio se cambiato (`deploy.ps1`) | Ogni 3 minuti e all'avvio del server (ritardo 3 min); durata massima 15 min per esecuzione |
| `LandiniDashboard-ETL` | Estrazione dati da Takeoff CRM (`etl_nightly.ps1`) | Ogni notte alle 02:00 |
| `LandiniDashboard-Backup` | Backup del database (`backup_db.ps1`) | Ogni notte alle 02:30 |

Rilanciare lo script su attività già esistenti le aggiorna (idempotente), non le duplica.

> **Perché un supervisore e non solo "Se l'attività non riesce, riavvia".** Quell'opzione dell'Utilità di pianificazione scatta solo se l'attività *non riesce a partire*, non quando il programma parte e poi termina con un errore. Per questo è `start_dashboard.ps1` a rilanciare Streamlit (dopo un crash o dopo un deploy). Se Streamlit esce più di 5 volte in 2 minuti, il supervisore aspetta 60 secondi prima di riprovare e lo scrive in `logs\dashboard-<data>.log`.

Avvia subito `LandiniDashboard` senza aspettare un riavvio del server:

```powershell
Start-ScheduledTask -TaskName "LandiniDashboard"
```

## 9. Verifica finale

```powershell
# Le 4 attività esistono e sono pronte/in esecuzione
Get-ScheduledTask -TaskName "LandiniDashboard*" | Select-Object TaskName, State

# Streamlit risponde
Invoke-WebRequest http://localhost:8501/_stcore/health -UseBasicParsing

# Log di avvio di Streamlit
Get-Content (Get-ChildItem C:\landini-dashboard\logs\dashboard-*.log | Sort-Object LastWriteTime -Descending | Select-Object -First 1) -Tail 20
```

Apri `http://<hostname-server>:8501` da un altro PC sulla rete aziendale (dominio): dovresti vedere Home e Manutenzioni (Scadenze dipendenti resta nascosta finché `ENABLE_SCADENZE=false`).

Prova anche un ciclo di deploy a vuoto (nessun nuovo commit): dopo al massimo 3 minuti, controlla `logs\deploy.log` — non deve esserci alcuna riga (il deploy esce silenziosamente quando non c'è nulla di nuovo).

## 10. Rollback manuale

Se qualcosa non va e il rollback automatico di `deploy.ps1` non basta (es. serve tornare a una versione più vecchia dell'ultimo commit):

```powershell
cd C:\landini-dashboard
git log --oneline -10          # scegli il commit a cui tornare
git reset --hard <hash-commit>
uv sync --frozen
Get-Process | Where-Object { ($_.Name -eq "python" -or $_.Name -eq "streamlit") -and $_.Path -like "C:\landini-dashboard*" } | Stop-Process -Force
# Il supervisore (attività LandiniDashboard) rilancia Streamlit entro ~5 secondi
```

Per tornare indietro anche sul database, vedi il backup più recente in `BACKUP_DIR` (o nel fallback `logs\backups\`):

```powershell
& "C:\Program Files\PostgreSQL\16\bin\pg_restore.exe" -h localhost -p 5435 -U postgres -d landini_dashboard --clean --if-exists "<percorso-al-.dump>"
```

## 11. Applicare una migrazione dello schema

Quando in futuro si aggiunge un nuovo script numerato in `database\init\` (es. `005_customers.sql`, dopo un `git pull`/deploy automatico che l'ha già portato sul server):

```powershell
cd C:\landini-dashboard
.\deploy\windows\migrate.ps1
```

Fa un backup (`pg_dump`) prima di applicare qualsiasi script nuovo, poi applica solo quelli non ancora applicati (tracciati in `schema_migrations`), fermandosi al primo errore.

## 12. Disinstallazione completa

```powershell
cd C:\landini-dashboard
.\deploy\windows\unregister_tasks.ps1
Get-NetFirewallRule -DisplayName "LandiniDashboard-Streamlit" | Remove-NetFirewallRule
```

Questo ferma e rimuove le attività pianificate e la regola firewall — **non tocca il database** (`landini_dashboard`, i ruoli `etl_writer`/`dashboard_reader`) né la cartella `C:\landini-dashboard`. Per rimuovere anche quelli:

```powershell
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -h localhost -p 5435 -U postgres -c "DROP DATABASE landini_dashboard;"
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -h localhost -p 5435 -U postgres -c "DROP ROLE etl_writer; DROP ROLE dashboard_reader;"
Remove-Item -Recurse -Force C:\landini-dashboard
```

Fallo solo dopo aver confermato che non serve più nulla (backup a parte, che restano in `BACKUP_DIR` finché non li cancelli tu esplicitamente).

---

## Cosa NON toccare

Questo server ospita anche altri sistemi critici, indipendenti da questa dashboard. **Nessuno script di questo repo li tocca mai** (vedi `Assert-LocalDashboardDb` in `deploy\windows\_lib.ps1`, che si ferma se `.env` non punta esplicitamente a `localhost:5435`) — ma vale la pena saperlo anche per chi opera manualmente:

- **Porta 5432**: PostgreSQL 9.4, usato da **SILOG**. Non fermare/riavviare, non connettersi, non modificare la configurazione.
- **Porta 5433**: PostgreSQL di **TeamPortal**.
- **Porta 5434**: **pgbouncer** di TeamPortal.
- **Servizio `postgresql-x64-9.4`**: non fermarlo/riavviarlo mai per errore pensando sia il Postgres 16 della dashboard (nomi simili, versioni diverse).
- **Cartelle `...\PostgreSQL\9.4\` e `...\PostgreSQL\9.4 - Copia\`**: non leggere/scrivere/cancellare nulla lì dentro.
- **`C:\teamportal`**: applicazione TeamPortal, cartella separata.
- **IIS**: se in esecuzione su questo server per altri siti/applicazioni, non modificarne la configurazione, i binding o i pool di applicazioni — questa dashboard non usa IIS (Streamlit ha il proprio server integrato sulla 8501).

Se un qualunque script di questo repo dovesse mai tentare di connettersi a una porta diversa da 5435, o di fermare un servizio diverso da quelli elencati nella sezione 8, **è un bug**: fermati e segnala il problema invece di procedere.
