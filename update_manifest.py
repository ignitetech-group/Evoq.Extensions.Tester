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
    total_features = 0
    total_scenarios = 0
    total_passed = 0
    total_failed = 0
    
    if not OUTPUT_DIR.exists():
        print(f"⚠️  Folder '{OUTPUT_FOLDER}' not found")
        return
    
    for folder in sorted(OUTPUT_DIR.iterdir()):
        if folder.is_dir() and folder.name.endswith('_result'):
            ext_name = folder.name.replace('_result', '')
            features = {}
            ext_screenshots = 0
            ext_passed = 0
            ext_failed = 0
            
            # First pass: collect all screenshots by feature name
            screenshot_map = defaultdict(list)
            for file in sorted(folder.iterdir()):
                if file.suffix == '.png':
                    # Extract feature name from screenshot filename
                    # Format: FeatureName_step01_description.png
                    parts = file.stem.rsplit('_step', 1)
                    if len(parts) == 2:
                        feature_key = parts[0].replace('_', ' ')
                        screenshot_map[feature_key].append(file.name)
                    ext_screenshots += 1
            
            # Second pass: parse JSON files
            for file in sorted(folder.iterdir()):
                if file.suffix == '.json' and file.stem.endswith('_test_result'):
                    try:
                        with open(file, 'r', encoding='utf-8') as f:
                            test_data = json.load(f)
                        
                        feature_name = test_data.get('metadata', {}).get('feature_name', file.stem.replace('_test_result', ''))
                        feature_key = feature_name.replace(' ', '_').replace('_', ' ')  # Normalize for matching
                        
                        # Extract summary
                        summary = test_data.get('summary', {})
                        passed = summary.get('passed', 0)
                        failed = summary.get('failed', 0)
                        
                        # Collect all screenshots from steps
                        screenshots = []
                        for scenario in test_data.get('test_scenarios', []):
                            for step in scenario.get('steps', []):
                                if step.get('screenshot'):
                                    screenshots.append(step['screenshot'])
                        
                        # Also include screenshots from the map if not already captured
                        for key in screenshot_map:
                            if feature_name.lower().replace(' ', '') in key.lower().replace(' ', ''):
                                for ss in screenshot_map[key]:
                                    if ss not in screenshots:
                                        screenshots.append(ss)
                        
                        features[feature_name] = {
                            'json_file': file.name,
                            'screenshots': screenshots,
                            'scenarios': [
                                {
                                    'name': s.get('scenario_name', 'Unknown'),
                                    'status': s.get('status', 'UNKNOWN'),
                                    'issues': s.get('issues', []),
                                    'step_count': len(s.get('steps', []))
                                }
                                for s in test_data.get('test_scenarios', [])
                            ],
                            'observations': test_data.get('observations', []),
                            'summary': summary,
                            'metadata': test_data.get('metadata', {}),
                            # Embed full test data to avoid fetch issues with local files
                            'full_data': test_data
                        }
                        
                        ext_passed += passed
                        ext_failed += failed
                        
                    except (json.JSONDecodeError, KeyError) as e:
                        print(f"⚠️  Failed to parse {file}: {e}")
            
            if features:
                total_screenshots += ext_screenshots
                total_features += len(features)
                total_scenarios += sum(len(f['scenarios']) for f in features.values())
                total_passed += ext_passed
                total_failed += ext_failed
                
                results[ext_name] = {
                    'folder': folder.name,
                    'features': features,
                    'total_screenshots': ext_screenshots,
                    'total_features': len(features),
                    'total_passed': ext_passed,
                    'total_failed': ext_failed,
                    'pass_rate': f"{round(ext_passed / (ext_passed + ext_failed) * 100) if (ext_passed + ext_failed) > 0 else 0}%"
                }
    
    data = {
        'outputFolder': OUTPUT_FOLDER,
        'results': results,
        'stats': {
            'extensions': len(results),
            'features': total_features,
            'scenarios': total_scenarios,
            'screenshots': total_screenshots,
            'passed': total_passed,
            'failed': total_failed,
            'pass_rate': f"{round(total_passed / (total_passed + total_failed) * 100) if (total_passed + total_failed) > 0 else 0}%"
        }
    }
    
    with open(MANIFEST_FILE, 'w') as f:
        f.write('// Auto-generated manifest - run update_manifest.py to refresh\n')
        f.write('window.MANIFEST_DATA = ')
        json.dump(data, f, indent=2)
        f.write(';\n')
    
    print(f"✅ Updated manifest.js")
    print(f"   📦 {len(results)} extensions")
    print(f"   🧪 {total_features} features")
    print(f"   📋 {total_scenarios} test scenarios")
    print(f"   📸 {total_screenshots} screenshots")
    print(f"   ✅ {total_passed} passed / ❌ {total_failed} failed ({data['stats']['pass_rate']})")


if __name__ == '__main__':
    scan()

