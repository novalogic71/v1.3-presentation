#!/usr/bin/env python3
"""
Check for sync drift throughout a file by analyzing multiple segments.
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

def extract_audio_segment(video_path, start_time, duration, output_path):
    """Extract audio segment using FFmpeg."""
    cmd = [
        'ffmpeg', '-y', '-i', video_path,
        '-ss', str(start_time),
        '-t', str(duration),
        '-vn', '-acodec', 'pcm_s16le',
        '-ar', '22050',
        output_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)

def check_sync_drift(master_path, dub_path, segment_duration=30, step_interval=60):
    """Check sync at multiple points throughout the files."""
    
    # Get duration of master file
    cmd = ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', 
           '-of', 'default=noprint_wrappers=1:nokey=1', master_path]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    total_duration = float(result.stdout.strip())
    
    print(f"Total duration: {total_duration:.1f} seconds")
    print(f"Analyzing {segment_duration}s segments every {step_interval}s")
    print("-" * 60)
    
    detector = ProfessionalSyncDetector()
    results = []
    
    with tempfile.TemporaryDirectory() as temp_dir:
        start_time = 0
        segment_num = 1
        
        while start_time < total_duration - segment_duration:
            print(f"Segment {segment_num}: {start_time}s - {start_time + segment_duration}s")
            
            # Extract segments
            master_segment = os.path.join(temp_dir, f'master_{segment_num}.wav')
            dub_segment = os.path.join(temp_dir, f'dub_{segment_num}.wav')
            
            try:
                extract_audio_segment(master_path, start_time, segment_duration, master_segment)
                extract_audio_segment(dub_path, start_time, segment_duration, dub_segment)
                
                # Analyze sync
                sync_result = detector.analyze_sync(master_segment, dub_segment)
                offset = sync_result.offset_seconds
                confidence = sync_result.confidence
                
                print(f"  Offset: {offset:.3f}s (confidence: {confidence:.3f})")
                
                results.append({
                    'segment': segment_num,
                    'start_time': start_time,
                    'offset_seconds': offset,
                    'confidence': confidence
                })
                
            except Exception as e:
                print(f"  Error analyzing segment: {e}")
                
            start_time += step_interval
            segment_num += 1
    
    # Summary
    print("\n" + "=" * 60)
    print("SYNC DRIFT ANALYSIS SUMMARY")
    print("=" * 60)
    
    if results:
        offsets = [r['offset_seconds'] for r in results]
        min_offset = min(offsets)
        max_offset = max(offsets)
        drift = max_offset - min_offset
        
        print(f"Min offset: {min_offset:.3f}s")
        print(f"Max offset: {max_offset:.3f}s")
        print(f"Total drift: {drift:.3f}s")
        
        if drift > 0.1:  # More than 100ms drift
            print(f"\n⚠️  SYNC DRIFT DETECTED: {drift:.3f}s drift across file")
            print("Segments with significant drift:")
            for r in results:
                if abs(r['offset_seconds'] - offsets[0]) > 0.05:
                    print(f"  Segment {r['segment']} ({r['start_time']}s): {r['offset_seconds']:.3f}s")
        else:
            print(f"\n✅ No significant sync drift detected")
    
    return results

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python check_sync_drift.py <master_file> <dub_file>")
        sys.exit(1)
    
    master_file = sys.argv[1]
    dub_file = sys.argv[2]
    
    if not os.path.exists(master_file) or not os.path.exists(dub_file):
        print("Error: One or both files do not exist")
        sys.exit(1)
    
    results = check_sync_drift(master_file, dub_file)