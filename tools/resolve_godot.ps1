function Resolve-GodotExecutable {
    param(
        [Parameter(Mandatory = $false)]
        [string]$RequestedPath,

        [Parameter(Mandatory = $true)]
        [string]$AssetsLabRoot
    )

    $requestedValue = $RequestedPath
    if ([string]::IsNullOrWhiteSpace($requestedValue)) {
        $requestedValue = $env:GODOT_BIN
    }
    if ([string]::IsNullOrWhiteSpace($requestedValue)) {
        $requestedValue = $env:GODOT_PATH
    }

    if (-not [string]::IsNullOrWhiteSpace($requestedValue)) {
        $command = Get-Command $requestedValue -ErrorAction SilentlyContinue
        if ($null -ne $command -and $command.CommandType -eq "Application") {
            return $command.Source
        }
        if (Test-Path -LiteralPath $requestedValue -PathType Leaf) {
            return (Resolve-Path -LiteralPath $requestedValue).Path
        }
        throw "Godot executable was not found at '$requestedValue'. Set GODOT_BIN or GODOT_PATH to the Godot executable, or pass -GodotPath."
    }

    foreach ($commandName in @("godot", "godot4")) {
        $command = Get-Command $commandName -ErrorAction SilentlyContinue
        if ($null -ne $command -and $command.CommandType -eq "Application") {
            return $command.Source
        }
    }

    $adjacentCandidates = @(
        (Join-Path $AssetsLabRoot "..\Godot-4.6.2\unpacked\Godot_v4.6.2-stable_win64_console.exe"),
        (Join-Path $AssetsLabRoot "..\Godot-4.6.2\unpacked\Godot_v4.6.2-stable_win64.exe")
    )
    foreach ($candidate in $adjacentCandidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw "Godot executable was not found. Set GODOT_BIN/GODOT_PATH, pass -GodotPath, or add Godot to PATH."
}
