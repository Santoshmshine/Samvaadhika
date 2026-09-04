# 🎯 START HERE - Samvaadhika Installation

Welcome! You've found the Samvaadhika offline translation platform. Follow this quick guide to get started.

## ⚡ Super Quick Start (1-2 minutes)

### Choose Your Platform:

#### 🪟 Windows
```powershell
# Just run this one command:
.\install.ps1
```
If that doesn't work, try this in PowerShell:
```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
.\install.ps1
```

#### 🐧 Linux
```bash
chmod +x install.sh
./install.sh
```

#### 🍎 macOS
```bash
chmod +x install.sh
./install.sh
```

---

## ⏱️ What Happens Next

1. **Checks Python** (10 seconds)
   - Verifies Python 3.12+ is installed
   - Shows error if missing

2. **Creates Environment** (2-3 minutes)
   - Sets up isolated Python workspace
   - Installs all dependencies

3. **Downloads Models** (10-30 minutes)
   - Gets 3 translation models (~1.8 GB)
   - This is the longest part
   - Speed depends on your internet

4. **Verifies Everything** (1-2 minutes)
   - Tests all components
   - Shows success/error report

5. **Ready to Use!** ✅
   - Application is configured
   - Models are downloaded
   - You're ready to translate

**Total Time: 20-45 minutes** (first time only)

---

## 📋 Before You Start

Check that you have:
- ✅ **Python 3.12+** - [Install if needed](https://www.python.org/downloads/)
- ✅ **2.5 GB free space** - For models and dependencies
- ✅ **Internet connection** - For model downloads
- ✅ **Windows 7+, Linux, or macOS 10.14+** - Any recent OS

## 🆘 Python Not Installed?

### Windows
1. Go to https://www.python.org/downloads/
2. Click "Download Python 3.12" (or newer)
3. Run the installer
4. ✅ **IMPORTANT**: Check the box "Add Python to PATH"
5. Click Install
6. Then run `install.ps1`

### Linux (Ubuntu/Debian)
```bash
sudo apt-get update
sudo apt-get install python3.12 python3.12-venv
```

### macOS (Homebrew)
```bash
brew install python@3.12
```

---

## 🚀 Start Installation

**Pick your platform above** and run the one-line command.

The installer will:
- ✅ Check Python version
- ✅ Create virtual environment
- ✅ Download and install dependencies
- ✅ Download translation models
- ✅ Verify everything works
- ✅ Show you how to start

**Just run it and let it work!** ☕

---

## ✅ After Installation

When you see:
```
✅ INSTALLATION SUCCESSFUL!
```

Open a new terminal and run:

### Windows (PowerShell)
```powershell
.\venv312\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

### Linux/Mac
```bash
source venv312/bin/activate
python -m uvicorn app.main:app --reload
```

Then open: **http://localhost:8000** in your browser 🌐

---

## 📚 Need More Details?

| Document | Read When |
|----------|-----------|
| [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md) | Having installation problems |
| [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | Need quick commands |
| [README_INSTALLATION.md](README_INSTALLATION.md) | Want to know what this is |
| [README.md](README.md) | Need model setup details |

---

## 🆘 Something Went Wrong?

**Python not found?**
→ Install Python 3.12+ from python.org

**Installation hangs?**
→ Check internet connection, restart

**Models won't download?**
→ Check free disk space (~2.5 GB needed)

**Still stuck?**
→ See [INSTALLATION_GUIDE.md - Troubleshooting](INSTALLATION_GUIDE.md#-troubleshooting)

---

## 🎯 What You Get

After installation:
- ✅ **6 Translation Directions**: EN↔HI, EN↔MR, HI↔MR
- ✅ **Offline Translation**: No internet needed after setup
- ✅ **REST API**: Ready-to-use endpoints
- ✅ **Web Interface**: Easy-to-use dashboard
- ✅ **High Quality**: 82-88% confidence scores
- ✅ **Fast**: 0.5-0.8 seconds per translation

---

## 🚀 Ready?

Choose your platform:

**Windows:**
```powershell
.\install.ps1
```

**Linux/Mac:**
```bash
./install.sh
```

---

## 💡 Pro Tips

1. **Don't close terminal** during installation
2. **Check internet speed** - model download takes 10-30 minutes
3. **First translation is slow** - models load in 2-3 seconds
4. **Subsequent translations are fast** - ~0.5-0.8 seconds
5. **Leave plenty of disk space** - models need ~1.8 GB

---

## 📞 Quick Help

| Issue | Solution |
|-------|----------|
| Python not found | Install from python.org |
| Download slow | Normal for first time; 10-30 min typical |
| Port 8000 in use | Use `--port 8001` with uvicorn |
| Out of disk space | Delete old files or upgrade drive |
| Still stuck | See INSTALLATION_GUIDE.md troubleshooting |

---

**Status**: ✅ Ready to Install
**Time Needed**: 20-45 minutes
**Difficulty**: ⭐ Easy (automated)

**Now run the installer for your platform above!** 🚀
