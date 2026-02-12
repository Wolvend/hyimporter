param(
    [string]$Config = "config.yaml",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = (Resolve-Path (Join-Path $ScriptDir "..")).Path
Set-Location $RootDir

if (-not (Test-Path $Config)) {
    throw "Config file not found: $Config. Create one from config/config.example.yaml"
}

$PythonExe = Join-Path $RootDir ".venv\\Scripts\\python.exe"
if (-not (Test-Path $PythonExe)) {
    throw "Virtual environment missing. Run scripts/setup_windows.ps1 first."
}

if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$RootDir\\src;$env:PYTHONPATH"
} else {
    $env:PYTHONPATH = "$RootDir\\src"
}

& $PythonExe -m hyimporter.build --config $Config @ExtraArgs
