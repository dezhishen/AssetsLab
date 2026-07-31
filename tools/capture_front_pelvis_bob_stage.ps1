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
    "--script", "res://tests/front_pelvis_bob_stage_test.gd"
)
$process = Start-Process -FilePath $godotPath -ArgumentList $arguments -WindowStyle Hidden -PassThru -Wait
if ($process.ExitCode -ne 0) {
    throw "Front pelvis bob stage failed with exit code $($process.ExitCode)"
}
$frameDirectory = Join-Path $prototypeRoot "test_output\skeleton_pipeline\front_pelvis_bob"
$gifPath = Join-Path $prototypeRoot "test_output\skeleton_pipeline\front_pelvis_bob.gif"
if ((Get-ChildItem -LiteralPath $frameDirectory -Filter "frame_*.png" -File | Measure-Object).Count -ne 8) {
    throw "Front pelvis bob stage did not produce eight frames"
}
& $pythonPath (Join-Path $assetsLabRoot "tools\make_gif.py") --input $frameDirectory --output $gifPath --fps 8
if ($LASTEXITCODE -ne 0) {
    throw "Front pelvis bob GIF conversion failed with exit code $LASTEXITCODE"
}
Write-Output "FRONT_PELVIS_BOB_CAPTURE_PASS=$gifPath"
