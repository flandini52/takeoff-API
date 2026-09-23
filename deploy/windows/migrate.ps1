<#
.SYNOPSIS
    Applica al database landini_dashboard gli script SQL numerati di
    database/init/ non ancora applicati, tenendone traccia in
    schema_migrations. Fa un backup (pg_dump) PRIMA di applicare qualsiasi
    script nuovo.

.DESCRIPTION
    Alla primissima esecuzione su un database gia' inizializzato con
    init_db.ps1, non trova ancora schema_migrations popolata: registra
    come "gia' applicati" tutti gli script .sql attualmente presenti in
    database/init/ (si presume che init_db.ps1 li abbia gia' eseguiti) SENZA
    rieseguirli e senza fare un backup inutile. Da quel momento in poi,
    ogni nuovo script aggiunto a database/init/ (es. 005_qualcosa.sql)
    verra' rilevato come pendente ed applicato, uno alla volta, in ordine,
    fermandosi al primo errore.

    Stesso controllo di sicurezza di init_db.ps1: si ferma se .env non
    punta a localhost:5435.
#>

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_lib.ps1")

Write-Host "== Migrazione schema landini_dashboard ==" -ForegroundColor Cyan

$RepoRoot = Get-RepoRoot
$PsqlExe = Get-PostgresBinPath "psql.exe"
$PgDumpExe = Get-PostgresBinPath "pg_dump.exe"
$InitDir = Join-Path $RepoRoot "database\init"
$EnvFile = Join-Path $RepoRoot ".env"

$envValues = Read-EnvFile -Path $EnvFile
Assert-LocalDashboardDb -EnvValues $envValues

$dbHost = $envValues["DB_HOST"]
$dbPort = $envValues["DB_PORT"]
$dbName = $envValues["DB_NAME"]

if ([string]::IsNullOrWhiteSpace($dbName)) { throw "DB_NAME non impostato in .env." }
if (-not (Test-Path $InitDir)) { throw "Cartella database/init non trovata: $InitDir" }

$postgresPassword = Read-SecurePasswordAsPlainText -Prompt "Password dell'utente 'postgres' su ${dbHost}:${dbPort}"
$env:PGPASSWORD = $postgresPassword

try {
    # 1. Tabella di tracciamento delle migrazioni gia' applicate.
    & $PsqlExe -h $dbHost -p $dbPort -U postgres -d $dbName -v ON_ERROR_STOP=1 -c `
        "CREATE TABLE IF NOT EXISTS schema_migrations (filename TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now());"
    if ($LASTEXITCODE -ne 0) { throw "Creazione di schema_migrations fallita." }

    $appliedRaw = & $PsqlExe -h $dbHost -p $dbPort -U postgres -d $dbName -tAc "SELECT filename FROM schema_migrations ORDER BY filename;"
    if ($LASTEXITCODE -ne 0) { throw "Lettura di schema_migrations fallita." }
    $applied = @($appliedRaw -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" })

    $allFiles = @(Get-ChildItem -Path $InitDir -Filter "*.sql" | Sort-Object Name)
    if ($allFiles.Count -eq 0) { throw "Nessuno script .sql trovato in $InitDir" }

    if ($applied.Count -eq 0) {
        # Bootstrap: si presume che init_db.ps1 abbia gia' applicato tutti
        # gli script attualmente presenti in database/init/. Li registro
        # come gia' applicati senza rieseguirli e senza fare un backup.
        Write-Host "Prima esecuzione di migrate.ps1: registro come gia' applicati gli script esistenti (init_db.ps1 li ha gia' eseguiti)." -ForegroundColor Yellow
        foreach ($file in $allFiles) {
            & $PsqlExe -h $dbHost -p $dbPort -U postgres -d $dbName -v ON_ERROR_STOP=1 -c `
                "INSERT INTO schema_migrations (filename) VALUES ('$($file.Name)') ON CONFLICT DO NOTHING;"
            if ($LASTEXITCODE -ne 0) { throw "Registrazione di $($file.Name) in schema_migrations fallita." }
        }
        Write-Host "== Nessuna migrazione da applicare in questa esecuzione ==" -ForegroundColor Green
        exit 0
    }

    $pending = @($allFiles | Where-Object { $applied -notcontains $_.Name })

    if ($pending.Count -eq 0) {
        Write-Host "== Nessuna migrazione nuova da applicare ==" -ForegroundColor Green
        exit 0
    }

    Write-Host ("Migrazioni da applicare: " + ($pending.Name -join ", "))

    # 2. Backup PRIMA di applicare qualsiasi script nuovo.
    $backupDir = Get-BackupDir -EnvValues $envValues -RepoRoot $RepoRoot
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupFile = Join-Path $backupDir "pre-migrate-$timestamp.dump"
    Write-Host "Backup pre-migrazione: $backupFile"
    & $PgDumpExe -h $dbHost -p $dbPort -U postgres -Fc -f $backupFile $dbName
    if ($LASTEXITCODE -ne 0) { throw "Backup pre-migrazione fallito: interrotto senza applicare nessuna migrazione." }

    # 3. Applica le migrazioni pendenti, una alla volta, in ordine,
    #    fermandosi al primo errore (nessun rollback automatico: il
    #    backup appena fatto e' il punto di ripristino manuale).
    foreach ($file in $pending) {
        Write-Host "Applico $($file.Name)..."
        & $PsqlExe -h $dbHost -p $dbPort -U postgres -d $dbName -v ON_ERROR_STOP=1 -f $file.FullName
        if ($LASTEXITCODE -ne 0) {
            throw "Migrazione $($file.Name) fallita (exit code $LASTEXITCODE). Database NON ripristinato automaticamente: usa il backup $backupFile per un rollback manuale (vedi DEPLOY_WINDOWS.md)."
        }
        & $PsqlExe -h $dbHost -p $dbPort -U postgres -d $dbName -v ON_ERROR_STOP=1 -c `
            "INSERT INTO schema_migrations (filename) VALUES ('$($file.Name)') ON CONFLICT DO NOTHING;"
        if ($LASTEXITCODE -ne 0) { throw "Registrazione di $($file.Name) in schema_migrations fallita (lo script SQL era comunque andato a buon fine)." }
    }

    Write-Host "== Migrazione completata: $($pending.Count) script applicati ==" -ForegroundColor Green
}
finally {
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
    $postgresPassword = $null
}
