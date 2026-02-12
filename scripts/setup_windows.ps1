param(
    [switch]$UpgradePipOnly
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = (Resolve-Path (Join-Path $ScriptDir "..")).Path
Set-Location $RootDir

if (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonLauncher = "py"
    $PythonLauncherArgs = @("-3")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonLauncher = "python"
    $PythonLauncherArgs = @()
} else {
    throw "Python launcher not found. Install Python 3.10+ and retry."
}

Write-Host "[1/3] Creating virtual environment (.venv)"
& $PythonLauncher @PythonLauncherArgs -m venv .venv

$PythonExe = Join-Path $RootDir ".venv\\Scripts\\python.exe"
if (-not (Test-Path $PythonExe)) {
    throw "Failed to create virtual environment at $PythonExe"
}

Write-Host "[2/3] Installing Python dependencies"
& $PythonExe -m pip install --upgrade pip setuptools wheel
if (-not $UpgradePipOnly) {
    & $PythonExe -m pip install -r requirements.txt
}

Write-Host "[3/3] Validation"
& $PythonExe --version
& $PythonExe -m pip freeze | Select-Object -First 20

Write-Host "Done. Build with:"
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts/build_world.ps1 -Config config.yaml"
