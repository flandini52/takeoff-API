<#
.SYNOPSIS
    Supervisore di Streamlit: lo avvia dalla root del repo e, se termina per
    qualsiasi motivo, lo rilancia dopo 5 secondi. Non termina mai da solo.
    Pensato per l'attivita' pianificata LandiniDashboard (trigger
    "All'avvio" - vedi register_tasks.ps1).

.DESCRIPTION
    Perche' un ciclo qui dentro: l'opzione "Se l'attivita' non riesce,
    riavvia ogni..." dell'Utilita' di pianificazione scatta SOLO se
    l'attivita' non riesce a partire, NON quando il programma parte e poi
    esce con un codice di errore. Quindi il riavvio di Streamlit (dopo un
    crash o dopo che deploy.ps1 lo termina per caricare il codice nuovo) lo
    gestisce questo script. RestartOnFailure resta configurato solo come
    ulteriore rete di sicurezza, nel caso muoia il supervisore stesso.

    Protezione anti-loop: se Streamlit esce piu' di 5 volte in 2 minuti
    (es. codice rotto che crasha all'avvio) aspetta 60 secondi prima di
    riprovare e lo scrive nel log, invece di rilanciarlo a raffica.

    NIENTE --server.runOnSave: il codice nuovo viene caricato solo da un
    riavvio esplicito (deploy.ps1 termina il processo Streamlit, questo
    supervisore lo rilancia con il codice aggiornato).
#>

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_lib.ps1")

$RepoRoot = Get-RepoRoot
$LogDir = Join-Path $RepoRoot "logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

$RetentionDays = 14
$RestartDelaySeconds = 5
$BurstWindowSeconds = 120
$BurstMaxRestarts = 5
$BurstPauseSeconds = 60

function Get-DashboardLogFile {
    # Un file di log al giorno: ricalcolato a ogni avvio di Streamlit, cosi'
    # un supervisore che gira per settimane non scrive sempre sullo stesso
    # file.
    return Join-Path $LogDir ("dashboard-{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))
}

function Write-SupervisorLog {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path (Get-DashboardLogFile) -Value $line
}

function Remove-OldLogs {
    Get-ChildItem -Path $LogDir -Filter "dashboard-*.log" -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$RetentionDays) } |
        Remove-Item -Force -ErrorAction SilentlyContinue
}

Set-Location $RepoRoot
Write-SupervisorLog "Supervisore avviato (PID $PID)."

$recentExits = @()

while ($true) {
    Remove-OldLogs
    $logFile = Get-DashboardLogFile
    Write-SupervisorLog "Avvio Streamlit..."

    # Un errore di avvio (es. uv non trovato) non deve far terminare il
    # supervisore: lo intercetto, lo scrivo nel log e riprovo.
    try {
        & uv run streamlit run "streamlit\app\main.py" `
            --server.address 0.0.0.0 `
            --server.port 8501 `
            --server.headless true `
            *>> $logFile
        $exitCode = $LASTEXITCODE
    }
    catch {
        $exitCode = -1
        Write-SupervisorLog ("Errore nell'avvio di Streamlit: {0}" -f $_.Exception.Message)
    }

    Write-SupervisorLog ("Streamlit terminato (exit code {0})." -f $exitCode)

    # Anti-loop: conta le uscite negli ultimi $BurstWindowSeconds secondi.
    $now = Get-Date
    $recentExits = @($recentExits | Where-Object { ($now - $_).TotalSeconds -le $BurstWindowSeconds }) + @($now)

    if ($recentExits.Count -gt $BurstMaxRestarts) {
        Write-SupervisorLog ("ATTENZIONE: Streamlit e' uscito {0} volte in {1} secondi. Attendo {2} secondi prima di riprovare. Controlla questo log." -f `
            $recentExits.Count, $BurstWindowSeconds, $BurstPauseSeconds)
        Start-Sleep -Seconds $BurstPauseSeconds
        $recentExits = @()
    }
    else {
        Start-Sleep -Seconds $RestartDelaySeconds
    }
}
