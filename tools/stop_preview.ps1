$ErrorActionPreference = "Stop"
$assetsLabRoot = Split-Path -Parent $PSScriptRoot
$pidPath = Join-Path $assetsLabRoot "prototype\test_output\lan_preview.pid"
if (-not (Test-Path -LiteralPath $pidPath)) {
    Write-Output "PREVIEW_SERVER_NOT_FOUND"
    exit 0
}

$serverPid = [int](Get-Content -LiteralPath $pidPath -Raw).Trim()
$process = Get-Process -Id $serverPid -ErrorAction SilentlyContinue
if ($process) {
    Stop-Process -Id $serverPid
    Write-Output "PREVIEW_SERVER_STOPPED pid=$serverPid"
} else {
    Write-Output "PREVIEW_SERVER_NOT_RUNNING pid=$serverPid"
}
Remove-Item -LiteralPath $pidPath -Force
