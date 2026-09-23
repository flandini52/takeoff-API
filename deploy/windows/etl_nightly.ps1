<#
.SYNOPSIS
    Esegue l'ETL completo (activities + deadlines) e logga l'esito.
    Pensato per l'attivita' pianificata LandiniDashboard-ETL (notturna).
#>

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_lib.ps1")

$RepoRoot = Get-RepoRoot
$LogDir = Join-Path $RepoRoot "logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

$RetentionDays = 14
Get-ChildItem -Path $LogDir -Filter "etl-*.log" -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$RetentionDays) } |
    Remove-Item -Force -ErrorAction SilentlyContinue

$LogFile = Join-Path $LogDir ("etl-{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))

Set-Location $RepoRoot

Add-Content -Path $LogFile -Value ("[{0}] Avvio ETL notturno (all)..." -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))

& uv run python -m landini_etl.main all *>> $LogFile
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Add-Content -Path $LogFile -Value ("[{0}] ETL completato con successo." -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
} else {
    Add-Content -Path $LogFile -Value ("[{0}] ETL fallito (exit code {1})." -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $exitCode)
}

exit $exitCode
