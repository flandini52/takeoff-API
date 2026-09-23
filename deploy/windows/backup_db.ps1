<#
.SYNOPSIS
    Backup logico (pg_dump) del database landini_dashboard, conservato per
    14 giorni. Pensato per l'attivita' pianificata LandiniDashboard-Backup
    (notturna).

.DESCRIPTION
    Si autentica come etl_writer (ha SELECT su tutte le tabelle
    applicative - vedi database/init/*.sql): non serve la password
    dell'utente admin 'postgres' solo per un backup logico, quindi questo
    script gira senza interazione.

    Destinazione: BACKUP_DIR da .env se raggiungibile, altrimenti un
    fallback locale sotto logs/backups (vedi Get-BackupDir in _lib.ps1).
#>

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_lib.ps1")

$RepoRoot = Get-RepoRoot
$LogDir = Join-Path $RepoRoot "logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$LogFile = Join-Path $LogDir "backup.log"

function Write-BackupLog {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $LogFile -Value $line
    Write-Host $line
}

$RetentionDays = 14

try {
    $PgDumpExe = Get-PostgresBinPath "pg_dump.exe"
    $EnvFile = Join-Path $RepoRoot ".env"
    $envValues = Read-EnvFile -Path $EnvFile
    Assert-LocalDashboardDb -EnvValues $envValues

    $dbHost = $envValues["DB_HOST"]
    $dbPort = $envValues["DB_PORT"]
    $dbName = $envValues["DB_NAME"]
    if ([string]::IsNullOrWhiteSpace($dbName)) { throw "DB_NAME non impostato in .env." }

    $etlWriterPassword = $envValues["ETL_WRITER_PASSWORD"]
    if ([string]::IsNullOrWhiteSpace($etlWriterPassword)) { throw "ETL_WRITER_PASSWORD non impostato in .env." }

    $backupDir = Get-BackupDir -EnvValues $envValues -RepoRoot $RepoRoot
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupFile = Join-Path $backupDir "landini_dashboard-$timestamp.dump"

    Write-BackupLog "Avvio backup verso $backupFile..."

    $env:PGPASSWORD = $etlWriterPassword
    try {
        & $PgDumpExe -h $dbHost -p $dbPort -U etl_writer -Fc -f $backupFile $dbName
        if ($LASTEXITCODE -ne 0) { throw "pg_dump fallito (exit code $LASTEXITCODE)." }
    }
    finally {
        Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
    }

    Write-BackupLog "Backup completato: $backupFile"

    $old = Get-ChildItem -Path $backupDir -Filter "landini_dashboard-*.dump" -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$RetentionDays) }
    foreach ($file in $old) {
        Remove-Item -Path $file.FullName -Force -ErrorAction SilentlyContinue
        Write-BackupLog "Rimosso backup vecchio: $($file.Name)"
    }

    Write-BackupLog "== Backup completato =="
}
catch {
    Write-BackupLog "ERRORE: $_"
    exit 1
}
