# Snapshot live odds, re-score upcoming matches, grade started picks, refresh site data.
# Scheduled a few times a day (see README). Logs to data/logs/.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force data/logs | Out-Null
$log = "data/logs/collect_$(Get-Date -Format yyyy-MM-dd).log"

uv run python -m tennis_edge.ingest.odds_live *>> $log
uv run python -m tennis_edge.models.predict *>> $log
uv run python -m tennis_edge.betting.clv_tracker *>> $log
uv run python -m tennis_edge.export *>> $log
