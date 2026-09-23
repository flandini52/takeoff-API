<#
.SYNOPSIS
    Inizializza il database landini_dashboard su PostgreSQL 16 (Windows,
    localhost:5435): crea il database e i ruoli etl_writer/dashboard_reader
    eseguendo in ordine gli script di database/init/.

.DESCRIPTION
    Idempotente: se il database o i ruoli esistono gia', non fallisce e non
    cancella nulla (vedi database/init/001_roles.sql). Chiede la password
    dell'utente postgres a runtime, non la salva mai. Le password dei ruoli
    applicativi (etl_writer, dashboard_reader) vengono lette da .env.

    Si ferma subito se .env non punta a localhost:5435 — vedi
    Assert-LocalDashboardDb in _lib.ps1: questo server ha altri database
    CRITICI (SILOG su 5432, TeamPortal su 5433/5434) che non vanno mai
    toccati.

.NOTES
    Da eseguire da C:\landini-dashboard\deploy\windows con un utente che ha
    accesso a psql.exe e, la prima volta, la password dell'utente postgres.
#>

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_lib.ps1")

Write-Host "== Inizializzazione database landini_dashboard ==" -ForegroundColor Cyan

$RepoRoot = Get-RepoRoot
$PsqlExe = Get-PostgresBinPath "psql.exe"
$InitDir = Join-Path $RepoRoot "database\init"
$EnvFile = Join-Path $RepoRoot ".env"

$envValues = Read-EnvFile -Path $EnvFile
Assert-LocalDashboardDb -EnvValues $envValues

$dbHost = $envValues["DB_HOST"]
$dbPort = $envValues["DB_PORT"]
$dbName = $envValues["DB_NAME"]
$etlWriterPassword = $envValues["ETL_WRITER_PASSWORD"]
$dashboardReaderPassword = $envValues["DASHBOARD_READER_PASSWORD"]

if ([string]::IsNullOrWhiteSpace($dbName)) { throw "DB_NAME non impostato in .env." }
if ([string]::IsNullOrWhiteSpace($etlWriterPassword)) { throw "ETL_WRITER_PASSWORD non impostato in .env." }
if ([string]::IsNullOrWhiteSpace($dashboardReaderPassword)) { throw "DASHBOARD_READER_PASSWORD non impostato in .env." }

if (-not (Test-Path $InitDir)) { throw "Cartella database/init non trovata: $InitDir" }
$sqlFiles = Get-ChildItem -Path $InitDir -Filter "*.sql" | Sort-Object Name
if ($sqlFiles.Count -eq 0) { throw "Nessuno script .sql trovato in $InitDir" }

$postgresPassword = Read-SecurePasswordAsPlainText -Prompt "Password dell'utente 'postgres' su ${dbHost}:${dbPort}"

$env:PGPASSWORD = $postgresPassword
$env:ETL_WRITER_PASSWORD = $etlWriterPassword
$env:DASHBOARD_READER_PASSWORD = $dashboardReaderPassword

try {
    # 1. Crea il database se non esiste gia' (CREATE DATABASE non supporta
    #    IF NOT EXISTS in Postgres: controllo prima con una query).
    Write-Host "Verifico se il database '$dbName' esiste..."
    $dbExists = & $PsqlExe -h $dbHost -p $dbPort -U postgres -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$dbName';"
    if ($LASTEXITCODE -ne 0) {
        throw "Connessione a Postgres fallita (host=$dbHost porta=$dbPort utente=postgres). Controlla la password e che il servizio postgresql-x64-16 sia avviato."
    }
    if ($dbExists.Trim() -eq "1") {
        Write-Host "Database '$dbName' gia' esistente, non lo ricreo." -ForegroundColor Yellow
    } else {
        Write-Host "Creo il database '$dbName'..."
        & $PsqlExe -h $dbHost -p $dbPort -U postgres -d postgres -c "CREATE DATABASE $dbName;"
        if ($LASTEXITCODE -ne 0) { throw "Creazione del database '$dbName' fallita." }
    }

    # 2. Esegue in ordine gli script di database/init/ (gli stessi usati
    #    dall'init del container Docker, nessuna copia) — sono idempotenti:
    #    ruoli con \if/\gset, tabelle/indici con IF NOT EXISTS, grant
    #    naturalmente idempotenti.
    foreach ($file in $sqlFiles) {
        Write-Host "Eseguo $($file.Name)..."
        & $PsqlExe -h $dbHost -p $dbPort -U postgres -d $dbName -v ON_ERROR_STOP=1 -f $file.FullName
        if ($LASTEXITCODE -ne 0) {
            throw "Script $($file.Name) fallito (exit code $LASTEXITCODE). Interrotto: nessuno script successivo e' stato eseguito."
        }
    }

    Write-Host "== Inizializzazione completata ==" -ForegroundColor Green
}
finally {
    # Non lasciare le password nell'ambiente del processo piu' del necessario.
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:\ETL_WRITER_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:\DASHBOARD_READER_PASSWORD -ErrorAction SilentlyContinue
    $postgresPassword = $null
}
