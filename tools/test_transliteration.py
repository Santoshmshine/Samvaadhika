#!/usr/bin/env python3
"""Small CLI to exercise `transliterate_text_if_needed` locally."""
import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path so `from app import ...` works when running this script
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def main():
    parser = argparse.ArgumentParser(description="Test transliteration helper")
    parser.add_argument("-t", "--text", help="Text to transliterate (or read from stdin)", default=None)
    parser.add_argument("-l", "--lang", help="Target language code (hi|mr)", default="mr")
    args = parser.parse_args()

    if args.text is None:
        import sys
        args.text = sys.stdin.read().strip()

    try:
        from app.pipeline import transliterate_text_if_needed
    except Exception as e:
        print(f"Failed to import transliteration helper: {e}")
        return

    out = transliterate_text_if_needed(args.text or "", args.lang)
    print("--- Original ---")
    print(args.text)
    print("--- Transliterated ---")
    print(out)

if __name__ == "__main__":
    main()
