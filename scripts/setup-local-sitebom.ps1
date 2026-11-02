$ErrorActionPreference = 'Stop'
$repository = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$server = Join-Path $repository 'scripts\serve-local-sitebom.py'
$python = (Get-Command pythonw.exe -ErrorAction Stop).Source
$taskName = 'Neovi-SiteBOM-Local'
$action = New-ScheduledTaskAction -Execute $python -Argument ('"' + $server + '" --port 8765') -WorkingDirectory $repository
$trigger = New-ScheduledTaskTrigger -AtLogOn -User ([Security.Principal.WindowsIdentity]::GetCurrent().Name)
$principal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Write-Output "SiteBOM will start at Windows sign-in: http://127.0.0.1:8765/dashboard"
