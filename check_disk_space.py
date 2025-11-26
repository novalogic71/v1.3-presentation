#!/usr/bin/env python3
"""Check disk space and clean up temporary files"""
import shutil
import os
import subprocess

def get_disk_usage(path="/tmp"):
    """Get disk usage statistics"""
    stat = shutil.disk_usage(path)
    total_gb = stat.total / (1024**3)
    used_gb = stat.used / (1024**3)
    free_gb = stat.free / (1024**3)
    percent = (stat.used / stat.total) * 100
    
    print(f"\n📊 Disk Usage for {path}:")
    print(f"   Total: {total_gb:.2f} GB")
    print(f"   Used:  {used_gb:.2f} GB ({percent:.1f}%)")
    print(f"   Free:  {free_gb:.2f} GB")
    return free_gb

def clean_tmp():
    """Clean up large temporary directories"""
    dirs_to_check = [
        "/tmp/ebu-adm-toolbox",
        "/tmp/dlb_mp4base",
        "/tmp/atmos_*",
        "/tmp/test_*"
    ]
    
    print("\n🧹 Cleaning up temporary files...")
    for pattern in dirs_to_check:
        try:
            subprocess.run(f"rm -rf {pattern}", shell=True, check=False)
            print(f"   Cleaned: {pattern}")
        except Exception as e:
            print(f"   Failed to clean {pattern}: {e}")

if __name__ == "__main__":
    # Check /tmp
    tmp_free = get_disk_usage("/tmp")
    
    # Check workspace
    workspace_free = get_disk_usage("/mnt/data/amcmurray/Sync_dub/v1.3-presentation")
    
    # Clean up
    clean_tmp()
    
    # Check again
    print("\n📊 After cleanup:")
    get_disk_usage("/tmp")
    
    print("\n✅ Ready to build EBU ADM Toolbox!")
    print(f"   Recommended build location: /mnt/data/amcmurray/Sync_dub/v1.3-presentation/external/")

