param(
    [string]$GodotPath
)

$ErrorActionPreference = "Stop"
$assetsLabRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$prototypeRoot = Join-Path $assetsLabRoot "prototype"
. (Join-Path $PSScriptRoot "resolve_godot.ps1")
$godotPath = Resolve-GodotExecutable -RequestedPath $GodotPath -AssetsLabRoot $assetsLabRoot

$arguments = @(
    "--headless",
    "--display-driver", "windows",
    "--rendering-driver", "opengl3",
    "--rendering-method", "gl_compatibility",
    "--audio-driver", "Dummy",
    "--path", $prototypeRoot,
    "--script", "res://tests/side_skeleton_stage_test.gd"
)
$process = Start-Process -FilePath $godotPath -ArgumentList $arguments -WindowStyle Hidden -PassThru -Wait
if ($process.ExitCode -ne 0) {
    throw "Side skeleton stage failed with exit code $($process.ExitCode)"
}
$capturePath = Join-Path $prototypeRoot "test_output\skeleton_pipeline\side_base.png"
if (-not (Test-Path -LiteralPath $capturePath -PathType Leaf)) {
    throw "Side skeleton stage did not produce a capture"
}
Write-Output "SIDE_SKELETON_CAPTURE_PASS=$capturePath"
