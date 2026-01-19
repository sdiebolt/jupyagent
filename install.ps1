$ErrorActionPreference = "Stop"

$RepoBase = "https://raw.githubusercontent.com/sdiebolt/jupyagent/main"
$InstallDir = "$env:LOCALAPPDATA\Programs\jupyagent"
$AppDir = "$env:USERPROFILE\.jupyagent"
$BinDir = "$InstallDir\bin"
$ExeName = "jupyagent"

Write-Host "Installing JupyAgent Manager..."

# 1. Prereqs (Check Python)
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python is required but not found in PATH."
    exit 1
}

# 2. Setup App Directory & Venv
Write-Host "Setting up environment in $AppDir..."
New-Item -ItemType Directory -Force -Path $AppDir | Out-Null
if (-not (Test-Path "$AppDir\venv")) {
    python -m venv "$AppDir\venv"
}

# 3. Install Dependencies
Write-Host "Installing dependencies (textual)..."
& "$AppDir\venv\Scripts\pip" install -q textual requests

# 4. Download Script
Write-Host "Downloading application..."
try {
    Invoke-WebRequest -Uri "$RepoBase/jupyagent.py" -OutFile "$AppDir\jupyagent.py"
} catch {
    Write-Error "Failed to download application."
    Write-Error $_.Exception.Message
    exit 1
}

# 5. Create Wrapper
Write-Host "Creating launcher..."
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
$BatContent = "@echo off
`"$AppDir\venv\Scripts\python`" `"$AppDir\jupyagent.py`" %*"
Set-Content -Path "$BinDir\$ExeName.bat" -Value $BatContent

# 6. Add to PATH
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$BinDir*") {
    Write-Host "Adding to PATH..."
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$BinDir", "User")
    Write-Host "NOTE: You may need to restart your terminal for PATH changes to take effect."
}

Write-Host "Installation complete!"
Write-Host "Run '$ExeName' to get started."
