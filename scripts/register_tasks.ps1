# Registers two Windows Task Scheduler jobs for the current user:
#   "Tennis Edge rebuild" - daily 06:00, refresh results and rebuild models
#   "Tennis Edge odds"    - 07:00, 12:00, 17:00, 22:00, snapshot odds / predict / grade
# They run only while you are logged in, never with elevated rights, and catch up
# on a missed run when the computer wakes. Remove with: scripts/unregister_tasks.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$ps = "powershell.exe"
$common = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File"

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

$rebuild = New-ScheduledTaskAction -Execute $ps -WorkingDirectory $root `
    -Argument "$common `"$root\scripts\daily_rebuild.ps1`""
Register-ScheduledTask -TaskName "Tennis Edge rebuild" -Action $rebuild -Settings $settings `
    -Trigger (New-ScheduledTaskTrigger -Daily -At "06:00") `
    -Description "Refresh tennis results and rebuild models (tennis-edge)" -Force | Out-Null

$odds = New-ScheduledTaskAction -Execute $ps -WorkingDirectory $root `
    -Argument "$common `"$root\scripts\collect_odds.ps1`""
$times = "07:00", "12:00", "17:00", "22:00" | ForEach-Object { New-ScheduledTaskTrigger -Daily -At $_ }
Register-ScheduledTask -TaskName "Tennis Edge odds" -Action $odds -Settings $settings `
    -Trigger $times -Description "Snapshot tennis odds, predict and grade picks (tennis-edge)" -Force | Out-Null

Get-ScheduledTask -TaskName "Tennis Edge*" | Select-Object TaskName, State
