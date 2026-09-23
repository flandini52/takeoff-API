<#
.SYNOPSIS
    Regola firewall in ingresso per Streamlit (TCP 8501), solo profilo
    Dominio. Idempotente.
#>

$ErrorActionPreference = "Stop"

# Solo profilo Dominio (rete aziendale) e solo dispositivi della stessa
# sottorete del server (LocalSubnet): anche se per errore la porta 8501
# venisse inoltrata dal router, le richieste da Internet resterebbero
# bloccate.

$RuleName = "LandiniDashboard-Streamlit"

$existing = Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Regola '$RuleName' gia' presente, aggiorno i parametri." -ForegroundColor Yellow
    Set-NetFirewallRule -DisplayName $RuleName -Enabled True -Profile Domain -Direction Inbound `
        -Action Allow -Protocol TCP -LocalPort 8501 -RemoteAddress LocalSubnet
}
else {
    New-NetFirewallRule -DisplayName $RuleName -Description "Landini Dashboard (Streamlit)" `
        -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8501 -Profile Domain `
        -RemoteAddress LocalSubnet -Enabled True | Out-Null
    Write-Host "Regola '$RuleName' creata." -ForegroundColor Green
}
