param(
    [string]$GodotPath,
    [string]$PythonPath,
    [switch]$Female,
    [switch]$Compact,
    [switch]$BaseFeatures,
    [switch]$RebuildHead,
    [switch]$RebuildBody,
    [switch]$RgsWalkReference,
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
$randomAppearanceRoot = Join-Path $prototypeRoot "test_output\random_appearance"

$previousGeneratorPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = $pythonModules
try {
    $generatorOutputRoot = if ($Female) { $randomAppearanceRoot } else { Join-Path $randomAppearanceRoot "male" }
    $generatorArguments = @(
        (Join-Path $assetsLabRoot "tools\generate_random_appearance.py"),
        "--output", $generatorOutputRoot
    )
    if ($Female) {
        $generatorArguments += "--both"
    }
    if ($Compact) {
        $generatorArguments += "--compact"
    }
    if ($PSBoundParameters.ContainsKey("AppearanceSeed")) {
        $generatorArguments += @("--seed", "$AppearanceSeed")
    }
    $generatorOutput = & $pythonPath @generatorArguments 2>&1
    $generatorExitCode = $LASTEXITCODE
    $generatorOutput | ForEach-Object { Write-Output $_ }
    if ($generatorExitCode -ne 0) {
        throw "Random appearance generation failed with exit code $generatorExitCode"
    }
    $seedLine = $generatorOutput | Where-Object { "$_" -match "^RANDOM_APPEARANCE_SEED=" } | Select-Object -Last 1
    if ($null -eq $seedLine) {
        throw "Random appearance generator did not return a seed"
    }
    $appearanceSeed = [int]("$seedLine" -replace "^RANDOM_APPEARANCE_SEED=", "")
    $validationArguments = @(
        (Join-Path $assetsLabRoot "tools\validate_random_appearance.py"),
        "--root", $randomAppearanceRoot
    )
    if ($Female) {
        $validationArguments += "--both"
    } else {
        $validationArguments[2] = $generatorOutputRoot
    }
    $validationOutput = & $pythonPath @validationArguments 2>&1
    $validationExitCode = $LASTEXITCODE
    $validationOutput | ForEach-Object { Write-Output $_ }
    if ($validationExitCode -ne 0) {
        throw "Random appearance validation failed with exit code $validationExitCode"
    }
    if ($BaseFeatures) {
        $baseValidationOutput = & $pythonPath (Join-Path $assetsLabRoot "tools\validate_base_features.py") 2>&1
        $baseValidationExitCode = $LASTEXITCODE
        $baseValidationOutput | ForEach-Object { Write-Output $_ }
        if ($baseValidationExitCode -ne 0) {
            throw "Base feature validation failed with exit code $baseValidationExitCode"
        }
    }
}
finally {
    $env:PYTHONPATH = $previousGeneratorPythonPath
}

$importLogPath = Join-Path $assetsLabRoot "prototype\test_output\headless_import.log"
New-Item -ItemType Directory -Force -Path (Split-Path $importLogPath) | Out-Null
$importOutput = & $godotPath --headless --editor --import --path $prototypeRoot --quit 2>&1
$importExitCode = $LASTEXITCODE
$importOutput | Out-File -LiteralPath $importLogPath -Encoding utf8
if ($importExitCode -ne 0) {
    throw "Godot headless asset import failed with exit code $importExitCode"
}

function Invoke-GodotScriptTest {
    param([string]$ScriptName)

    $scriptArguments = @(
        "--headless",
        "--path", $prototypeRoot,
        "--script", "res://tests/$ScriptName"
    )
    $scriptOutput = & $godotPath @scriptArguments 2>&1
    $scriptExitCode = $LASTEXITCODE
    $scriptOutput | ForEach-Object { Write-Output $_ }
    if ($scriptExitCode -ne 0) {
        throw "Godot test $ScriptName failed with exit code $scriptExitCode"
    }
}

$previousPythonPath = $env:PYTHONPATH
$previousChibiAssetRoot = $env:CHIBI_ASSET_ROOT
$env:PYTHONPATH = $pythonModules
$env:CHIBI_ASSET_ROOT = $assetVariant
try {
    if ($RebuildHead) {
        & $pythonPath (Join-Path $assetsLabRoot "tools\validate_rebuild_runtime_anchors.py")
        if ($LASTEXITCODE -ne 0) {
            throw "Rebuild runtime anchor validation failed with exit code $LASTEXITCODE"
        }
    }
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
    if ($BaseFeatures) {
        if ($arguments -contains "--") {
            $arguments += "--base-features"
        } else {
            $arguments += @("--", "--base-features")
        }
    } else {
        if ($arguments -contains "--") {
            $arguments += "--appearance-seed=$appearanceSeed"
        } else {
            $arguments += @("--", "--appearance-seed=$appearanceSeed")
        }
    }
    if ($RebuildHead) {
        if ($arguments -contains "--") {
            $arguments += "--rebuild-head"
        } else {
            $arguments += @("--", "--rebuild-head")
        }
    }
    if ($RebuildBody) {
        if ($arguments -contains "--") {
            $arguments += "--rebuild-body"
        } else {
            $arguments += @("--", "--rebuild-body")
        }
    }
    if ($RgsWalkReference) {
        if ($arguments -contains "--") {
            $arguments += "--rgs-walk-reference"
        } else {
            $arguments += @("--", "--rgs-walk-reference")
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
