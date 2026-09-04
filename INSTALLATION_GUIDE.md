# 🚀 Samvaadhika Installation Guide

## Quick Start (Fully Automated)

Choose your platform below for a **one-command installation** that downloads everything automatically:

---

## 🪟 Windows Installation

### Prerequisites
- Windows 7 or later
- Python 3.12+ ([download here](https://www.python.org/downloads/))
- Internet connection (for model downloads)

### Installation Steps

**Option 1: Double-click (Easiest)**
1. Download the repository
2. Navigate to the folder in File Explorer
3. **Double-click `install.ps1`**
4. Follow the on-screen prompts
5. Installation complete! ✅

**Option 2: PowerShell**
1. Open PowerShell as Administrator
2. Navigate to the project folder:
   ```powershell
   cd C:\Users\[YourUsername]\git\Samvaadhika
   ```
3. Run the installer:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
   .\install.ps1
   ```
4. Wait for installation to complete

**Option 3: Command Prompt**
1. Open Command Prompt (`cmd.exe`)
2. Navigate to the project folder:
   ```cmd
   cd C:\Users\[YourUsername]\git\Samvaadhika
   ```
3. Run the installer:
   ```cmd
   python install.py
   ```

### What Gets Installed
- ✅ Python 3.12 virtual environment (venv312)
- ✅ 150+ Python packages
- ✅ All three IndicTrans2 models (~1.8 GB)
- ✅ SQLite database
- ✅ Full verification

### Time Required
- First installation: **20-45 minutes**
  - Virtual environment: 2-3 min
  - Dependencies: 5-10 min
  - Models download: 10-30 min (depending on internet)
  - Verification: 1-2 min
- Subsequent installations: **5-10 minutes** (models cached)

### After Installation
```powershell
# Activate the environment
.\venv312\Scripts\Activate.ps1

# Start the application
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Open in browser
Start-Process http://localhost:8000
```

---

## 🐧 Linux Installation

### Prerequisites
- Linux (Ubuntu, Debian, CentOS, Fedora, etc.)
- Python 3.12+
- Internet connection (for model downloads)

### Installation Steps

**Ubuntu/Debian:**
```bash
# 1. Install Python 3.12 (if not already installed)
sudo apt-get update
sudo apt-get install python3.12 python3.12-venv

# 2. Clone/download the repository
cd ~/git  # or your preferred location
git clone https://github.com/yourusername/Samvaadhika.git
cd Samvaadhika

# 3. Run the automated installer
chmod +x install.sh
./install.sh
```

**CentOS/RHEL:**
```bash
# 1. Install Python 3.12
sudo dnf install python3.12 python3.12-devel

# 2. Clone/download repository
cd ~/git
git clone https://github.com/yourusername/Samvaadhika.git
cd Samvaadhika

# 3. Run the automated installer
chmod +x install.sh
./install.sh
```

**Fedora:**
```bash
# 1. Install Python 3.12
sudo dnf install python3.12 python3.12-devel

# 2. Run installation
chmod +x install.sh
./install.sh
```

### Time Required
- First installation: **20-45 minutes**
- Subsequent installations: **5-10 minutes**

### After Installation
```bash
# Activate the environment
source venv312/bin/activate

# Start the application
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Open in browser (if GUI available)
xdg-open http://localhost:8000
```

---

## 🍎 macOS Installation

### Prerequisites
- macOS 10.14+
- Python 3.12+ (via Homebrew recommended)
- Internet connection

### Installation Steps

**Using Homebrew (Recommended):**
```bash
# 1. Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. Install Python 3.12
brew install python@3.12

# 3. Clone/download repository
cd ~/git  # or your preferred location
git clone https://github.com/yourusername/Samvaadhika.git
cd Samvaadhika

# 4. Run the automated installer
chmod +x install.sh
./install.sh
```

**Using MacPorts:**
```bash
# 1. Install Python 3.12
sudo port install python312

# 2. Navigate and install
cd ~/git/Samvaadhika
chmod +x install.sh
./install.sh
```

### Time Required
- First installation: **20-45 minutes**
- Subsequent installations: **5-10 minutes**

### After Installation
```bash
# Activate the environment
source venv312/bin/activate

# Start the application
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Open in browser
open http://localhost:8000
```

---

## 📋 What the Installer Does

### Automatically Performed Steps:
1. **Checks Python Version** - Verifies Python 3.12+ is available
2. **Creates Virtual Environment** - Isolated Python environment (venv312)
3. **Upgrades pip** - Latest package manager
4. **Installs Dependencies** - All packages from requirements.txt
5. **Creates Model Directories** - Proper folder structure
6. **Downloads Models** - All three IndicTrans2 models:
   - indictrans2-en-indic-dist-200M (English ↔ Hindi/Marathi)
   - indictrans2-indic-en-dist-200M (Hindi/Marathi ↔ English)
   - indictrans2-indic-indic-dist-320M (Hindi ↔ Marathi)
7. **Initializes Database** - SQLite for job tracking
8. **Verifies Installation** - Tests all components
9. **Prints Summary** - Ready-to-use instructions

### Models Downloaded (~1.8 GB total):
```
✅ indictrans2-en-indic-dist-200M
   Size: 445 MB
   Purpose: English → Hindi/Marathi
   Files: 20

✅ indictrans2-indic-en-dist-200M
   Size: 445 MB
   Purpose: Hindi/Marathi → English
   Files: 16

✅ indictrans2-indic-indic-dist-320M
   Size: 896 MB
   Purpose: Hindi ↔ Marathi
   Files: 17
```

---

## 🔧 Troubleshooting

### Problem: Python Not Found
**Solution:**
- Windows: Add Python to PATH during installation
- Linux: `sudo apt-get install python3.12 python3.12-venv`
- Mac: `brew install python@3.12`

### Problem: Permission Denied (Linux/Mac)
**Solution:**
```bash
chmod +x install.sh
./install.sh
```

### Problem: Model Download Fails
**Reason:** Some models are gated (access control)
**Solution:** See [REQUEST_GATED_MODEL_ACCESS.md](REQUEST_GATED_MODEL_ACCESS.md)

### Problem: Insufficient Disk Space
**Required:** ~2.5 GB total
- 100 MB for Python environment
- 150 MB for dependencies
- 1.8 GB for models
- 250 MB for system/cache

### Problem: Network Timeout
**Solution:** Model downloads may timeout on slow connections
- Retry: `python install.py` (resumes where it left off)
- Check internet: `ping google.com`
- Move closer to router or use wired connection

### Problem: Virtual Environment Not Activating
**Windows:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
.\venv312\Scripts\Activate.ps1
```

**Linux/Mac:**
```bash
source venv312/bin/activate
```

---

## ✅ Verify Installation

After installation completes successfully, verify everything:

**Using Command Line:**
```powershell
# Windows
.\venv312\Scripts\python.exe -c "from app.pipeline import translate_text; print(translate_text('Hello', 'en', 'hi'))"

# Linux/Mac
source venv312/bin/activate
python -c "from app.pipeline import translate_text; print(translate_text('Hello', 'en', 'hi'))"
```

---

## 🚀 Start Using Samvaadhika

### Quick Test
```python
from app.pipeline import translate_text

# English to Hindi
result, confidence = translate_text("My name is Mohit", "en", "hi")
print(result)  # Output: मेरा नाम मोहित है ।
```

### Start Web Application
```bash
# Activate environment
source venv312/bin/activate  # Linux/Mac
.\venv312\Scripts\Activate.ps1  # Windows

# Start server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Open browser
http://localhost:8000
```

### API Usage
```bash
curl -X POST http://localhost:8000/translate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello world",
    "source_language": "en",
    "target_language": "hi"
  }'
```

---

## 📚 Documentation

- **[README.md](README.md)** - Application overview and model setup
- **[REQUEST_GATED_MODEL_ACCESS.md](REQUEST_GATED_MODEL_ACCESS.md)** - Manual model access

---

## 💡 Tips

1. **First Run is Slow**: Model downloads take time, but subsequent runs are fast
2. **Leave Terminal Open**: Don't close during installation
3. **Check Internet**: Model downloads require stable connection
4. **Disk Space**: Ensure ~2.5 GB free space
5. **Python 3.12+**: Older Python versions not supported
6. **Admin Rights**: Not required for installation (Windows)

---

## 🆘 Getting Help

If installation fails:
1. Check error messages above
2. Review [Troubleshooting](#troubleshooting) section
3. Verify Python version: `python --version`
4. Check disk space: `df -h` (Linux/Mac) or `dir C:\` (Windows)
5. Test internet: Try downloading a file manually
6. See documentation files for more details

---

## 📦 Installation Verification

After successful installation, your directory should contain:
```
Samvaadhika/
├── venv312/                          ← Virtual environment
├── models/
│   ├── indictrans2-en-indic-dist-200M/     ✅
│   ├── indictrans2-indic-en-dist-200M/     ✅
│   └── indictrans2-indic-indic-dist-320M/  ✅
├── app/                             ← Application code
├── samvaadhika.db                   ← Database
├── install.py                       ← Main installer
├── install.ps1                      ← PowerShell installer
├── install.sh                       ← Bash installer
└── [other files]
```

---

**Ready to Go!** 🎉

You now have a fully functional Samvaadhika installation with:
- ✅ All translation models
- ✅ Complete dependencies
- ✅ Production-ready configuration
- ✅ Full bidirectional language support

Start translating! 🌍
