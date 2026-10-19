# PowerShell : génère un .env local (en clair, jamais commité) avec toutes les valeurs attendues
# par docker-compose.yml. Docker Compose le charge automatiquement depuis la racine du projet :
# aucun wrapper n'est nécessaire, "docker compose up -d --build" suffit ensuite.
#   .\scripts\windows\gen_secrets.ps1            .\scripts\windows\gen_secrets.ps1 -Force
param([switch]$Force)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..")
$out = ".env"
if ((Test-Path $out) -and -not $Force) { Write-Host "$out existe déjà. Utilisez -Force pour tout régénérer."; exit 0 }

# Nommée New-SecretValue (pas "R") : PowerShell a un alias intégré "r" -> Invoke-History qui prime
# sur une fonction du même nom, donc un helper nommé "R" ne serait jamais réellement appelé.
function New-SecretValue { $b = New-Object byte[] 24; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); -join ($b | ForEach-Object { $_.ToString("x2") }) }

@"
# Généré par scripts\windows\gen_secrets.ps1 — NE JAMAIS COMMITER (déjà exclu par .gitignore).
# Noms de variables documentés sans valeur dans .env.example.
POSTGRES_PASSWORD=$(New-SecretValue)
API_DB_PASSWORD=$(New-SecretValue)
AUTH_DB_PASSWORD=$(New-SecretValue)
JWT_SECRET=$(New-SecretValue)
INTERNAL_TOKEN=$(New-SecretValue)
ACTUATOR_TOKEN=$(New-SecretValue)
EVENT_HMAC_KEY=$(New-SecretValue)
GRAFANA_PASSWORD=$(New-SecretValue)
DEMO_PASSWORD=$(New-SecretValue)
ATTACKER_PASSWORD=$(New-SecretValue)
PROBE_PASSWORD=$(New-SecretValue)
WEAK_PASSWORD=sunshine1
TRUST_SOURCE_IP=false
NEVER_BAN=
TRAFFIC_RPS=4
ASSISTANT_CHAT_MODEL=qwen2.5:3b-instruct
ASSISTANT_EMBED_MODEL=nomic-embed-text
"@ | Set-Content -Encoding ascii $out

Write-Host "OK : $out créé (secrets en clair, locaux à cette machine, jamais commités)."
Write-Host "WEAK_PASSWORD (compte volontairement faible 'carol', scénario brute-force) est fixe : sunshine1."
Write-Host "Suite : docker compose up -d --build"
