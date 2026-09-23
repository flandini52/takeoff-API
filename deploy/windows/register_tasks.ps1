<#
.SYNOPSIS
    Crea (o aggiorna, se esistono gia') le 4 attivita' pianificate che
    fanno girare la dashboard.

.DESCRIPTION
    - LandiniDashboard: supervisore di Streamlit (start_dashboard.ps1),
      trigger "all'avvio" (ritardo 1 minuto), nessun limite di durata, una
      sola istanza. E' il supervisore a rilanciare Streamlit se termina;
      RestartOnFailure (ogni 1 minuto, 999 volte) copre solo il caso in
      cui non riesca a partire l'attivita' stessa.
    - LandiniDashboard-Deploy: deploy.ps1, ogni 3 minuti e all'avvio.
    - LandiniDashboard-ETL: etl_nightly.ps1, ogni notte alle 02:00.
    - LandiniDashboard-Backup: backup_db.ps1, ogni notte alle 02:30.

    Tutte girano con lo stesso account di servizio (utente di dominio
    standard, es. LANDINI\svc-dashboard, o un gMSA). Quell'account deve
    avere il diritto "Accedi come processo batch" (Log on as a batch job,
    SeBatchLogonRight) - vedi DEPLOY_WINDOWS.md - e permessi NTFS di
    lettura/scrittura solo su questa cartella del repo. Non servono
    permessi di amministratore ne' diritti su altre attivita' pianificate:
    deploy.ps1 riavvia Streamlit terminandone il processo (che possiede) e
    il supervisore lo rilancia, senza fermare/avviare un'attivita' diversa.

    Idempotente: Register-ScheduledTask -Force aggiorna un'attivita' con
    lo stesso nome invece di fallire se esiste gia'.

.PARAMETER ServiceAccount
    Account con cui girano le attivita', es. LANDINI\svc-dashboard.

.EXAMPLE
    .\register_tasks.ps1 -ServiceAccount "LANDINI\svc-dashboard"
#>

param(
    [Parameter(Mandatory)] [string]$ServiceAccount
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_lib.ps1")

$RepoRoot = Get-RepoRoot
$DeployDir = Join-Path $RepoRoot "deploy\windows"

$securePassword = Read-Host -Prompt "Password per $ServiceAccount" -AsSecureString
$bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
    $password = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
}
finally {
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

function New-DashboardTaskAction {
    param([Parameter(Mandatory)] [string]$ScriptName)
    $scriptPath = Join-Path $DeployDir $ScriptName
    if (-not (Test-Path $scriptPath)) { throw "Script non trovato: $scriptPath" }
    return New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`"" `
        -WorkingDirectory $RepoRoot
}

try {
    # --- LandiniDashboard: Streamlit, sempre attivo -------------------------
    Write-Host "Registro LandiniDashboard..."
    $action = New-DashboardTaskAction "start_dashboard.ps1"
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $trigger.Delay = "PT1M"
    $settings = New-ScheduledTaskSettingsSet `
        -RestartCount 999 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -MultipleInstances IgnoreNew `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries
    $settings.ExecutionTimeLimit = "PT0S"   # "Arresta se in esecuzione per piu' di": disattivato
    Register-ScheduledTask -TaskName "LandiniDashboard" -Action $action -Trigger $trigger `
        -Settings $settings -User $ServiceAccount -Password $password -RunLevel Limited -Force | Out-Null

    # --- LandiniDashboard-Deploy: ogni 3 minuti ------------------------------
    Write-Host "Registro LandiniDashboard-Deploy..."
    $action = New-DashboardTaskAction "deploy.ps1"
    # Ripetizione ogni 3 minuti per 10 anni. NON usare
    # -RepetitionDuration ([TimeSpan]::MaxValue): su Windows Server 2016/2019
    # con PowerShell 5.1 fallisce con "value incorrectly formatted or out of
    # range". Un secondo trigger "All'avvio" fa ripartire il ciclo anche
    # dopo un riavvio del server.
    $repeatTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
        -RepetitionInterval (New-TimeSpan -Minutes 3) -RepetitionDuration (New-TimeSpan -Days 3650)
    $startupTrigger = New-ScheduledTaskTrigger -AtStartup
    $startupTrigger.Delay = "PT3M"
    $trigger = @($repeatTrigger, $startupTrigger)
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew
    $settings.ExecutionTimeLimit = "PT15M"   # un deploy bloccato non resta appeso per sempre
    Register-ScheduledTask -TaskName "LandiniDashboard-Deploy" -Action $action -Trigger $trigger `
        -Settings $settings -User $ServiceAccount -Password $password -RunLevel Limited -Force | Out-Null

    # --- LandiniDashboard-ETL: ogni notte alle 02:00 -------------------------
    Write-Host "Registro LandiniDashboard-ETL..."
    $action = New-DashboardTaskAction "etl_nightly.ps1"
    $trigger = New-ScheduledTaskTrigger -Daily -At "02:00"
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName "LandiniDashboard-ETL" -Action $action -Trigger $trigger `
        -Settings $settings -User $ServiceAccount -Password $password -RunLevel Limited -Force | Out-Null

    # --- LandiniDashboard-Backup: ogni notte alle 02:30 ----------------------
    Write-Host "Registro LandiniDashboard-Backup..."
    $action = New-DashboardTaskAction "backup_db.ps1"
    $trigger = New-ScheduledTaskTrigger -Daily -At "02:30"
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName "LandiniDashboard-Backup" -Action $action -Trigger $trigger `
        -Settings $settings -User $ServiceAccount -Password $password -RunLevel Limited -Force | Out-Null

    Write-Host "== 4 attivita' pianificate registrate/aggiornate ==" -ForegroundColor Green
    Write-Host "Verifica con: Get-ScheduledTask -TaskName 'LandiniDashboard*'"
}
finally {
    $password = $null
}
