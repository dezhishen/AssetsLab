[CmdletBinding()]
param(
    [ValidateSet("A_both_legs_pass", "B_front_leg_only_pass", "All")]
    [string]$Workflow = "All",
    [string]$GodotPath = ""
)

$assetsLabRoot = Split-Path -Parent $PSScriptRoot
$prototypeRoot = Join-Path $assetsLabRoot "prototype"
$outputRoot = Join-Path $prototypeRoot "test_output\skeleton_workflows"
$logRoot = Join-Path $prototypeRoot "test_output"
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null

if ([string]::IsNullOrWhiteSpace($GodotPath)) {
    $GodotPath = $env:GODOT_BIN
}
if ([string]::IsNullOrWhiteSpace($GodotPath)) {
    $GodotPath = $env:GODOT_PATH
}
if ([string]::IsNullOrWhiteSpace($GodotPath)) {
    $GodotPath = Join-Path (Split-Path -Parent $assetsLabRoot) "Godot-4.6.2\unpacked\Godot_v4.6.2-stable_win64_console.exe"
}
if (-not (Test-Path -LiteralPath $GodotPath)) {
    throw "Godot executable not found: $GodotPath"
}

$workflows = if ($Workflow -eq "All") {
    @("A_both_legs_pass", "B_front_leg_only_pass")
} else {
    @($Workflow)
}

foreach ($name in $workflows) {
    $logPath = Join-Path $logRoot ("skeleton_capture_{0}.log" -f $name)
    $arguments = @(
        "--headless",
        "--display-driver", "windows",
        "--rendering-driver", "opengl3",
        "--rendering-method", "gl_compatibility",
        "--audio-driver", "Dummy",
        "--fixed-fps", "12",
        "--path", $prototypeRoot,
        "--script", "res://tests/skeleton_workflow_capture.gd",
        "--",
        "--workflow=$name"
    )
    & $GodotPath @arguments *> $logPath
    $exitCode = $LASTEXITCODE
    if (Test-Path -LiteralPath $logPath) {
        Get-Content -LiteralPath $logPath
    }
    if ($exitCode -ne 0) {
        throw "Skeleton workflow capture failed for $name with exit code $exitCode"
    }
    if (-not (Select-String -LiteralPath $logPath -Pattern "SKELETON_WORKFLOW_CAPTURE_PASS" -Quiet)) {
        throw "Skeleton workflow capture did not report PASS for $name"
    }
}

$pythonPath = $env:PYTHON_BIN
if ([string]::IsNullOrWhiteSpace($pythonPath)) {
    $pythonPath = "python"
}
& $pythonPath (Join-Path $assetsLabRoot "tools\make_skeleton_workflow_previews.py")
if ($LASTEXITCODE -ne 0) {
    throw "Skeleton workflow preview generation failed"
}

Write-Output "SKELETON_WORKFLOW_CAPTURE_SCRIPT_PASS workflows=$($workflows -join ',') output=$outputRoot"
