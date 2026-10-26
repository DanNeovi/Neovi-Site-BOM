$ErrorActionPreference = 'Stop'
$repository = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$secretFolder = Join-Path $env:LOCALAPPDATA 'Neovi\SiteBomLive'
New-Item -ItemType Directory -Path $secretFolder -Force | Out-Null
$pin = Read-Host 'Enter the six digit Site BOM editor PIN' -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($pin)
try { $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
if ($plain -notmatch '^\d{6}$') { throw 'The Site BOM PIN must be exactly six digits.' }
$pin | ConvertFrom-SecureString | Set-Content -LiteralPath (Join-Path $secretFolder 'pin.txt') -NoNewline
$plain = $null
$runner = Join-Path $repository 'scripts\run-live-sync.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -ExecutionPolicy Bypass -File "' + $runner + '"')
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
$principal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'Neovi-SiteBOM-Live-Sync' -Action $action -Trigger $trigger -Principal $principal -Force | Out-Null
Write-Output 'Site BOM Drive export sync registered for every five minutes while this user is signed in.'
