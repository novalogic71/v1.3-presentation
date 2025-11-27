#!/usr/bin/env python3
"""Test script to check offset precision and display exact values."""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from sync_analyzer.core.audio_sync_detector import ProfessionalSyncDetector

def test_offset_precision(master_path, dub_path):
    """Test offset calculation and display all precision values."""

    print("="*80)
    print("OFFSET PRECISION TEST")
    print("="*80)
    print(f"Master: {master_path}")
    print(f"Dub:    {dub_path}")
    print()

    # Initialize detector
    detector = ProfessionalSyncDetector(
        sample_rate=22050,
        window_size_seconds=30.0,
        confidence_threshold=0.3,
        use_gpu=False
    )

    # Run analysis with all methods
    results = detector.analyze_sync(
        Path(master_path),
        Path(dub_path),
        methods=['mfcc', 'onset', 'spectral', 'correlation']
    )

    # Display results for each method
    print("INDIVIDUAL METHOD RESULTS:")
    print("-"*80)
    for method_name, result in results.items():
        print(f"\n{method_name.upper()}:")
        print(f"  offset_samples:      {result.offset_samples}")
        print(f"  offset_seconds:      {result.offset_seconds:.10f}")
        print(f"  offset_milliseconds: {result.offset_seconds * 1000:.10f}")
        print(f"  confidence:          {result.confidence:.4f}")

        # Calculate frame offsets
        fps_values = [23.976, 24.0, 29.97, 30.0]
        print(f"  Frame offsets:")
        for fps in fps_values:
            frames = result.offset_seconds * fps
            frames_rounded = round(abs(frames))
            print(f"    @ {fps:6.3f} fps: {frames:10.6f} frames (rounded: {frames_rounded}f)")

    # Get consensus
    consensus = detector.get_consensus_result(results)

    print("\n" + "="*80)
    print("CONSENSUS RESULT:")
    print("-"*80)
    print(f"  method_used:         {consensus.method_used}")
    print(f"  offset_samples:      {consensus.offset_samples}")
    print(f"  offset_seconds:      {consensus.offset_seconds:.10f}")
    print(f"  offset_milliseconds: {consensus.offset_seconds * 1000:.10f}")
    print(f"  confidence:          {consensus.confidence:.4f}")

    # Show what would be sent to frontend
    print("\n" + "="*80)
    print("VALUES SENT TO FRONTEND:")
    print("-"*80)
    print(f"  offset_seconds:      {consensus.offset_seconds}")
    print(f"  offset_milliseconds: {consensus.offset_seconds * 1000}")

    # Show what frontend would calculate
    print("\n" + "="*80)
    print("FRONTEND CALCULATIONS (OLD WAY - recalculating from seconds):")
    print("-"*80)
    offset_ms_recalc = consensus.offset_seconds * 1000
    print(f"  offsetMs = offset_seconds * 1000 = {offset_ms_recalc}")
    print(f"  Displayed: {abs(offset_ms_recalc):.1f}ms")

    print("\n" + "="*80)
    print("FRONTEND CALCULATIONS (NEW WAY - using pre-calculated):")
    print("-"*80)
    offset_ms_direct = consensus.offset_seconds * 1000
    print(f"  offsetMs = offset_milliseconds = {offset_ms_direct}")
    print(f"  Displayed: {abs(offset_ms_direct):.1f}ms")

    print("\n" + "="*80)


if __name__ == "__main__":
    master = "/mnt/data/amcmurray/_insync_master_files/DunkirkEC_InsideTheCockpit_ProRes.mov"
    dub = "/mnt/data/amcmurray/_outofsync_master_files/DunkirkEC_InsideTheCockpit_ProRes_15sec.mov"

    test_offset_precision(master, dub)
