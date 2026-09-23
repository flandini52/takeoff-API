<#
.SYNOPSIS
    Rimuove le 4 attivita' pianificate della dashboard.

.DESCRIPTION
    Nessun altro effetto: non tocca il database, i file del repo, i log o
    l'account di servizio. Idempotente: un'attivita' gia' assente viene
    semplicemente segnalata, non e' un errore.
#>

$ErrorActionPreference = "Stop"

$TaskNames = @("LandiniDashboard", "LandiniDashboard-Deploy", "LandiniDashboard-ETL", "LandiniDashboard-Backup")

foreach ($name in $TaskNames) {
    $existing = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false
        Write-Host "Rimossa: $name" -ForegroundColor Green
    }
    else {
        Write-Host "Non trovata (gia' rimossa?): $name" -ForegroundColor Yellow
    }
}
