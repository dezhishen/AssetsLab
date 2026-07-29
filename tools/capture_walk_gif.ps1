param(
    [switch]$Female,
    [string]$GodotPath,
    [string]$PythonPath
)

$ErrorActionPreference = "Stop"

$assetsLabRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$prototypeRoot = Join-Path $assetsLabRoot "prototype"
. (Join-Path $PSScriptRoot "resolve_godot.ps1")
$godotPath = Resolve-GodotExecutable -RequestedPath $GodotPath -AssetsLabRoot $assetsLabRoot
. (Join-Path $PSScriptRoot "resolve_python.ps1")
$pythonPath = Resolve-PythonExecutable -RequestedPath $PythonPath -AssetsLabRoot $assetsLabRoot
$pythonModules = Join-Path $assetsLabRoot ".tools\python"
$frameDirectory = Join-Path $prototypeRoot "test_output\capture_frames"
$gifPath = Join-Path $prototypeRoot "test_output\movement_walk.gif"
$logPath = Join-Path $prototypeRoot "test_output\capture.log"

$godotArguments = @(
    "--display-driver", "windows",
    "--rendering-driver", "opengl3",
    "--rendering-method", "gl_compatibility",
    "--fixed-fps", "12",
    "--path", $prototypeRoot,
    "--script", "res://tests/capture_test.gd",
    "--log-file", $logPath
)
if ($Female) {
    $godotArguments += "--female"
}
$godotProcess = Start-Process -FilePath $godotPath -ArgumentList $godotArguments -WindowStyle Hidden -PassThru -Wait
if (Test-Path -LiteralPath $logPath) {
    Get-Content -LiteralPath $logPath
}
if ($godotProcess.ExitCode -ne 0) {
    throw "Godot capture test failed with exit code $($godotProcess.ExitCode)"
}
if (-not (Select-String -LiteralPath $logPath -Pattern "CAPTURE_TEST_PASS" -Quiet)) {
    throw "Godot capture test did not report CAPTURE_TEST_PASS"
}

$previousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = $pythonModules
try {
    & $pythonPath (Join-Path $assetsLabRoot "tools\make_gif.py") --input $frameDirectory --output $gifPath --fps 12
    if ($LASTEXITCODE -ne 0) {
        throw "GIF conversion failed with exit code $LASTEXITCODE"
    }
}
finally {
    $env:PYTHONPATH = $previousPythonPath
}

Write-Output "CAPTURE_COMPLETE=$gifPath"
