<#
.SYNOPSIS
    Deploy "pull": se origin/main ha nuovi commit, aggiorna il working
    tree, risincronizza le dipendenze e riavvia Streamlit. Torna alla
    versione precedente da solo se qualcosa va storto.

.DESCRIPTION
    Pensato per l'attivita' pianificata LandiniDashboard-Deploy (ogni 3
    minuti). Usa un lock file per non avere due deploy in parallelo. Non
    tocca mai .env, logs/ o backups/: sono in .gitignore, quindi
    `git reset --hard` non li tocca (git non modifica mai i file
    ignorati).

    Il riavvio di Streamlit NON usa Stop/Start-ScheduledTask su un'altra
    attivita' pianificata (richiederebbe permessi che un account di
    servizio non amministratore normalmente non ha): termina invece il
    processo Streamlit in esecuzione. L'attivita' pianificata
    LandiniDashboard lo rileva come "terminato" e lo riavvia da sola
    (RestartOnFailure, configurato da register_tasks.ps1) — a questo
    account basta poter terminare un proprio processo, sempre permesso.
#>

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_lib.ps1")

$RepoRoot = Get-RepoRoot
$LogDir = Join-Path $RepoRoot "logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$LogFile = Join-Path $LogDir "deploy.log"
$LockFile = Join-Path $LogDir "deploy.lock"

function Write-DeployLog {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $LogFile -Value $line
    Write-Host $line
}

function Restart-Dashboard {
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe' or Name = 'streamlit.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match [regex]::Escape($RepoRoot) } |
        ForEach-Object {
            try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {}
        }
}

function Wait-DashboardHealthy {
    # RestartInterval dell'attivita' LandiniDashboard e' 1 minuto (vedi
    # register_tasks.ps1): il riavvio puo' impiegare fino a quel tempo
    # piu' il boot di Streamlit, quindi il retry copre ~90 secondi.
    for ($i = 0; $i -lt 18; $i++) {
        Start-Sleep -Seconds 5
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8501/_stcore/health" -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -eq 200) { return $true }
        } catch {
            # Non ancora pronto, ritento.
        }
    }
    return $false
}

# 6. Lock per evitare due deploy in parallelo. Un lock piu' vecchio di 10
#    minuti e' considerato orfano (deploy precedente interrotto) e viene
#    ignorato, non blocca per sempre.
if (Test-Path $LockFile) {
    $lockAge = (Get-Date) - (Get-Item $LockFile).LastWriteTime
    if ($lockAge.TotalMinutes -lt 10) {
        Write-DeployLog "Un altro deploy sembra gia' in corso (lock di $([int]$lockAge.TotalMinutes) min fa), esco."
        exit 0
    }
    Write-DeployLog "Lock trovato ma vecchio di $([int]$lockAge.TotalMinutes) minuti: probabile deploy interrotto, lo ignoro."
}
New-Item -ItemType File -Path $LockFile -Force | Out-Null

try {
    Set-Location $RepoRoot

    # 1. Fetch e confronto con origin/main.
    git fetch origin main *>> $LogFile
    if ($LASTEXITCODE -ne 0) {
        Write-DeployLog "git fetch fallito (exit $LASTEXITCODE), esco senza modificare nulla."
        exit 1
    }

    $currentHash = (git rev-parse HEAD).Trim()
    $remoteHash = (git rev-parse origin/main).Trim()

    if ($currentHash -eq $remoteHash) {
        # Nessun nuovo commit: gira ogni 3 minuti, non logghiamo rumore.
        exit 0
    }

    Write-DeployLog "Nuova versione trovata: $currentHash -> $remoteHash. Avvio il deploy."

    # 2. Aggiorna il working tree e le dipendenze.
    git reset --hard origin/main *>> $LogFile
    if ($LASTEXITCODE -ne 0) {
        Write-DeployLog "git reset --hard fallito (exit $LASTEXITCODE). Interrotto."
        exit 1
    }

    uv sync --frozen *>> $LogFile
    if ($LASTEXITCODE -ne 0) {
        Write-DeployLog "uv sync fallito (exit $LASTEXITCODE) sulla nuova versione. Torno a $currentHash."
        git reset --hard $currentHash *>> $LogFile
        uv sync --frozen *>> $LogFile
        Write-DeployLog "Tornato a $currentHash dopo un uv sync fallito su $remoteHash."
        exit 1
    }

    # 3. Riavvia Streamlit e attende che torni sano.
    Write-DeployLog "Riavvio Streamlit..."
    Restart-Dashboard

    # 4. Health check.
    if (Wait-DashboardHealthy) {
        Write-DeployLog "Deploy riuscito: $remoteHash e' in esecuzione (health check OK)."
        exit 0
    }

    # 5. Rollback automatico.
    Write-DeployLog "Health check fallito dopo il deploy di $remoteHash. Torno a $currentHash."
    git reset --hard $currentHash *>> $LogFile
    uv sync --frozen *>> $LogFile
    Restart-Dashboard

    if (Wait-DashboardHealthy) {
        Write-DeployLog "Rollback a $currentHash riuscito (health check OK). ATTENZIONE: il deploy di $remoteHash NON funzionava, verifica manualmente prima di ritentare."
    } else {
        Write-DeployLog "ERRORE GRAVE: anche dopo il rollback a $currentHash l'health check fallisce. Serve intervento manuale."
    }
    exit 1
}
finally {
    Remove-Item -Path $LockFile -Force -ErrorAction SilentlyContinue
}
