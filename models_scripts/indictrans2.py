import os
from huggingface_hub import login
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

# Replace this with a NEW token since the old one was exposed
login("YOUR_HF_TOKEN_HERE")

model_name = "ai4bharat/indictrans2-en-indic-dist-200M"
# Define your local visible directory
target_directory = "./models/indictrans2-en-indic-dist-200M"

print(f"Downloading tokenizer directly to {target_directory}...")
tokenizer = AutoTokenizer.from_pretrained(
    model_name, 
    trust_remote_code=True,
    cache_dir=target_directory
)

print(f"Downloading model weights directly to {target_directory}...")
model = AutoModelForSeq2SeqLM.from_pretrained(
    model_name, 
    trust_remote_code=True,
    cache_dir=target_directory
)

print("Successfully downloaded! Check your local folder now.")
