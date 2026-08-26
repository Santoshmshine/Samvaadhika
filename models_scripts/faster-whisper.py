import os
from faster_whisper import WhisperModel

model_size = "small"
# Explicitly set your target visible folder directory
target_directory = "./models/faster-whisper-small"

print(f"Downloading faster-whisper small directly to {target_directory}...")

# Use download_root to force the download path
model = WhisperModel(
    model_size,
    device="cpu",
    compute_type="float32",
    download_root=target_directory
)

print("Download complete! Look inside your project folder now.")
