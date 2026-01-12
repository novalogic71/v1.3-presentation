#!/usr/bin/env python3
"""
Test script to identify which files in the batch have false peaks

Checks all ORIGINALS series files and other files to find which ones
have suspiciously large offsets (>30s) that might be false peaks.
"""

import sys
import csv
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import logging
logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

CSV_FILE = "/mnt/data/amcmurray/Sync_dub/v1.3-presentation/wb_dubsync_batch_standard.csv"

def parse_csv():
    """Parse the CSV file and extract file pairs"""
    pairs = []
    with open(CSV_FILE, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            master = row['master_file'].strip()
            components_str = row['component_files'].strip()
            components = [c.strip() for c in components_str.split(';') if c.strip()]
            pairs.append({
                'master': master,
                'components': components
            })
    return pairs

def test_file_pair(master, components, max_duration=300):
    """Test a single file pair and return offset"""
    if not os.path.exists(master):
        return None, "Master file not found"
    
    missing = [c for c in components if not os.path.exists(c)]
    if missing:
        return None, f"Missing {len(missing)} component files"
    
    try:
        from sync_analyzer.analysis import analyze
        from pathlib import Path
        
        # Test with first component only for speed
        consensus, sync_results, _ = analyze(
            Path(master),
            Path(components[0]),
            methods=['mfcc']  # Just MFCC for speed
        )
        
        return consensus.offset_seconds, None
        
    except Exception as e:
        return None, str(e)

def main():
    """Test all files in batch"""
    print("="*80)
    print("Testing Batch Files for False Peaks")
    print("="*80)
    
    pairs = parse_csv()
    print(f"\nFound {len(pairs)} file pairs in CSV\n")
    
    # Focus on ORIGINALS series first
    originals_pairs = [p for p in pairs if 'ORIGINALS_THE_YR05' in p['master']]
    other_pairs = [p for p in pairs if 'ORIGINALS_THE_YR05' not in p['master']]
    
    print(f"ORIGINALS series: {len(originals_pairs)} files")
    print(f"Other files: {len(other_pairs)} files\n")
    
    suspicious_files = []
    good_files = []
    error_files = []
    
    # Test ORIGINALS series first
    print("Testing ORIGINALS series files...")
    print("-" * 80)
    
    for i, pair in enumerate(originals_pairs, 1):
        master_name = Path(pair['master']).name
        print(f"[{i}/{len(originals_pairs)}] {master_name[:60]}...", end=" ", flush=True)
        
        offset, error = test_file_pair(pair['master'], pair['components'])
        
        if error:
            print(f"ERROR: {error}")
            error_files.append((master_name, error))
        elif offset is not None:
            abs_offset = abs(offset)
            if abs_offset > 30:
                print(f"⚠️  SUSPICIOUS: {offset:.3f}s")
                suspicious_files.append((master_name, offset, "ORIGINALS"))
            elif abs_offset > 10:
                print(f"⚠️  LARGE: {offset:.3f}s")
                suspicious_files.append((master_name, offset, "ORIGINALS"))
            else:
                print(f"✓ {offset:.3f}s")
                good_files.append((master_name, offset))
    
    # Test a sample of other files
    print(f"\n\nTesting sample of other files (first 5)...")
    print("-" * 80)
    
    for i, pair in enumerate(other_pairs[:5], 1):
        master_name = Path(pair['master']).name
        print(f"[{i}/5] {master_name[:60]}...", end=" ", flush=True)
        
        offset, error = test_file_pair(pair['master'], pair['components'])
        
        if error:
            print(f"ERROR: {error}")
            error_files.append((master_name, error))
        elif offset is not None:
            abs_offset = abs(offset)
            if abs_offset > 30:
                print(f"⚠️  SUSPICIOUS: {offset:.3f}s")
                suspicious_files.append((master_name, offset, "OTHER"))
            elif abs_offset > 10:
                print(f"⚠️  LARGE: {offset:.3f}s")
                suspicious_files.append((master_name, offset, "OTHER"))
            else:
                print(f"✓ {offset:.3f}s")
                good_files.append((master_name, offset))
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    print(f"\n✓ Good offsets (<10s): {len(good_files)}")
    print(f"⚠️  Large offsets (10-30s): {len([f for f in suspicious_files if abs(f[1]) <= 30])}")
    print(f"❌ Suspicious offsets (>30s): {len([f for f in suspicious_files if abs(f[1]) > 30])}")
    print(f"✗ Errors: {len(error_files)}")
    
    if suspicious_files:
        print(f"\n\nFILES WITH SUSPICIOUS OFFSETS (>30s):")
        print("-" * 80)
        for name, offset, series in sorted(suspicious_files, key=lambda x: abs(x[1]), reverse=True):
            if abs(offset) > 30:
                print(f"  {name[:70]}")
                print(f"    Offset: {offset:.3f}s ({series} series)")
                print()
    
    if error_files:
        print(f"\n\nFILES WITH ERRORS:")
        print("-" * 80)
        for name, error in error_files[:10]:  # Show first 10
            print(f"  {name[:70]}")
            print(f"    Error: {error[:100]}")
            print()

if __name__ == "__main__":
    main()
