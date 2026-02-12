param(
    [Parameter(Mandatory = $true)]
    [string]$MapName,
    [string]$OutputRoot = "C:/hyimporter/out"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = (Resolve-Path (Join-Path $ScriptDir "..")).Path
Set-Location $RootDir

$PythonExe = Join-Path $RootDir ".venv\\Scripts\\python.exe"
if (-not (Test-Path $PythonExe)) {
    throw "Missing .venv Python. Run scripts/setup_windows.ps1 first."
}

$VoxelViewerRoot = Join-Path $RootDir "voxelviewer"
if (-not (Test-Path $VoxelViewerRoot)) {
    throw "Missing voxelviewer workspace at: $VoxelViewerRoot"
}

$MapOutDir = Join-Path $OutputRoot $MapName
if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$RootDir\\src;$env:PYTHONPATH"
} else {
    $env:PYTHONPATH = "$RootDir\\src"
}

& $PythonExe -m hyimporter.importer_mcp `
    --output-dir $MapOutDir `
    --index-with-voxelviewer `
    --voxelviewer-root $VoxelViewerRoot

Write-Host "VoxelViewer index connection complete for: $MapOutDir"
