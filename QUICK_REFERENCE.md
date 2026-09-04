# ⚡ Quick Reference Guide

## 🚀 Installation (One Command)

### Windows
```powershell
install.ps1
```
Or from PowerShell:
```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
.\install.ps1
```

### Linux/Mac
```bash
./install.sh
```

## 📋 After Installation

### Activate Environment
```powershell
# Windows
.\venv312\Scripts\Activate.ps1

# Linux/Mac
source venv312/bin/activate
```

### Start Application
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Open in Browser
```
http://localhost:8000
```

## 💬 Translation Commands

### Python
```python
from app.pipeline import translate_text

# English to Hindi
result, conf = translate_text("My name is Mohit", "en", "hi")
print(result)  # मेरा नाम मोहित है ।

# Hindi to English
result, conf = translate_text("मेरा नाम मोहित है", "hi", "en")
print(result)  # My name is Mohit.

# Hindi to Marathi
result, conf = translate_text("मेरा नाम मोहित है", "hi", "mr")
print(result)  # माझे नाव मोहित आहे.
```

### REST API
```bash
# English to Hindi
curl -X POST http://localhost:8000/translate \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello","source_language":"en","target_language":"hi"}'

# Hindi to English
curl -X POST http://localhost:8000/translate \
  -H "Content-Type: application/json" \
  -d '{"text":"नमस्ते","source_language":"hi","target_language":"en"}'
```

## 🔍 Verification

```bash
# Test translation
python -c "from app.pipeline import translate_text; print(translate_text('Hello', 'en', 'hi'))"

# List models
ls -la models/  # Linux/Mac
dir models\    # Windows
```

## 📊 Language Pairs

| From | To | Status |
|------|-----|--------|
| en | hi | ✅ |
| en | mr | ✅ |
| hi | en | ✅ |
| mr | en | ✅ |
| hi | mr | ✅ |
| mr | hi | ✅ |

## 🗂️ Important Files

| File | Purpose |
|------|---------|
| `install.ps1` | Windows installer |
| `install.sh` | Linux/Mac installer |
| `install.py` | Main installer (all platforms) |
| `app/pipeline.py` | Translation engine |
| `requirements.txt` | Python dependencies |
| `samvaadhika.db` | SQLite database |

## 📁 Directory Structure

```
Samvaadhika/
├── venv312/                        # Python environment
├── models/
│   ├── indictrans2-en-indic-dist-200M/
│   ├── indictrans2-indic-en-dist-200M/
│   └── indictrans2-indic-indic-dist-320M/
├── app/                           # Application code
├── uploads/                       # User uploads
├── outputs/                       # Generated files
├── cache/                         # Cache files
└── samvaadhika.db                # Database
```

## 🔧 Common Tasks

### Clear Model Cache
```bash
rm -rf models/.cache  # Linux/Mac
rmdir /S models\.cache  # Windows
```

### Reinstall Dependencies
```bash
python -m pip install -r requirements.txt --force-reinstall
```

### Reset Database
```bash
rm samvaadhika.db  # Linux/Mac
del samvaadhika.db  # Windows
```

### View Logs
```bash
tail -f samvaadhika.log  # Linux/Mac
Get-Content samvaadhika.log -Tail 20 -Wait  # Windows
```

## ⚙️ Configuration

Edit `app/config.py` to modify:
- Model paths
- Database URL
- Server settings
- Cache directory
- Log level

## 📞 Troubleshooting

### Python Not Found
```bash
# Windows: Add to PATH
# Linux/Mac: Install python3.12
sudo apt-get install python3.12
```

### Model Download Fails
```bash
# Try again (resumes where it stopped)
python install.py

# Check internet connection
ping google.com
```

### Port Already in Use
```bash
# Use different port
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### Low Memory
- Close other applications
- Increase available RAM
- Use smaller models (if available)

## 📚 Documentation

| Document | Content |
|----------|---------|
| [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md) | Detailed setup |
| [README_INSTALLATION.md](README_INSTALLATION.md) | Overview & features |
| [README.md](README.md) | Application overview and model setup |

## 🎯 Common Usage Patterns

### Translate Single Text
```python
result, conf = translate_text("Hello", "en", "hi")
```

### Batch Translation
```python
texts = ["Hello", "Good morning", "Thank you"]
for text in texts:
    result, conf = translate_text(text, "en", "hi")
    print(f"{text} → {result}")
```

### With Error Handling
```python
try:
    result, conf = translate_text(text, src, tgt)
    if conf >= 0.80:
        print(f"High quality: {result}")
    else:
        print(f"Lower quality: {result}")
except Exception as e:
    print(f"Error: {e}")
```

## ✅ Verification Checklist

After installation, verify:
- [ ] Python 3.12+ available
- [ ] Virtual environment created (venv312)
- [ ] All dependencies installed
- [ ] Three models downloaded
- [ ] Database initialized
- [ ] All 6 translations working
- [ ] Web server starts
- [ ] Browser access works

## 📈 Performance Tips

1. **First Run**: Allow 2-3 seconds for model loading
2. **Subsequent Runs**: ~0.5-0.8 seconds per translation
3. **Batch Mode**: Group translations for efficiency
4. **Memory**: Keep 2-3 GB free for model loading
5. **CPU**: Multi-core processor improves speed

## 🔒 Security

✅ No data sent to cloud
✅ All processing local
✅ No telemetry/tracking
✅ No authentication required (by default)
✅ Can add authentication in app/auth.py

## 🎓 Learning Resources

- API Documentation: Built into FastAPI
- Model Details: See [README.md](README.md)
- Installation Help: [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md)
- Architecture: [BAIF_Translation_Platform_Design (1).md](BAIF_Translation_Platform_Design%20(1).md)

## 🚀 Production Deployment

1. Set `DEBUG=False` in app/config.py
2. Use production ASGI server (e.g., Gunicorn)
3. Set up reverse proxy (Nginx/Apache)
4. Configure SSL/TLS
5. Set up monitoring & logging
6. Database backups

## 📞 Getting Help

1. Check relevant documentation
2. Review application logs
3. Run verification script
4. Check system requirements
5. Verify internet connection

---

**Last Updated**: September 2, 2026
**Status**: ✅ Ready to Use
**All Systems**: Operational
