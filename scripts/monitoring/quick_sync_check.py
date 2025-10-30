#!/usr/bin/env python3
"""
Quick sync check at specific time points.
"""

import sys
import os
import subprocess
import tempfile
from pathlib import Path

# Add project root to Python path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root))

from sync_analyzer.core.audio_sync_detector import ProfessionalSyncDetector

def check_sync_at_time(master_path, dub_path, time_point, duration=10):
    """Check sync at a specific time point."""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        master_segment = os.path.join(temp_dir, 'master.wav')
        dub_segment = os.path.join(temp_dir, 'dub.wav')
        
        # Extract segments
        for file_path, output in [(master_path, master_segment), (dub_path, dub_segment)]:
            cmd = [
                'ffmpeg', '-y', '-i', file_path,
                '-ss', str(time_point),
                '-t', str(duration),
                '-vn', '-acodec', 'pcm_s16le',
                '-ar', '22050',
                output
            ]
            subprocess.run(cmd, check=True, capture_output=True)
        
        # Analyze sync
        detector = ProfessionalSyncDetector()
        results = detector.analyze_sync(Path(master_segment), Path(dub_segment))
        consensus_result = detector.get_consensus_result(results)

        print(f"Time {time_point}s: Offset = {consensus_result.offset_seconds:.3f}s, Confidence = {consensus_result.confidence:.3f}")
        return consensus_result.offset_seconds

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python quick_sync_check.py <master_file> <dub_file> [time1] [time2] ...")
        print("Example: python quick_sync_check.py master.mov dub.mov 0 60 120 300")
        sys.exit(1)
    
    master_file = sys.argv[1]
    dub_file = sys.argv[2]
    
    # Default time points if none specified
    time_points = [0, 60, 120, 300, 600] if len(sys.argv) == 3 else [int(t) for t in sys.argv[3:]]
    
    print(f"Checking sync at time points: {time_points}")
    print("-" * 50)
    
    offsets = []
    for time_point in time_points:
        try:
            offset = check_sync_at_time(master_file, dub_file, time_point)
            offsets.append(offset)
        except Exception as e:
            print(f"Time {time_point}s: Error - {e}")
    
    if len(offsets) > 1:
        drift = max(offsets) - min(offsets)
        print(f"\nSync drift: {drift:.3f}s (from {min(offsets):.3f}s to {max(offsets):.3f}s)")