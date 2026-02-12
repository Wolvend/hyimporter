param(
    [Parameter(Mandatory = $true)]
    [string]$MapName,

    # HyImporter output root (Windows path).
    [string]$OutputRoot = "C:/hyimporter/out",

    # Hytale saves root (Windows path). Default matches standard launcher install.
    [string]$HytaleSavesRoot = "$env:APPDATA/Hytale/UserData/Saves",

    # Target save/world folder name under $HytaleSavesRoot.
    [string]$WorldName = "woof",

    # If set, deletes existing .schematic/.schem files in the destination schematics folder first.
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

function Normalize-WinPath([string]$p) {
    return ($p -replace '/', '\')
}

$OutputRoot = Normalize-WinPath $OutputRoot
$HytaleSavesRoot = Normalize-WinPath $HytaleSavesRoot

$mapOutDir = Join-Path $OutputRoot $MapName
$srcTiles = Join-Path $mapOutDir "tiles"
if (-not (Test-Path $srcTiles)) {
    throw "Missing tiles folder: $srcTiles"
}

$dstModRoot = Join-Path (Join-Path (Join-Path $HytaleSavesRoot $WorldName) "mods") "cc.invic_SchematicLoader"
$dstSchems = Join-Path $dstModRoot "schematics"
New-Item -ItemType Directory -Force -Path $dstSchems | Out-Null

if ($Clean) {
    Get-ChildItem -Path $dstSchems -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "*.schematic" -or $_.Name -like "*.schem" } |
        Remove-Item -Force
}

$schemCount = 0
Get-ChildItem -Path $srcTiles -Filter "*.schematic" -File -ErrorAction SilentlyContinue | ForEach-Object {
    Copy-Item -Force $_.FullName (Join-Path $dstSchems $_.Name)
    $schemCount++
}
Get-ChildItem -Path $srcTiles -Filter "*.schem" -File -ErrorAction SilentlyContinue | ForEach-Object {
    Copy-Item -Force $_.FullName (Join-Path $dstSchems $_.Name)
    $schemCount++
}

# Copy helpful HyImporter artifacts next to the mod folder (safe; the mod ignores unknown files).
$runbookDir = Join-Path $mapOutDir "runbook"
$qaDir = Join-Path $mapOutDir "qa"
if (Test-Path $runbookDir) {
    Copy-Item -Force (Join-Path $runbookDir "tile_manifest.csv") (Join-Path $dstModRoot "hyimporter_tile_manifest.csv") -ErrorAction SilentlyContinue
    Copy-Item -Force (Join-Path $runbookDir "hytale_import_runbook.md") (Join-Path $dstModRoot "hyimporter_import_runbook.md") -ErrorAction SilentlyContinue
}
if (Test-Path $qaDir) {
    Copy-Item -Force (Join-Path $qaDir "summary.json") (Join-Path $dstModRoot "hyimporter_summary.json") -ErrorAction SilentlyContinue
    Copy-Item -Force (Join-Path $qaDir "importer_mcp_review.md") (Join-Path $dstModRoot "hyimporter_review.md") -ErrorAction SilentlyContinue
}

Write-Host "Copied $schemCount schematic file(s) to:"
Write-Host "  $dstSchems"
Write-Host ""
Write-Host "Next:"
Write-Host "1) Restart the Hytale world/server (SchematicLoader builds /schem load commands at startup)."
Write-Host "2) In game:"
Write-Host "   /schem list"
Write-Host "   /schem load <tile_file_name>"
Write-Host "   /schem paste"

