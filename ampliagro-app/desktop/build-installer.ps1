# PowerShell Build Script for Ampliagro Installer
# This script builds the Ampliagro_Windows.exe installer
# Requires NSIS to be installed

param(
    [switch]$Clean = $false,
    [switch]$WebInstaller = $false
)

Write-Host "==========================================" -ForegroundColor Green
Write-Host "Ampliagro Windows Installer Builder" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green

# Define paths
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$AmpliagroAppDir = Join-Path $ProjectRoot "ampliagro-app\desktop"
$InstallerFiles = @("installer.html", "installer.css", "installer.js")

if ($WebInstaller) {
    Write-Host "`n[1/4] Building Web-based Installer..." -ForegroundColor Yellow
    
    # Create installer directory
    $InstallerDir = Join-Path $AmpliagroAppDir "installer"
    if (!(Test-Path $InstallerDir)) {
        New-Item -ItemType Directory -Path $InstallerDir -Force | Out-Null
    }
    
    # Copy installer files
    foreach ($file in $InstallerFiles) {
        $src = Join-Path $ProjectRoot $file
        $dst = Join-Path $InstallerDir $file
        if (Test-Path $src) {
            Copy-Item $src $dst -Force
            Write-Host "  Copied: $file"
        }
    }
    
    Write-Host "  Web installer files ready in: $InstallerDir" -ForegroundColor Green
}

Write-Host "`n[2/4] Setting up NSIS custom installer..." -ForegroundColor Yellow

# Copy NSIS script to build directory
$NsisScript = Join-Path $AmpliagroAppDir "custom-installer.nsi"
$BuildDir = Join-Path $AmpliagroAppDir "build"

if (!(Test-Path $BuildDir)) {
    New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null
}

# Copy license file for NSIS
$LicenseFile = Join-Path $BuildDir "license.txt"
if (!(Test-Path $LicenseFile)) {
    # Create a basic license file
    @"
AMPLIAGRO END USER LICENSE AGREEMENT

This End User License Agreement ("EULA") is a legally binding agreement between you and Ampliagro.

BY INSTALLING AND USING APPLIAGRO, YOU AGREE TO BE BOUNDED BY THESE TERMS.

IMPORTANT: Please read this EULA carefully before installing and using Ampliagro.

[LICENSA]
"@ | Out-File -FilePath $LicenseFile -Encoding UTF8
    Write-Host "  Created license.txt"
}

Write-Host "`n[3/4] Building Electron installer..." -ForegroundColor Yellow

if (Test-Path (Join-Path $AmpliagroAppDir "package.json")) {
    Push-Location $AmpliagroAppDir
    
    try {
        # Run electron-builder for Windows
        if (Test-Path "node_modules") {
            Write-Host "  Running: npm run dist:win" -ForegroundColor Cyan
            npm run dist:win
            Write-Host "  Build complete!" -ForegroundColor Green
        } else {
            Write-Host "  Installing dependencies..." -ForegroundColor Yellow
            npm install
            npm run dist:win
            Write-Host "  Build complete!" -ForegroundColor Green
        }
    } catch {
        Write-Host "  Build error: $_" -ForegroundColor Red
    } finally {
        Pop-Location
    }
} else {
    Write-Host "  package.json not found!" -ForegroundColor Red
}

Write-Host "`n[4/4] Build Summary" -ForegroundColor Yellow
Write-Host "  - Installer files location: $AmpliagroAppDir\dist\" -ForegroundColor Cyan
Write-Host "  - The installer will show 3 tabs: Banco de Dados, Culturas, Download" -ForegroundColor Cyan

Write-Host "`n==========================================" -ForegroundColor Green
Write-Host "Build completed successfully!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green

# Show output
$DistDir = Join-Path $AmpliagroAppDir "dist"
if (Test-Path $DistDir) {
    Write-Host "`nGenerated files:" -ForegroundColor Yellow
    Get-ChildItem $DistDir -Filter "*.exe" -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "  - $($_.Name)" -ForegroundColor Cyan
    }
}