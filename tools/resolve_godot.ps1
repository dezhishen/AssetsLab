function Resolve-HeadlessGodotPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $resolvedPath = (Resolve-Path -LiteralPath $Path).Path
    $fileName = [System.IO.Path]::GetFileName($resolvedPath)
    if ($fileName -match "_console\.exe$") {
        return $resolvedPath
    }

    # Godot's Windows GUI and console builds are shipped side by side. Prefer
    # the console binary for every automated test, even when GODOT_BIN, PATH,
    # or -GodotPath points at the GUI binary.
    $consoleName = [System.IO.Path]::GetFileNameWithoutExtension($fileName) + "_console.exe"
    $consolePath = Join-Path (Split-Path -Parent $resolvedPath) $consoleName
    if (Test-Path -LiteralPath $consolePath -PathType Leaf) {
        return (Resolve-Path -LiteralPath $consolePath).Path
    }
    return $resolvedPath
}

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
            return (Resolve-HeadlessGodotPath -Path $command.Source)
        }
        if (Test-Path -LiteralPath $requestedValue -PathType Leaf) {
            return (Resolve-HeadlessGodotPath -Path $requestedValue)
        }
        throw "Godot executable was not found at '$requestedValue'. Set GODOT_BIN or GODOT_PATH to the Godot executable, or pass -GodotPath."
    }

    foreach ($commandName in @("godot", "godot4")) {
        $command = Get-Command $commandName -ErrorAction SilentlyContinue
        if ($null -ne $command -and $command.CommandType -eq "Application") {
            return (Resolve-HeadlessGodotPath -Path $command.Source)
        }
    }

    $adjacentCandidates = @(
        (Join-Path $AssetsLabRoot "..\Godot-4.6.2\unpacked\Godot_v4.6.2-stable_win64_console.exe"),
        (Join-Path $AssetsLabRoot "..\Godot-4.6.2\unpacked\Godot_v4.6.2-stable_win64.exe")
    )
    foreach ($candidate in $adjacentCandidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-HeadlessGodotPath -Path $candidate)
        }
    }

    throw "Godot executable was not found. Set GODOT_BIN/GODOT_PATH, pass -GodotPath, or add Godot to PATH."
}
