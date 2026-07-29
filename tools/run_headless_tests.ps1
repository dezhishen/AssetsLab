param(
    [string]$GodotPath,
    [switch]$Female
)

$ErrorActionPreference = "Stop"

$assetsLabRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$prototypeRoot = Join-Path $assetsLabRoot "prototype"
. (Join-Path $PSScriptRoot "resolve_godot.ps1")
$godotPath = Resolve-GodotExecutable -RequestedPath $GodotPath -AssetsLabRoot $assetsLabRoot

function Invoke-SmokeTest {
    param([switch]$UseFemale)

    $arguments = @(
        "--headless",
        "--path", $prototypeRoot,
        "--script", "res://tests/smoke_test.gd"
    )
    if ($UseFemale) {
        $arguments += @("--", "--female")
    }

    Write-Output ("Running headless smoke test ({0}) with {1}" -f ($(if ($UseFemale) { "female" } else { "male" }), $godotPath))
    $output = & $godotPath @arguments 2>&1
    $output | ForEach-Object { Write-Output $_ }
    if ($LASTEXITCODE -ne 0) {
        throw "Godot headless smoke test failed with exit code $LASTEXITCODE"
    }
    if (-not ($output -match "SMOKE_TEST_PASS")) {
        throw "Godot headless smoke test did not report SMOKE_TEST_PASS"
    }
}

Invoke-SmokeTest
if ($Female) {
    Invoke-SmokeTest -UseFemale
}

Write-Output "HEADLESS_TESTS_PASS"
