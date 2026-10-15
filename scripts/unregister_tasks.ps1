# Removes the scheduled jobs created by register_tasks.ps1.
Unregister-ScheduledTask -TaskName "Tennis Edge rebuild" -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "Tennis Edge odds" -Confirm:$false -ErrorAction SilentlyContinue
Write-Output "Tennis Edge scheduled tasks removed."
