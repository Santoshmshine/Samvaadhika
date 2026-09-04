from pathlib import Path

from huggingface_hub import snapshot_download

model_name = "ai4bharat/indictrans2-en-indic-dist-200M"
target_directory = Path(__file__).resolve().parent.parent / "models" / "indictrans2"

print(f"Downloading {model_name} to {target_directory}...")
snapshot_download(
    repo_id=model_name,
    local_dir=str(target_directory),
)

print("Successfully downloaded. The application can now load the local checkpoint.")
