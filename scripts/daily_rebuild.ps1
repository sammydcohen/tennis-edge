# Re-download the daily results datasets and rebuild ratings, features and models.
# Scheduled once a day, before the first odds collection. Logs to data/logs/.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force data/logs | Out-Null
$log = "data/logs/rebuild_$(Get-Date -Format yyyy-MM-dd).log"

uv run python -m tennis_edge.pipeline --tour atp --live --refresh *>> $log
uv run python -m tennis_edge.pipeline --tour wta --live --refresh *>> $log
