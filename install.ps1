$ErrorActionPreference = "Stop"

$RepoUrl = "https://raw.githubusercontent.com/sdiebolt/jupyagent/main/jupyagent.py" # PLACEHOLDER
$InstallDir = "$env:LOCALAPPDATA\Programs\jupyagent"
$BinDir = "$InstallDir\bin"
$ExeName = "jupyagent"

Write-Host "Installing JupyAgent Manager..."

# Create Directories
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

# Download Script
Write-Host "Downloading..."
try {
    Invoke-WebRequest -Uri $RepoUrl -OutFile "$BinDir\jupyagent.py"
} catch {
    Write-Error "Failed to download from $RepoUrl"
    Write-Error $_.Exception.Message
    exit 1
}

# Create Wrapper (.bat) for easy execution
$BatContent = "@echo off
python `"$BinDir\jupyagent.py`" %*"
Set-Content -Path "$BinDir\$ExeName.bat" -Value $BatContent

# Add to PATH
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$BinDir*") {
    Write-Host "Adding to PATH..."
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$BinDir", "User")
    Write-Host "NOTE: You may need to restart your terminal for PATH changes to take effect."
}

Write-Host "Installation complete!"
Write-Host "Run '$ExeName' to get started."
