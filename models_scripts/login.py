import os
from huggingface_hub import login

# Set HF_TOKEN env var or paste your token below
login(os.environ.get("HF_TOKEN", "YOUR_HF_TOKEN_HERE"))
