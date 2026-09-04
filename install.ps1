# Samvaadhika - Automated Installation (PowerShell)
#
# Usage:
#   Option 1: Double-click install.ps1
#   Option 2: powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1
#   Option 3: In PowerShell: Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process; .\install.ps1

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "SAMVAADHIKA - AUTOMATED INSTALLATION (PowerShell)" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This script will:" -ForegroundColor Yellow
Write-Host "  1. Create Python 3.12 virtual environment"
Write-Host "  2. Install all dependencies"
Write-Host "  3. Download all three translation models"
Write-Host "  4. Verify everything works"
Write-Host ""
Write-Host "Estimated time: 20-45 minutes"
Write-Host "Please do NOT close this window during installation"
Write-Host ""

# Check if Python 3.12 is available
Write-Host "Checking Python installation..." -ForegroundColor Green

try {
    $pythonVersion = & python --version 2>&1
    Write-Host "  ✅ Found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Python not found on PATH" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Python 3.12 from: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "Make sure to check 'Add Python to PATH' during installation"
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Run the main installation script
Write-Host ""
Write-Host "Running automated installation..." -ForegroundColor Green
Write-Host ""

$pythonExe = (Get-Command python).Source
& $pythonExe install.py

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Installation encountered errors!" -ForegroundColor Red
    Write-Host "Please check the output above for details"
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Green
Write-Host "INSTALLATION SUCCESSFUL!" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "To start the application:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  1. Activate environment:"
Write-Host "     .\venv312\Scripts\Activate.ps1"
Write-Host ""
Write-Host "  2. Start the application:"
Write-Host "     python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
Write-Host ""
Write-Host "  3. Open in browser:"
Write-Host "     http://localhost:8000"
Write-Host ""
Write-Host "For more information, see INSTALLATION_GUIDE.md"
Write-Host ""

Read-Host "Press Enter to exit"
