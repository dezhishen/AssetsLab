param(
    [switch]$Female,
    [switch]$Compact,
	[switch]$BaseFeatures,
	[switch]$RgsWalkReference,
    [string]$GodotPath,
    [string]$PythonPath,
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
$frameDirectory = Join-Path $prototypeRoot "test_output\capture_frames"
$randomAppearanceRoot = Join-Path $prototypeRoot "test_output\random_appearance"
$gifName = if ($RgsWalkReference) {
    "movement_rgs_reference.gif"
} elseif ($BaseFeatures) {
    "movement_walk_base_features_v1.gif"
} elseif ($Compact) {
	"movement_walk_compact.gif"
} else {
    "movement_walk.gif"
}
$gifPath = Join-Path $prototypeRoot "test_output\$gifName"
$logPath = Join-Path $prototypeRoot "test_output\capture.log"

$previousGeneratorPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = $pythonModules
try {
    $generatorArguments = @(
        (Join-Path $assetsLabRoot "tools\generate_random_appearance.py"),
        "--output", (Join-Path $randomAppearanceRoot $(if ($Female) { "female" } else { "male" }))
    )
    if ($Female) {
        $generatorArguments += "--female"
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
    $validationOutput = & $pythonPath (Join-Path $assetsLabRoot "tools\validate_random_appearance.py") --root (Join-Path $randomAppearanceRoot $(if ($Female) { "female" } else { "male" })) 2>&1
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

$godotArguments = @(
    "--display-driver", "windows",
    "--rendering-driver", "opengl3",
    "--rendering-method", "gl_compatibility",
    "--audio-driver", "Dummy",
    "--fixed-fps", "12",
    "--path", $prototypeRoot,
    "--script", "res://tests/capture_test.gd",
    "--log-file", $logPath
)
# Everything after this separator is forwarded to OS.get_cmdline_user_args()
# and is consumed by player.gd as a test-only runtime mode.
$godotArguments += "--"
if ($Female) {
    $godotArguments += "--female"
}
if ($Compact) {
    $godotArguments += "--compact"
}
if ($BaseFeatures) {
    $godotArguments += "--base-features"
} else {
    $godotArguments += "--appearance-seed=$appearanceSeed"
}
if ($RgsWalkReference) {
	$godotArguments += "--rgs-walk-reference"
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
    if ($RgsWalkReference) {
        Copy-Item -LiteralPath $gifPath -Destination (Join-Path $assetsLabRoot "prototype\preview\assets\movement_rgs_reference.gif") -Force
    }
}
finally {
    $env:PYTHONPATH = $previousPythonPath
}

Write-Output "CAPTURE_COMPLETE=$gifPath"
