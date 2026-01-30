#!/usr/bin/env python3
"""
Package test results for sharing.
Creates a folder with all necessary files that can be zipped and shared.

Usage: python3 package_for_sharing.py
"""

import shutil
from pathlib import Path
from datetime import datetime

# ============================================================
# CONFIGURATION
# ============================================================
OUTPUT_FOLDER = "repos"  # Must match update_manifest.py
PACKAGE_NAME = "evoq_test_results"  # Output folder name
# ============================================================

def package():
    # Create timestamped package folder
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    package_dir = Path(f"{PACKAGE_NAME}_{timestamp}")
    
    # Check required files exist
    manifest = Path("manifest.js")
    navigator = Path("navigator.html")
    discard_status = Path("discard_status.js")
    results_dir = Path(OUTPUT_FOLDER)
    
    missing = []
    if not manifest.exists():
        missing.append("manifest.js (run: python3 update_manifest.py)")
    if not navigator.exists():
        missing.append("navigator.html")
    if not results_dir.exists():
        missing.append(f"{OUTPUT_FOLDER}/ folder")
    
    if missing:
        print("❌ Missing required files:")
        for m in missing:
            print(f"   - {m}")
        return
    
    print(f"📦 Creating package: {package_dir}/")
    
    # Create package directory
    package_dir.mkdir(exist_ok=True)
    
    # Copy navigator as index.html for easy opening
    shutil.copy(navigator, package_dir / "index.html")
    print(f"   ✓ Copied navigator.html → index.html")
    
    # Copy manifest.js
    shutil.copy(manifest, package_dir / "manifest.js")
    print(f"   ✓ Copied manifest.js")
    
    # Copy discard_status.js (create empty one if it doesn't exist)
    if discard_status.exists():
        shutil.copy(discard_status, package_dir / "discard_status.js")
        print(f"   ✓ Copied discard_status.js")
    else:
        # Create empty discard status file
        with open(package_dir / "discard_status.js", 'w') as f:
            f.write('// Discard status - no discarded scenarios\n')
            f.write('window.DISCARD_STATUS = {};\n')
        print(f"   ✓ Created empty discard_status.js")
    
    # Copy results folder
    dest_results = package_dir / OUTPUT_FOLDER
    shutil.copytree(results_dir, dest_results)
    
    # Count files copied
    file_count = sum(1 for _ in dest_results.rglob("*") if _.is_file())
    folder_count = sum(1 for _ in dest_results.rglob("*") if _.is_dir())
    print(f"   ✓ Copied {OUTPUT_FOLDER}/ ({file_count} files in {folder_count} folders)")
    
    # Calculate total size
    total_size = sum(f.stat().st_size for f in package_dir.rglob("*") if f.is_file())
    size_mb = total_size / (1024 * 1024)
    
    print()
    print(f"✅ Package ready: {package_dir}/")
    print(f"   📊 Total size: {size_mb:.1f} MB")
    print()
    print("To share:")
    print(f"   zip -r {package_dir}.zip {package_dir}/")
    print()
    print("Recipients can open index.html in any browser to view results.")


if __name__ == '__main__':
    package()

