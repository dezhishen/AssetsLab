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

    $logDirectory = Join-Path $assetsLabRoot "prototype\test_output"
    New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
    $logName = if ($UseFemale) { "headless_female.log" } else { "headless_male.log" }
    $logPath = Join-Path $logDirectory $logName
    $arguments = @(
        "--headless",
        "--log-file", $logPath,
        "--path", $prototypeRoot,
        "--script", "res://tests/smoke_test.gd"
    )
    if ($UseFemale) {
        $arguments += @("--", "--female")
    }

    Write-Output ("Running headless smoke test ({0}) with {1}" -f ($(if ($UseFemale) { "female" } else { "male" }), $godotPath))
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $output = & $godotPath @arguments 2>&1
    $nativeExitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorActionPreference
    $output | ForEach-Object { Write-Output $_ }
    if ($nativeExitCode -ne 0) {
        throw "Godot headless smoke test failed with exit code $nativeExitCode"
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
