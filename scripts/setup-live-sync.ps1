$ErrorActionPreference = 'Stop'
$secretFolder = Join-Path $env:LOCALAPPDATA 'Neovi\SiteBomLive'
New-Item -ItemType Directory -Path $secretFolder -Force | Out-Null
$pin = Read-Host 'Enter the six digit Site BOM editor PIN' -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($pin)
try { $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
if ($plain -notmatch '^\d{6}$') { throw 'The Site BOM PIN must be exactly six digits.' }
$pin | ConvertFrom-SecureString | Set-Content -LiteralPath (Join-Path $secretFolder 'pin.txt') -NoNewline
$plain = $null
$oldTask = Get-ScheduledTask -TaskName 'Neovi-SiteBOM-Live-Sync' -ErrorAction SilentlyContinue
if ($oldTask) { Unregister-ScheduledTask -TaskName 'Neovi-SiteBOM-Live-Sync' -Confirm:$false }
Write-Output 'Site BOM live sync PIN saved. A completed SiteBOM export triggers the sync; no timed task is installed.'
