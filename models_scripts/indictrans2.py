import os
from pathlib import Path

from huggingface_hub import snapshot_download

model_name = "ai4bharat/indictrans2-en-indic-dist-200M"
target_directory = Path(__file__).resolve().parent.parent / "models" / "indictrans2-en-indic-dist-200M"
token = os.environ.get("HF_TOKEN") or None

print(f"Downloading the complete model repository to {target_directory}...")
snapshot_download(
    repo_id=model_name,
    local_dir=str(target_directory),
    token=token,
    resume_download=True,
)

print("Successfully downloaded. Verify that model weights and tokenizer files are present.")
