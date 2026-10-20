# Register (or replace) a Windows scheduled task that runs update.py every day.
# Trendshift days are UTC, so 10:00 KST (01:00 UTC) gets yesterday's final ranking.
#
#   powershell -ExecutionPolicy Bypass -File schedule_daily.ps1            # daily at 10:00
#   powershell -ExecutionPolicy Bypass -File schedule_daily.ps1 -At 08:30
#   Unregister-ScheduledTask -TaskName BrowseTrendshiftUpdate -Confirm:$false   # remove
param([string]$At = "10:00")

$ErrorActionPreference = "Stop"
$project = $PSScriptRoot
$uv = (Get-Command uv).Source

$action = New-ScheduledTaskAction -Execute $uv -Argument "run update.py" -WorkingDirectory $project
$trigger = New-ScheduledTaskTrigger -Daily -At $At
# Run later if the PC was off/asleep at the scheduled time.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName "BrowseTrendshiftUpdate" -Action $action -Trigger $trigger -Settings $settings `
    -Description "trendshift.io daily data + README + index update ($project)" -Force | Out-Null
Get-ScheduledTask -TaskName "BrowseTrendshiftUpdate" | Get-ScheduledTaskInfo | Select-Object TaskName, NextRunTime
