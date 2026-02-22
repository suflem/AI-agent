param(
    [switch]$ForcePathUpdate
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonExe = Join-Path $projectRoot "venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    throw "未找到虚拟环境解释器: $pythonExe"
}

$binDir = Join-Path $env:USERPROFILE ".ai-agent\bin"
New-Item -ItemType Directory -Force -Path $binDir | Out-Null

$runCmdPath = Join-Path $binDir "ai-agent.cmd"
$apiCmdPath = Join-Path $binDir "ai-agent-api.cmd"

$runCmd = @"
@echo off
setlocal
cd /d "$projectRoot"
"$pythonExe" "$projectRoot\run.py" %*
"@

$apiCmd = @"
@echo off
setlocal
cd /d "$projectRoot"
"$pythonExe" "$projectRoot\run_api.py" %*
"@

Set-Content -Path $runCmdPath -Value $runCmd -Encoding ascii
Set-Content -Path $apiCmdPath -Value $apiCmd -Encoding ascii

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$pathEntries = @()
if ($userPath) {
    $pathEntries = $userPath -split ";" | Where-Object { $_ -and $_.Trim() -ne "" }
}

$alreadyInPath = $false
foreach ($entry in $pathEntries) {
    if ($entry.TrimEnd('\').ToLowerInvariant() -eq $binDir.TrimEnd('\').ToLowerInvariant()) {
        $alreadyInPath = $true
        break
    }
}

if (-not $alreadyInPath -or $ForcePathUpdate) {
    $newPath = ($pathEntries + $binDir) -join ";"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "已更新用户 PATH，新的终端会自动生效。"
} else {
    Write-Host "用户 PATH 已包含: $binDir"
}

Write-Host ""
Write-Host "命令安装完成："
Write-Host "  ai-agent      -> 启动 CLI"
Write-Host "  ai-agent-api  -> 启动 API 服务"
Write-Host ""
Write-Host "请关闭并重新打开终端后再执行命令。"
