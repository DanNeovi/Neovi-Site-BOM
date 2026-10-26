$ErrorActionPreference = 'Stop'
$repository = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$secretFile = Join-Path $env:LOCALAPPDATA 'Neovi\SiteBomLive\pin.txt'
if (-not (Test-Path -LiteralPath $secretFile -PathType Leaf)) { throw "Missing local PIN. Run scripts\setup-live-sync.ps1 interactively." }
$secure = Get-Content -LiteralPath $secretFile -Raw | ConvertTo-SecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try { $env:SITE_BOM_PIN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
try {
    & node (Join-Path $repository 'scripts\sync-live-source.mjs')
    if ($LASTEXITCODE -ne 0) { throw "Live Site BOM sync exited with code $LASTEXITCODE" }
}
finally { Remove-Item Env:SITE_BOM_PIN -ErrorAction SilentlyContinue }
