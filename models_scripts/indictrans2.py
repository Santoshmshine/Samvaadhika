import os
from pathlib import Path
from huggingface_hub import login

from huggingface_hub import snapshot_download

# Set HF_TOKEN env var or paste your token below
login(os.environ.get("HF_TOKEN"))

model_name = "ai4bharat/indictrans2-indic-indic-dist-320M"
target_directory = Path(__file__).resolve().parent.parent / "models" / "indictrans2-indic-indic-dist-320M"
token = os.environ.get("HF_TOKEN") or None

print(f"Downloading the complete model repository to {target_directory}...")
snapshot_download(
    repo_id=model_name,
    local_dir=str(target_directory),
    token=token,
    resume_download=True,
)

print("Successfully downloaded. Verify that model weights and tokenizer files are present.")
