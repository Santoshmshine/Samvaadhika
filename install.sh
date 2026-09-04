#!/bin/bash
# Samvaadhika - Automated Installation (Linux/Mac)
#
# Usage:
#   chmod +x install.sh
#   ./install.sh

set -e  # Exit on error

echo ""
echo "================================================================================"
echo "SAMVAADHIKA - AUTOMATED INSTALLATION (Linux/Mac)"
echo "================================================================================"
echo ""
echo "This script will:"
echo "  1. Create Python 3.12 virtual environment"
echo "  2. Install all dependencies"
echo "  3. Download all three translation models"
echo "  4. Verify everything works"
echo ""
echo "Estimated time: 20-45 minutes"
echo "Please do NOT interrupt this script"
echo ""

# Check Python version
echo "Checking Python installation..."
if command -v python3.12 &> /dev/null; then
    PYTHON_EXE="python3.12"
    echo "  ✅ Found Python 3.12"
elif command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    if [[ $PYTHON_VERSION == 3.12* ]] || [[ $PYTHON_VERSION == 3.13* ]]; then
        PYTHON_EXE="python3"
        echo "  ✅ Found Python $PYTHON_VERSION"
    else
        echo "  ❌ Python 3.12+ not found (found $PYTHON_VERSION)"
        echo ""
        echo "Please install Python 3.12 or later:"
        echo "  Ubuntu/Debian: sudo apt-get install python3.12 python3.12-venv"
        echo "  Mac (Homebrew): brew install python@3.12"
        exit 1
    fi
elif command -v python &> /dev/null; then
    PYTHON_VERSION=$(python --version | awk '{print $2}')
    if [[ $PYTHON_VERSION == 3.12* ]] || [[ $PYTHON_VERSION == 3.13* ]]; then
        PYTHON_EXE="python"
        echo "  ✅ Found Python $PYTHON_VERSION"
    else
        echo "  ❌ Python 3.12+ not found (found $PYTHON_VERSION)"
        exit 1
    fi
else
    echo "  ❌ Python not found"
    echo ""
    echo "Please install Python 3.12:"
    echo "  Ubuntu/Debian: sudo apt-get install python3.12 python3.12-venv"
    echo "  Mac (Homebrew): brew install python@3.12"
    exit 1
fi

echo ""
echo "Running automated installation..."
echo ""

# Run the Python installation script
$PYTHON_EXE install.py

if [ $? -ne 0 ]; then
    echo ""
    echo "Installation encountered errors!"
    echo "Please check the output above for details"
    exit 1
fi

echo ""
echo "================================================================================"
echo "INSTALLATION SUCCESSFUL!"
echo "================================================================================"
echo ""
echo "To start the application:"
echo ""
echo "  1. Activate environment:"
echo "     source venv312/bin/activate"
echo ""
echo "  2. Start the application:"
echo "     python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "  3. Open in browser:"
echo "     http://localhost:8000"
echo ""
echo "For more information, see INSTALLATION_GUIDE.md"
echo ""
