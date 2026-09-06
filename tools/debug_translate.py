#!/usr/bin/env python3
"""Debug script: run language detection and translation helpers locally.

Usage:
  python tools/debug_translate.py --text "..." --src mr --tgt en
  echo "..." | python tools/debug_translate.py --src mr --tgt en
"""
import sys
from pathlib import Path
import argparse

# Make repo importable
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--text", help="Text to test. If omitted, read stdin", default=None)
    parser.add_argument("--src", help="Source language code (en|hi|mr)", default=None)
    parser.add_argument("--tgt", help="Target language code (en|hi|mr)", default=None)
    args = parser.parse_args()

    if args.text is None:
        args.text = sys.stdin.read().strip()

    if not args.text:
        print("No text provided. Use --text or pipe content to stdin.")
        return 2

    from app.pipeline import detect_language, translate_text, _find_model_dir

    print("INPUT:\n", args.text)
    try:
        detected = detect_language(args.text)
    except Exception as e:
        detected = f"<error: {e}>"
    print("detected:", detected)

    if args.src and args.tgt:
        print(f"\ntranslate_text {args.src}→{args.tgt}:")
        try:
            out, conf = translate_text(args.text, args.src, args.tgt)
            print("  confidence:", conf)
            print("  output:\n", out)
        except Exception as e:
            print("  error:", e)

    # Helpful quick checks for Marathi↔English directions
    for (s, t) in [("mr", "en"), ("en", "mr")]:
        print(f"\ntranslate_text {s}→{t} (probe):")
        try:
            out, conf = translate_text(args.text, s, t)
            print("  confidence:", conf)
            print("  output:\n", out[:1000])
        except Exception as e:
            print("  error:", e)

    # Show IndicTrans2 model dirs if present
    try:
        print("\nIndicTrans2 model dirs:")
        print("  en->mr:", _find_model_dir("indictrans2-en-indic-dist-200M", "indictrans2"))
        print("  mr->en:", _find_model_dir("indictrans2-indic-en-dist-200M", "indictrans2"))
    except Exception as e:
        print("  error locating model dirs:", e)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
