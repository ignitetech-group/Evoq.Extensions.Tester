#!/usr/bin/env python3
"""
Quick script to update the manifest.js file.
Run this whenever you add new test results.

Usage: python3 update_manifest.py
"""

import json
from pathlib import Path
from collections import defaultdict

# ============================================================
# CONFIGURATION - Change this to point to your results folder
# ============================================================
OUTPUT_FOLDER = "repos"
# ============================================================

OUTPUT_DIR = Path(OUTPUT_FOLDER)
MANIFEST_FILE = Path("manifest.js")


def scan():
    results = {}
    total_screenshots = 0
    total_reports = 0
    
    if not OUTPUT_DIR.exists():
        print(f"⚠️  Folder '{OUTPUT_FOLDER}' not found")
        return
    
    for folder in sorted(OUTPUT_DIR.iterdir()):
        if folder.is_dir() and folder.name.endswith('_result'):
            ext_name = folder.name.replace('_result', '')
            tests = defaultdict(lambda: {'screenshots': [], 'report': None})
            
            for file in sorted(folder.iterdir()):
                if file.suffix == '.html':
                    test_name = file.stem.replace('_test_report', '').replace('_', ' ')
                    tests[test_name]['report'] = file.name
                elif file.suffix == '.png':
                    parts = file.stem.rsplit('_step', 1)
                    if len(parts) == 2:
                        test_name = parts[0].replace('_', ' ')
                        tests[test_name]['screenshots'].append(file.name)
            
            ext_screenshots = sum(len(t['screenshots']) for t in tests.values())
            ext_reports = sum(1 for t in tests.values() if t['report'])
            total_screenshots += ext_screenshots
            total_reports += ext_reports
            
            results[ext_name] = {
                'folder': folder.name,
                'tests': dict(tests),
                'total_screenshots': ext_screenshots,
                'total_reports': ext_reports
            }
    
    data = {
        'outputFolder': OUTPUT_FOLDER,
        'results': results,
        'stats': {
            'extensions': len(results),
            'reports': total_reports,
            'screenshots': total_screenshots
        }
    }
    
    with open(MANIFEST_FILE, 'w') as f:
        f.write('// Auto-generated manifest - run update_manifest.py to refresh\n')
        f.write('window.MANIFEST_DATA = ')
        json.dump(data, f)
        f.write(';\n')
    
    print(f"✅ Updated manifest.js")
    print(f"   📦 {len(results)} extensions")
    print(f"   📄 {total_reports} reports")
    print(f"   📸 {total_screenshots} screenshots")


if __name__ == '__main__':
    scan()

