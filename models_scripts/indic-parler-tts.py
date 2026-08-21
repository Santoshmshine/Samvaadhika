import os
from huggingface_hub import login
from huggingface_hub import snapshot_download

# 1. Authenticate with your token (set HF_TOKEN env var or paste below)
login(os.environ.get("HF_TOKEN", "YOUR_HF_TOKEN_HERE"))

# Define your target directory
local_dir = "./models/indic-parler-tts"
os.makedirs(local_dir, exist_ok=True)

print(f"Downloading Indic Parler-TTS to {local_dir}...")
# This pulls the full model repository directly into your specific folder
snapshot_download(
    repo_id="ai4bharat/indic-parler-tts",
    local_dir=local_dir,
    local_dir_use_symlinks=False
)
print("Download complete!")
