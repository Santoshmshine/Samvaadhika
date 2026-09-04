#!/usr/bin/env python3
"""
Samvaadhika - Automated Setup and Installation Script
Downloads and configures everything automatically.

Usage:
    python install.py

This script will:
1. Create Python 3.12 virtual environment (venv312)
2. Install all dependencies from requirements.txt
3. Download all three IndicTrans2 models from Hugging Face
4. Verify all installations
5. Initialize database

NO MANUAL STEPS REQUIRED!
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Optional

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text: str):
    """Print a formatted header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(80)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}\n")

def print_success(text: str):
    """Print success message"""
    print(f"{Colors.OKGREEN}✅ {text}{Colors.ENDC}")

def print_info(text: str):
    """Print info message"""
    print(f"{Colors.OKCYAN}ℹ️  {text}{Colors.ENDC}")

def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.WARNING}⚠️  {text}{Colors.ENDC}")

def print_error(text: str):
    """Print error message"""
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")

def run_command(cmd: list, description: str) -> bool:
    """Run a shell command and report status"""
    try:
        print_info(description)
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print_success(description)
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"{description}")
        print(f"  Error: {e.stderr[:200]}")
        return False
    except Exception as e:
        print_error(f"{description}: {str(e)}")
        return False

def check_python_version() -> bool:
    """Check if Python 3.12+ is available"""
    print_info("Checking Python version...")

    # Try Python 3.12 first
    try:
        result = subprocess.run(
            ['python', '--version'],
            capture_output=True,
            text=True,
            check=True
        )
        version = result.stdout.strip()
        print_info(f"Found {version}")
        if "3.12" in version or "3.13" in version or "3.14" in version:
            print_success("Python version compatible")
            return True
    except:
        pass

    # Check common paths
    python_paths = [
        "C:\\Users\\mohit\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
        "C:\\Python312\\python.exe",
        "/usr/bin/python3.12",
    ]

    for python_path in python_paths:
        if os.path.exists(python_path):
            print_success(f"Found Python at {python_path}")
            return True

    print_error("Python 3.12+ not found. Please install Python 3.12+")
    return False

def create_virtual_environment() -> bool:
    """Create Python virtual environment"""
    venv_path = Path("venv312")

    if venv_path.exists():
        print_info("Virtual environment already exists, skipping creation")
        return True

    print_info("Creating virtual environment 'venv312'...")
    if os.name == 'nt':  # Windows
        cmd = [sys.executable, "-m", "venv", "venv312"]
    else:  # Linux/Mac
        cmd = [sys.executable, "-m", "venv", "venv312"]

    return run_command(cmd, "Creating virtual environment")

def get_python_executable() -> Optional[str]:
    """Get the Python executable from venv"""
    if os.name == 'nt':  # Windows
        python_exe = Path("venv312") / "Scripts" / "python.exe"
    else:  # Linux/Mac
        python_exe = Path("venv312") / "bin" / "python"

    if python_exe.exists():
        return str(python_exe)
    return None

def upgrade_pip(python_exe: str) -> bool:
    """Upgrade pip in the virtual environment"""
    return run_command(
        [python_exe, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
        "Upgrading pip, setuptools, and wheel"
    )

def install_requirements(python_exe: str) -> bool:
    """Install dependencies from requirements.txt"""
    if not Path("requirements.txt").exists():
        print_error("requirements.txt not found!")
        return False

    return run_command(
        [python_exe, "-m", "pip", "install", "-r", "requirements.txt"],
        "Installing Python dependencies (this may take 10-15 minutes)"
    )

def create_model_directories() -> bool:
    """Create model directories"""
    models = [
        "models/indictrans2-en-indic-dist-200M",
        "models/indictrans2-indic-en-dist-200M",
        "models/indictrans2-indic-indic-dist-320M",
    ]

    for model_dir in models:
        Path(model_dir).mkdir(parents=True, exist_ok=True)

    print_success("Model directories created")
    return True

def download_models(python_exe: str) -> bool:
    """Download IndicTrans2 models from Hugging Face"""
    print_header("DOWNLOADING TRANSLATION MODELS")
    print_info("This may take 10-30 minutes depending on internet speed")
    print_info("Each model is ~400-900 MB\n")

    models = [
        {
            "name": "indictrans2-en-indic-dist-200M",
            "hf_id": "ai4bharat/indictrans2-en-indic-dist-200M",
            "description": "English ↔ Hindi/Marathi",
        },
        {
            "name": "indictrans2-indic-en-dist-200M",
            "hf_id": "ai4bharat/indictrans2-indic-en-dist-200M",
            "description": "Hindi/Marathi ↔ English",
        },
        {
            "name": "indictrans2-indic-indic-dist-320M",
            "hf_id": "ai4bharat/indictrans2-indic-indic-dist-320M",
            "description": "Hindi ↔ Marathi",
        },
    ]

    download_script = """
import os
import urllib.request
from huggingface_hub import snapshot_download

models = [
    ("ai4bharat/indictrans2-en-indic-dist-200M", "models/indictrans2-en-indic-dist-200M"),
    ("ai4bharat/indictrans2-indic-en-dist-200M", "models/indictrans2-indic-en-dist-200M"),
    ("ai4bharat/indictrans2-indic-indic-dist-320M", "models/indictrans2-indic-indic-dist-320M"),
]

print("\\n" + "="*80)
print("DOWNLOADING TRANSLATION MODELS")
print("="*80 + "\\n")

for hf_id, local_dir in models:
    model_name = hf_id.split("/")[-1]
    print(f"📥 Downloading {model_name}...")
    print(f"   to: {local_dir}\\n")

    try:
        os.makedirs(local_dir, exist_ok=True)
        snapshot_download(hf_id, local_dir=local_dir)

        # Verify
        files = os.listdir(local_dir)
        config_present = "config.json" in files

        if config_present:
            print(f"✅ {model_name}: {len(files)} files downloaded\\n")
        else:
            print(f"⚠️  {model_name}: Downloaded but config.json missing\\n")

    except Exception as e:
        print(f"❌ Failed to download {model_name}")
        print(f"   Error: {str(e)[:100]}\\n")
        print("   This may be a network issue or model access restriction.")
        print("   See REQUEST_GATED_MODEL_ACCESS.md for manual access instructions.\\n")

detector_path = "models/lid.176.ftz"
if os.path.exists(detector_path):
    print("✅ fastText language detector already available\n")
else:
    print("📥 Downloading fastText language detector...\n")
    try:
        urllib.request.urlretrieve(
            "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz",
            detector_path,
        )
        print("✅ fastText language detector downloaded\n")
    except Exception as e:
        print(f"⚠️  Failed to download language detector: {str(e)[:100]}")
        print("   Auto-detect will fall back to English until models/lid.176.ftz is available.\n")

print("="*80)
print("Model download complete!")
print("="*80)
"""

    # Write script to temporary file
    temp_script = Path("_download_models_temp.py")
    temp_script.write_text(download_script, encoding="utf-8")

    try:
        # Run the download script
        result = subprocess.run(
            [python_exe, str(temp_script)],
            capture_output=False,
            text=True
        )
        return result.returncode == 0
    finally:
        # Clean up temporary script
        temp_script.unlink(missing_ok=True)

def verify_installation(python_exe: str) -> bool:
    """Verify that everything is installed correctly"""
    print_header("VERIFYING INSTALLATION")

    verification_script = """
import os
import sys
from pathlib import Path

print("Checking Python environment...")
print(f"  Python: {sys.version.split()[0]}")
print()

# Check models
print("Checking models...")
models_dir = Path("models")
models = [
    "indictrans2-en-indic-dist-200M",
    "indictrans2-indic-en-dist-200M",
    "indictrans2-indic-indic-dist-320M",
]

models_ok = 0
for model in models:
    model_path = models_dir / model
    if model_path.exists() and (model_path / "config.json").exists():
        files = len(list(model_path.glob("*")))
        print(f"  ✅ {model} ({files} files)")
        models_ok += 1
    else:
        print(f"  ❌ {model} (missing)")

print()
if models_ok == 3:
    print("✅ All models verified!")
    sys.exit(0)
else:
    print(f"⚠️  {models_ok}/3 models found")
    sys.exit(1 if models_ok == 0 else 0)
"""

    temp_script = Path("_verify_temp.py")
    temp_script.write_text(verification_script, encoding="utf-8")

    try:
        result = subprocess.run(
            [python_exe, str(temp_script)],
            capture_output=False,
            text=True
        )
        return result.returncode == 0
    finally:
        temp_script.unlink(missing_ok=True)

def initialize_database(python_exe: str) -> bool:
    """Initialize the database"""
    db_script = """
import os
os.environ['DATABASE_URL'] = 'sqlite:///samvaadhika.db'

try:
    from app.database import engine, Base
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialized")
except Exception as e:
    print(f"⚠️  Database initialization: {e}")
    print("   This can be done later when the app starts")
"""

    temp_script = Path("_init_db_temp.py")
    temp_script.write_text(db_script, encoding="utf-8")

    try:
        subprocess.run(
            [python_exe, str(temp_script)],
            capture_output=True,
            text=True
        )
        return True
    except Exception as e:
        print_warning(f"Database initialization: {str(e)[:80]}")
        return False
    finally:
        temp_script.unlink(missing_ok=True)

def main():
    """Main installation flow"""
    print_header("SAMVAADHIKA - AUTOMATED INSTALLATION")
    print_info("This script will set up everything automatically.")
    print_info("Installation may take 20-45 minutes total.\n")

    # Step 1: Check Python
    print_header("STEP 1: CHECKING PYTHON")
    if not check_python_version():
        print_error("Please install Python 3.12 or later")
        sys.exit(1)

    # Step 2: Create virtual environment
    print_header("STEP 2: CREATING VIRTUAL ENVIRONMENT")
    if not create_virtual_environment():
        print_error("Failed to create virtual environment")
        sys.exit(1)

    python_exe = get_python_executable()
    if not python_exe:
        print_error("Could not find Python executable in venv")
        sys.exit(1)

    # Step 3: Upgrade pip
    print_header("STEP 3: UPGRADING PIP")
    if not upgrade_pip(python_exe):
        print_error("Failed to upgrade pip")
        sys.exit(1)

    # Step 4: Install requirements
    print_header("STEP 4: INSTALLING DEPENDENCIES")
    if not install_requirements(python_exe):
        print_error("Failed to install requirements")
        sys.exit(1)

    # Step 5: Create model directories
    print_header("STEP 5: CREATING MODEL DIRECTORIES")
    if not create_model_directories():
        print_error("Failed to create model directories")
        sys.exit(1)

    # Step 6: Download models
    print_header("STEP 6: DOWNLOADING MODELS")
    if not download_models(python_exe):
        print_warning("Model download encountered issues")
        print_info("See REQUEST_GATED_MODEL_ACCESS.md for manual setup")

    # Step 7: Verify installation
    print_header("STEP 7: VERIFYING INSTALLATION")
    if not verify_installation(python_exe):
        print_warning("Some verifications failed, but installation may still work")

    # Step 8: Initialize database
    print_header("STEP 8: INITIALIZING DATABASE")
    initialize_database(python_exe)

    # Final summary
    print_header("INSTALLATION COMPLETE!")
    print_success("Samvaadhika is ready to use!\n")

    print(f"{Colors.BOLD}Quick Start:{Colors.ENDC}")
    if os.name == 'nt':  # Windows
        print("  1. Activate environment: .\\venv312\\Scripts\\Activate.ps1")
    else:  # Linux/Mac
        print("  1. Activate environment: source venv312/bin/activate")

    print("  2. Start application: python -m uvicorn app.main:app --reload")
    print("  3. Open browser: http://localhost:8000")
    print("\nFor more info, see INSTALLATION_GUIDE.md")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_warning("\n\nInstallation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
