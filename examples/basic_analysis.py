#!/usr/bin/env python3
"""
Basic Analysis Example

This script demonstrates how to use the Professional Audio Sync Analyzer
for basic sync detection between master and dub audio tracks.
"""

import sys
import os
from pathlib import Path

# Add the parent directory to the path so we can import sync_analyzer
sys.path.insert(0, str(Path(__file__).parent.parent))

from sync_analyzer.core.audio_sync_detector import ProfessionalSyncDetector


def analyze_sync(master_file, dub_file):
    """
    Perform basic sync analysis between master and dub files.
    
    Args:
        master_file (str): Path to the master audio/video file
        dub_file (str): Path to the dub audio/video file
    
    Returns:
        dict: Analysis results with offset information
    """
    
    print(f"🎵 Analyzing sync between:")
    print(f"   Master: {master_file}")
    print(f"   Dub:    {dub_file}")
    print()
    
    # Initialize the sync detector
    detector = ProfessionalSyncDetector(
        sample_rate=22050,
        analysis_window_seconds=30.0,
        n_mfcc=13
    )
    
    try:
        # Perform the analysis
        results = detector.detect_sync(master_file, dub_file, methods=['mfcc'])
        
        if results:
            offset_seconds = results.get('offset_seconds', 0)
            confidence = results.get('confidence', 0)
            
            print(f"✅ Analysis Complete!")
            print(f"   Sync Offset: {offset_seconds:.3f} seconds")
            print(f"   Confidence: {confidence:.1%}")
            
            if abs(offset_seconds) < 0.040:  # Less than 40ms
                print(f"   Status: ✅ EXCELLENT SYNC (< 40ms)")
            elif abs(offset_seconds) < 0.100:  # Less than 100ms
                print(f"   Status: ⚠️  MINOR SYNC ISSUE (< 100ms)")
            else:
                print(f"   Status: ❌ SYNC CORRECTION NEEDED (> 100ms)")
                
            # Frame calculations for common frame rates
            frame_rates = [23.976, 24, 25, 29.97, 30]
            print(f"\n📊 Frame Offset Equivalents:")
            for fps in frame_rates:
                frame_offset = offset_seconds * fps
                print(f"   {fps:6.3f} fps: {frame_offset:+7.2f} frames")
                
            return results
            
        else:
            print("❌ Analysis failed - no results returned")
            return None
            
    except Exception as e:
        print(f"❌ Analysis failed with error: {e}")
        return None


def main():
    """Main function to run the basic analysis example."""
    
    if len(sys.argv) != 3:
        print("Usage: python basic_analysis.py <master_file> <dub_file>")
        print()
        print("Example:")
        print("  python basic_analysis.py master_video.mov dub_video.mov")
        sys.exit(1)
    
    master_file = sys.argv[1]
    dub_file = sys.argv[2]
    
    # Check if files exist
    if not os.path.exists(master_file):
        print(f"❌ Master file not found: {master_file}")
        sys.exit(1)
        
    if not os.path.exists(dub_file):
        print(f"❌ Dub file not found: {dub_file}")
        sys.exit(1)
    
    # Perform the analysis
    results = analyze_sync(master_file, dub_file)
    
    if results:
        print(f"\n💡 Next Steps:")
        print(f"   • Use the web UI for visual analysis and repair")
        print(f"   • Run: cd web_ui && python server.py")
        print(f"   • Open: http://localhost:3001")
    else:
        print(f"\n💡 Troubleshooting:")
        print(f"   • Check that files contain audio tracks")
        print(f"   • Verify files are not corrupted")
        print(f"   • Try different analysis methods")


if __name__ == "__main__":
    main()
