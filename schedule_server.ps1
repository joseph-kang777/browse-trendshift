# Register (or replace) a scheduled task that starts the web server (server.py) at logon.
#
#   powershell -ExecutionPolicy Bypass -File schedule_server.ps1
#   Unregister-ScheduledTask -TaskName BrowseTrendshiftServer -Confirm:$false   # remove
$ErrorActionPreference = "Stop"
$project = $PSScriptRoot
$uv = (Get-Command uv).Source

$cmd = "`$env:PYTHONIOENCODING='utf-8'; & '$uv' run server.py *> data\server.log"
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -Command `"$cmd`"" -WorkingDirectory $project
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
# No time limit; restart if it crashes.
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName "BrowseTrendshiftServer" -Action $action -Trigger $trigger -Settings $settings `
    -Description "Trendshift Finder web server on 127.0.0.1:8600 ($project)" -Force | Out-Null
Start-ScheduledTask -TaskName "BrowseTrendshiftServer"
Get-ScheduledTask -TaskName "BrowseTrendshiftServer" | Select-Object TaskName, State
