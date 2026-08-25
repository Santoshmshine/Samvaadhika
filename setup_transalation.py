import os
import sys
from pathlib import Path
import argostranslate.package
import argostranslate.translate

def setup_native_translation_models():
    # 1. Target language definitions
    target_pairs = [
        {"from": "en", "to": "hi", "name": "English -> Hindi"},
        {"from": "en", "to": "mr", "name": "English -> Marathi"}
    ]

    print("🌐 Synchronizing Argos Translate Package Index...")
    try:
        # Pulls the latest valid release links natively from the official source
        argostranslate.package.update_package_index()
        print("✅ Package index updated successfully.\n")
    except Exception as e:
        print(f"❌ Failed to update package index: {e}")
        sys.exit(1)

    # Fetch all available official packages
    available_packages = argostranslate.package.get_available_packages()

    # 2. Iterate and natively install targeted pairs
    for pair in target_pairs:
        print(f"⚙ Processing {pair['name']}...")
        
        # Filter the matching package from the official index
        matched_pkg = next(
            (pkg for pkg in available_packages if pkg.from_code == pair["from"] and pkg.to_code == pair["to"]),
            None
        )

        if not matched_pkg:
            print(f"❌ Could not find an official package for {pair['name']} in the index.\n")
            continue

        try:
            # Check if already registered to avoid redundant downloads
            installed_packages = argostranslate.package.get_installed_packages()
            is_installed = any(
                pkg.from_code == pair["from"] and pkg.to_code == pair["to"] 
                for pkg in installed_packages
            )

            if is_installed:
                print(f"✔ {pair['name']} is already registered locally. Skipping download.\n")
                continue

            # Natively downloads and extracts the validated zip archive
            print(f"📥 Downloading and extracting valid archive for {pair['name']}...")
            downloaded_file_path = matched_pkg.download()
            
            # Install the verified file path
            argostranslate.package.install_from_path(downloaded_file_path)
            print(f"🚀 {pair['name']} successfully registered and live!\n")

        except Exception as install_error:
            print(f"❌ Native installation failed for {pair['name']}: {install_error}\n")

    # 3. Validation Pipeline
    print("=== Running Operational Diagnostics ===")
    try:
        test_string = "Hello, welcome to our application setup."
        
        # Translate to Hindi
        hi_result = argostranslate.translate.translate(test_string, "en", "hi")
        print(f"📝 [en -> hi]\n   Input:  {test_string}\n   Output: {hi_result}\n")
        
        # Translate to Marathi
        mr_result = argostranslate.translate.translate(test_string, "en", "mr")
        print(f"📝 [en -> mr]\n   Input:  {test_string}\n   Output: {mr_result}\n")
        
    except Exception as translation_error:
        print(f"⚠️ Diagnostic failure: {translation_error}")

if __name__ == "__main__":
    try:
        import argostranslate
    except ImportError:
        print("❌ 'argostranslate' core module is missing.")
        print("💡 Run: pip install argostranslate")
        sys.exit(1)

    setup_native_translation_models()
