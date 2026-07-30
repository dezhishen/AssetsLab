param(
    [string]$GodotPath,
    [string]$PythonPath,
    [switch]$Female,
    [switch]$Compact,
    [int]$AppearanceSeed
)

$ErrorActionPreference = "Stop"

$assetsLabRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$prototypeRoot = Join-Path $assetsLabRoot "prototype"
. (Join-Path $PSScriptRoot "resolve_godot.ps1")
$godotPath = Resolve-GodotExecutable -RequestedPath $GodotPath -AssetsLabRoot $assetsLabRoot
. (Join-Path $PSScriptRoot "resolve_python.ps1")
$pythonPath = Resolve-PythonExecutable -RequestedPath $PythonPath -AssetsLabRoot $assetsLabRoot
$pythonModules = Join-Path $assetsLabRoot ".tools\python"
$assetVariant = if ($Compact) { "chibi_compact" } else { "chibi" }

$importLogPath = Join-Path $assetsLabRoot "prototype\test_output\headless_import.log"
New-Item -ItemType Directory -Force -Path (Split-Path $importLogPath) | Out-Null
$importOutput = & $godotPath --headless --editor --import --path $prototypeRoot --quit 2>&1
$importExitCode = $LASTEXITCODE
$importOutput | Out-File -LiteralPath $importLogPath -Encoding utf8
if ($importExitCode -ne 0) {
    throw "Godot headless asset import failed with exit code $importExitCode"
}

$previousPythonPath = $env:PYTHONPATH
$previousChibiAssetRoot = $env:CHIBI_ASSET_ROOT
$env:PYTHONPATH = $pythonModules
$env:CHIBI_ASSET_ROOT = $assetVariant
try {
    & $pythonPath (Join-Path $assetsLabRoot "tools\validate_chibi_frames.py")
    if ($LASTEXITCODE -ne 0) {
        throw "Chibi frame validation failed with exit code $LASTEXITCODE"
    }
    & $pythonPath (Join-Path $assetsLabRoot "tools\validate_face_variants.py")
    if ($LASTEXITCODE -ne 0) {
        throw "Face and ear frame validation failed with exit code $LASTEXITCODE"
    }
}
finally {
    $env:PYTHONPATH = $previousPythonPath
    $env:CHIBI_ASSET_ROOT = $previousChibiAssetRoot
}

function Invoke-SmokeTest {
    param([switch]$UseFemale)

    $logDirectory = Join-Path $assetsLabRoot "prototype\test_output"
    New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
    $logPrefix = if ($Compact) { "headless_compact" } else { "headless" }
    $logName = if ($UseFemale) { "$logPrefix`_female.log" } else { "$logPrefix`_male.log" }
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
    if ($Compact) {
        if ($arguments -contains "--") {
            $arguments += "--compact"
        } else {
            $arguments += @("--", "--compact")
        }
    }
    if ($PSBoundParameters.ContainsKey("AppearanceSeed")) {
        if ($arguments -contains "--") {
            $arguments += "--appearance-seed=$AppearanceSeed"
        } else {
            $arguments += @("--", "--appearance-seed=$AppearanceSeed")
        }
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
