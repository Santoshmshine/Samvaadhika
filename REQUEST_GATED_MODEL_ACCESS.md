# Requesting Access to Gated IndicTrans2 Models

## Overview
You need access to two gated repositories from AI4Bharat to enable full bidirectional translation:
1. **indictrans2-indic-en-dist-200M** - Indic languages (Hindi, Marathi) → English
2. **indictrans2-indic-indic-dist-320M** - Hindi ↔ Marathi cross-lingual translation

---

## Step 1: Access Repository 1 (Indic→English)

### 1a. Visit the Repository
Open this link in your browser:
```
https://huggingface.co/ai4bharat/indictrans2-indic-en-dist-200M
```

### 1b. Request Access
1. Click the **"Agree and access repository"** button (or similar)
2. You'll see a form requesting access
3. Fill in your details:
   - **Name**: Your full name
   - **Organization**: (optional) Your organization
   - **Purpose**: "Translation application for Hindi/Marathi to English"
4. Accept the license terms
5. Click **Submit** / **Request Access**

**Expected Response Time**: Usually instant to a few minutes

---

## Step 2: Access Repository 2 (Indic↔Indic)

### 2a. Visit the Repository
```
https://huggingface.co/ai4bharat/indictrans2-indic-indic-dist-320M
```

### 2b. Request Access
Repeat the same process as Step 1b

---

## Step 3: Verify Access (After Approval)

Once both repositories grant access, verify you can download them:

```powershell
cd C:\Users\mohit\git\Samvaadhika

# Activate the venv
.\venv312\Scripts\Activate.ps1

# Run this Python command to test access
python -c "
from huggingface_hub import snapshot_download
import os

print('Testing access to indictrans2-indic-en-dist-200M...')
try:
    snapshot_download('ai4bharat/indictrans2-indic-en-dist-200M', local_dir='models/indictrans2-indic-en-dist-200M', local_dir_use_symlinks=False)
    print('✅ Successfully downloaded indictrans2-indic-en-dist-200M')
except Exception as e:
    print(f'❌ Access denied or error: {e}')
"
```

---

## Step 4: Download the Models (Once Access Approved)

### Download via Python Script
```powershell
.\venv312\Scripts\python.exe << 'EOF'
from huggingface_hub import snapshot_download
import os

models = [
    'ai4bharat/indictrans2-indic-en-dist-200M',
    'ai4bharat/indictrans2-indic-indic-dist-320M'
]

for model_id in models:
    model_name = model_id.split('/')[-1]
    local_dir = f'models/{model_name}'

    print(f'\n📥 Downloading {model_name}...')
    try:
        snapshot_download(model_id, local_dir=local_dir, local_dir_use_symlinks=False)
        print(f'✅ Successfully downloaded to {local_dir}')
    except Exception as e:
        print(f'❌ Failed to download {model_name}: {e}')
EOF
```

### Alternative: Using HF CLI
```powershell
# Login to Hugging Face (optional but recommended for faster downloads)
.\venv312\Scripts\python.exe -c "from huggingface_hub import login; login()"

# Download models
.\venv312\Scripts\python.exe -m huggingface_hub.commands.download ai4bharat/indictrans2-indic-en-dist-200M --local-dir models/indictrans2-indic-en-dist-200M --local-dir-use-symlinks False

.\venv312\Scripts\python.exe -m huggingface_hub.commands.download ai4bharat/indictrans2-indic-indic-dist-320M --local-dir models/indictrans2-indic-indic-dist-320M --local-dir-use-symlinks False
```

---

## Step 5: Verify Installation

After downloading, run this test:

```powershell
cd C:\Users\mohit\git\Samvaadhika
.\venv312\Scripts\Activate.ps1

python -c "
from app.pipeline import translate_text

test_cases = [
    ('मेरा नाम मोहित है', 'hi', 'en', 'Hindi→English'),
    ('माझे नाव मोहित आहे', 'mr', 'en', 'Marathi→English'),
    ('मेरा नाम मोहित है', 'hi', 'mr', 'Hindi→Marathi'),
]

print('Testing all translation directions...\n')
for text, src, tgt, label in test_cases:
    try:
        result, conf = translate_text(text, src, tgt)
        print(f'✅ {label}')
        print(f'   Input:  {text}')
        print(f'   Output: {result}')
        print(f'   Confidence: {conf}\n')
    except Exception as e:
        print(f'❌ {label}: {e}\n')
"
```

---

## Troubleshooting

### "403 Client Error: Forbidden"
- **Cause**: Access not yet granted
- **Solution**: Wait a few minutes and retry. Check your email for any approval notifications

### "Access to model ... is restricted"
- **Cause**: Your request is still pending
- **Solution**: Visit the Hugging Face repo page and check the access request status

### "Cannot find module 'huggingface_hub'"
- **Solution**: Ensure venv is activated
  ```powershell
  .\venv312\Scripts\Activate.ps1
  python -m pip install huggingface_hub
  ```

### Downloaded but Translation Still Fails
- **Check**: Verify model files exist
  ```powershell
  Get-ChildItem models/indictrans2-indic-en-dist-200M | Select-Object Name
  Get-ChildItem models/indictrans2-indic-indic-dist-320M | Select-Object Name
  ```
- **Fix**: Restart Python/the application to reload models

---

## Expected Results After Setup

Once access is granted and models downloaded:

| Direction | Model | Confidence | Status |
|-----------|-------|-----------|--------|
| en → hi | indictrans2-en-indic-dist-200M | 0.88 | ✅ Working |
| en → mr | indictrans2-en-indic-dist-200M | 0.88 | ✅ Working |
| hi → en | indictrans2-indic-en-dist-200M | 0.85 | ✅ **NEW** |
| mr → en | indictrans2-indic-en-dist-200M | 0.85 | ✅ **NEW** |
| hi → mr | indictrans2-indic-indic-dist-320M | 0.82 | ✅ **NEW** |
| mr → hi | indictrans2-indic-indic-dist-320M | 0.82 | ✅ **NEW** |

---

## Quick Reference

**Repository URLs:**
- Indic→English: https://huggingface.co/ai4bharat/indictrans2-indic-en-dist-200M
- Indic↔Indic: https://huggingface.co/ai4bharat/indictrans2-indic-indic-dist-320M

**Model Download Paths:**
- `models/indictrans2-indic-en-dist-200M/`
- `models/indictrans2-indic-indic-dist-320M/`

**Activation:**
```powershell
.\venv312\Scripts\Activate.ps1
```

---

## Notes

1. **License**: These models are under a research/non-commercial license. Check the repository for specific terms.
2. **HF Token**: For faster/more reliable downloads, create a Hugging Face account and generate a token
3. **Time**: Each model is ~700MB-1GB, so downloads may take 5-15 minutes depending on internet speed
4. **Offline**: Once downloaded, models work completely offline

Let me know when access is granted and I can help with downloading the models!
