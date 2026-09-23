<#
.SYNOPSIS
    Regola firewall in ingresso per Streamlit (TCP 8501), solo profilo
    Dominio. Idempotente.
#>

$ErrorActionPreference = "Stop"

$RuleName = "LandiniDashboard-Streamlit"

$existing = Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Regola '$RuleName' gia' presente, aggiorno i parametri." -ForegroundColor Yellow
    Set-NetFirewallRule -DisplayName $RuleName -Enabled True -Profile Domain -Direction Inbound `
        -Action Allow -Protocol TCP -LocalPort 8501
}
else {
    New-NetFirewallRule -DisplayName $RuleName -Description "Landini Dashboard (Streamlit)" `
        -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8501 -Profile Domain -Enabled True | Out-Null
    Write-Host "Regola '$RuleName' creata." -ForegroundColor Green
}
