param(
    [string]$DriveFolder = 'G:\My Drive\SiteBOM'
)

$ErrorActionPreference = 'Stop'
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$outputRoot = Join-Path $repoRoot 'outputs'
$link = Join-Path $outputRoot 'NeoviBOM'
$target = [System.IO.Path]::GetFullPath($DriveFolder)

if (-not (Test-Path -LiteralPath $target -PathType Container)) {
    throw "Google Drive output folder is unavailable: $target"
}

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
$existing = Get-Item -LiteralPath $link -Force -ErrorAction SilentlyContinue
if ($existing) {
    if ($existing.LinkType -eq 'Junction' -and
        [System.IO.Path]::GetFullPath($existing.Target).TrimEnd('\') -eq $target.TrimEnd('\')) {
        Write-Output "Site BOM output already points to $target"
        exit 0
    }
    throw "Output path already exists and was not changed: $link. Move or reconcile it before linking."
}

New-Item -ItemType Junction -Path $link -Target $target | Out-Null
Write-Output "Site BOM output now points to $target"
