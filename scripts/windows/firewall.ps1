# À exécuter en Administrateur sur le PC Hôte avant la démonstration : n'autorise que le port du WAF (8080) depuis le
# réseau du point d'accès RESILIENCE-G<n> (192.168.137.0/24), bloque tout le reste venant de ce réseau vers ce PC.
param([string]$Subnet = "192.168.137.0/24")
$ErrorActionPreference = "Stop"
New-NetFirewallRule -DisplayName "Immune - autoriser WAF 8080" -Direction Inbound -Protocol TCP -LocalPort 8080 `
  -RemoteAddress $Subnet -Action Allow -Profile Any | Out-Null
New-NetFirewallRule -DisplayName "Immune - bloquer le reste du hotspot" -Direction Inbound -RemoteAddress $Subnet `
  -Action Block -Profile Any -Enabled True | Out-Null
Write-Host "Règles appliquées : seul le port 8080 (WAF) est joignable depuis $Subnet."
Write-Host "Pour annuler : Remove-NetFirewallRule -DisplayName 'Immune - autoriser WAF 8080','Immune - bloquer le reste du hotspot'"
