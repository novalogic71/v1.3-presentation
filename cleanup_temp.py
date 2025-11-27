#!/usr/bin/env python3
"""
Temp File Cleanup Utility
=========================

Cleans up orphaned temp files from the sync analyzer pipeline.
Run this periodically or add to startup scripts.

Usage:
    python cleanup_temp.py           # Standard cleanup
    python cleanup_temp.py --all     # Aggressive cleanup (all temp files)
    python cleanup_temp.py --stats   # Show stats only
"""

import argparse
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path


def get_size_str(size_bytes: int) -> str:
    """Convert bytes to human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def get_dir_size(path: Path) -> int:
    """Get total size of a directory."""
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    except Exception:
        pass
    return total


def cleanup_pattern(base_dir: Path, pattern: str, max_age_hours: int = 24) -> tuple:
    """Clean up files/dirs matching a pattern older than max_age_hours."""
    removed = 0
    freed = 0
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    
    for item in base_dir.glob(pattern):
        try:
            mtime = datetime.fromtimestamp(item.stat().st_mtime)
            if mtime < cutoff:
                size = item.stat().st_size if item.is_file() else get_dir_size(item)
                if item.is_file():
                    item.unlink()
                else:
                    shutil.rmtree(item)
                removed += 1
                freed += size
        except Exception as e:
            print(f"  Warning: Could not remove {item}: {e}")
    
    return removed, freed


def main():
    parser = argparse.ArgumentParser(description="Sync Analyzer Temp File Cleanup")
    parser.add_argument("--all", action="store_true", help="Remove ALL temp files (not just old ones)")
    parser.add_argument("--stats", action="store_true", help="Show stats only, don't remove anything")
    parser.add_argument("--max-age", type=int, default=24, help="Max age in hours (default: 24)")
    args = parser.parse_args()
    
    # Patterns to clean up
    patterns = {
        "/tmp": [
            "iab_*",
            "atmos_*",
            "adm_*",
            "proxy_*",
            "sync_*",
            "iab_to_adm_*",
            "iab_convert_*",
        ],
        "/mnt/data/amcmurray/Sync_dub/v1.3-presentation/temp_jobs": [
            "*"
        ]
    }
    
    max_age = 0 if args.all else args.max_age
    
    print("=" * 60)
    print("Sync Analyzer Temp File Cleanup")
    print("=" * 60)
    print(f"Max age: {max_age} hours {'(removing ALL)' if args.all else ''}")
    print(f"Mode: {'Stats only' if args.stats else 'Cleanup'}")
    print()
    
    total_removed = 0
    total_freed = 0
    
    for base_path, pattern_list in patterns.items():
        base_dir = Path(base_path)
        if not base_dir.exists():
            continue
        
        print(f"Scanning {base_path}...")
        
        for pattern in pattern_list:
            # Count matching items
            matches = list(base_dir.glob(pattern))
            if not matches:
                continue
            
            # Calculate size
            pattern_size = sum(
                f.stat().st_size if f.is_file() else get_dir_size(f)
                for f in matches
            )
            
            print(f"  {pattern}: {len(matches)} items, {get_size_str(pattern_size)}")
            
            if not args.stats:
                removed, freed = cleanup_pattern(base_dir, pattern, max_age)
                if removed > 0:
                    print(f"    → Removed {removed} items, freed {get_size_str(freed)}")
                    total_removed += removed
                    total_freed += freed
    
    print()
    print("=" * 60)
    
    if args.stats:
        print("Stats complete. Run without --stats to cleanup.")
    else:
        print(f"Cleanup complete!")
        print(f"  Removed: {total_removed} items")
        print(f"  Freed: {get_size_str(total_freed)}")
    
    # Show current disk usage
    print()
    print("Current disk usage:")
    for mount in ["/", "/tmp", "/mnt/data"]:
        try:
            total, used, free = shutil.disk_usage(mount)
            pct = (used / total) * 100
            print(f"  {mount}: {get_size_str(free)} free ({pct:.0f}% used)")
        except Exception:
            pass
    
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())

