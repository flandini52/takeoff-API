<#
.SYNOPSIS
    Avvia Streamlit dalla root del repo, in primo piano. Pensato per
    l'attivita' pianificata LandiniDashboard (trigger "All'avvio", riavvio
    automatico in caso di errore — vedi register_tasks.ps1).

.DESCRIPTION
    Se Streamlit termina per qualsiasi motivo esce con codice diverso da
    zero, cosi' l'Utilita' di pianificazione lo riavvia da sola (nessuna
    logica di retry qui dentro: la delega interamente all'attivita'
    pianificata). NIENTE --server.runOnSave: un aggiornamento del codice
    non fa ripartire l'app da solo, solo un riavvio esplicito (deploy.ps1
    o un riavvio manuale dell'attivita') la fa ripartire con le modifiche.
#>

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_lib.ps1")

$RepoRoot = Get-RepoRoot
$LogDir = Join-Path $RepoRoot "logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

# Rotazione semplice: un file di log al giorno, cancella quelli piu'
# vecchi di 14 giorni ad ogni avvio.
$RetentionDays = 14
Get-ChildItem -Path $LogDir -Filter "dashboard-*.log" -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$RetentionDays) } |
    Remove-Item -Force -ErrorAction SilentlyContinue

$LogFile = Join-Path $LogDir ("dashboard-{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))

Set-Location $RepoRoot

Add-Content -Path $LogFile -Value ("[{0}] Avvio Streamlit..." -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))

& uv run streamlit run "streamlit\app\main.py" `
    --server.address 0.0.0.0 `
    --server.port 8501 `
    --server.headless true `
    *>> $LogFile

$exitCode = $LASTEXITCODE
Add-Content -Path $LogFile -Value ("[{0}] Streamlit terminato (exit code {1})." -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $exitCode)

if ($exitCode -eq 0) {
    # Streamlit non dovrebbe mai uscire "con successo" in questo scenario
    # (deve girare all'infinito): tratto anche questo come un errore, cosi'
    # l'attivita' pianificata lo riavvia invece di considerarlo concluso.
    exit 1
}
exit $exitCode
