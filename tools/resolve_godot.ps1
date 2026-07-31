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

    # Godot's Windows GUI and console builds are shipped side by side. Automated
    # capture must never fall back to the GUI binary: that can open an editor or
    # game window despite a caller intending a silent preview run.
    $consoleName = [System.IO.Path]::GetFileNameWithoutExtension($fileName) + "_console.exe"
    $consolePath = Join-Path (Split-Path -Parent $resolvedPath) $consoleName
    if (Test-Path -LiteralPath $consolePath -PathType Leaf) {
        return (Resolve-Path -LiteralPath $consolePath).Path
    }

    # A PATH alias such as godot.exe may not share the versioned filename of
    # its console sibling. If exactly one console build lives beside it, use
    # that build; otherwise fail closed rather than launching a GUI executable.
    $consoleCandidates = @(Get-ChildItem -LiteralPath (Split-Path -Parent $resolvedPath) -Filter "*_console.exe" -File -ErrorAction SilentlyContinue)
    if ($consoleCandidates.Count -eq 1) {
        return $consoleCandidates[0].FullName
    }
    throw "Silent Godot automation requires a *_console.exe executable. No unambiguous console sibling was found for '$resolvedPath'."
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
        (Join-Path $AssetsLabRoot "..\Godot-4.6.2\unpacked\Godot_v4.6.2-stable_win64_console.exe")
    )
    foreach ($candidate in $adjacentCandidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-HeadlessGodotPath -Path $candidate)
        }
    }

    throw "Godot executable was not found. Set GODOT_BIN/GODOT_PATH, pass -GodotPath, or add Godot to PATH."
}
