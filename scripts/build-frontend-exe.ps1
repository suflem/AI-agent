param(
    [switch]$SkipInstall,
    [int]$InstallRetries = 3
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$frontendDir = Join-Path $projectRoot "frontend"

if (-not (Test-Path $frontendDir)) {
    throw "frontend 目录不存在: $frontendDir"
}

Write-Host "Project root: $projectRoot"
Set-Location $frontendDir

$npmCacheDir = Join-Path $frontendDir ".npm-cache"
if (-not (Test-Path $npmCacheDir)) {
    New-Item -Path $npmCacheDir -ItemType Directory | Out-Null
}
$env:npm_config_cache = $npmCacheDir
Write-Host "Using npm cache: $npmCacheDir"

function Invoke-CmdChecked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,
        [Parameter(Mandatory = $true)]
        [string]$StepName
    )

    cmd /c $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$StepName failed with exit code $LASTEXITCODE. Command: $Command"
    }
}

if (-not $SkipInstall) {
    $installSucceeded = $false
    $installCommand = "npm install --foreground-scripts --no-audit --fund=false --fetch-retries=5 --fetch-retry-mintimeout=20000 --fetch-retry-maxtimeout=120000"

    for ($attempt = 1; $attempt -le $InstallRetries; $attempt++) {
        Write-Host "Installing npm dependencies... (attempt $attempt/$InstallRetries)"
        cmd /c $installCommand

        if ($LASTEXITCODE -eq 0) {
            $installSucceeded = $true
            break
        }

        if ($attempt -lt $InstallRetries) {
            $waitSeconds = [Math]::Min(30, [Math]::Pow(2, $attempt + 1))
            Write-Warning "npm install failed with exit code $LASTEXITCODE. Retrying in $waitSeconds seconds..."
            Start-Sleep -Seconds $waitSeconds
        }
    }

    if (-not $installSucceeded) {
        throw "Dependency installation failed after $InstallRetries attempts. Command: $installCommand"
    }
}

Write-Host "Building Windows installer (.exe)..."
Invoke-CmdChecked -Command "npm run build:electron" -StepName "Electron installer build"

$releaseDir = Join-Path $frontendDir "release"
if (-not (Test-Path $releaseDir)) {
    throw "Build completed but release directory was not found: $releaseDir"
}

$installerFiles = Get-ChildItem -Path $releaseDir -Recurse -File -Filter "*.exe" -ErrorAction SilentlyContinue
if (-not $installerFiles) {
    throw "Build completed but no .exe artifacts were found under: $releaseDir"
}

Write-Host "Build completed. Output directory: $releaseDir"
Write-Host "Generated installer artifacts:"
$installerFiles | ForEach-Object { Write-Host " - $($_.FullName)" }
