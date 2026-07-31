param(
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

$arguments = @(
    "--headless",
    "--display-driver", "windows",
    "--rendering-driver", "opengl3",
    "--rendering-method", "gl_compatibility",
    "--audio-driver", "Dummy",
    "--path", $prototypeRoot,
    "--script", "res://tests/front_leg_cycle_stage_test.gd"
)
$process = Start-Process -FilePath $godotPath -ArgumentList $arguments -WindowStyle Hidden -PassThru -Wait
if ($process.ExitCode -ne 0) {
    throw "Front leg cycle stage failed with exit code $($process.ExitCode)"
}
$frameDirectory = Join-Path $prototypeRoot "test_output\skeleton_pipeline\front_legs"
$gifPath = Join-Path $prototypeRoot "test_output\skeleton_pipeline\front_legs.gif"
if ((Get-ChildItem -LiteralPath $frameDirectory -Filter "frame_*.png" -File | Measure-Object).Count -ne 8) {
    throw "Front leg cycle stage did not produce eight frames"
}
& $pythonPath (Join-Path $assetsLabRoot "tools\make_gif.py") --input $frameDirectory --output $gifPath --fps 8
if ($LASTEXITCODE -ne 0) {
    throw "Front leg cycle GIF conversion failed with exit code $LASTEXITCODE"
}
Write-Output "FRONT_LEG_CYCLE_CAPTURE_PASS=$gifPath"
