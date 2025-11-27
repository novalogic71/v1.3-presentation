#!/usr/bin/env python3
"""Diagnostic test for Wonder Woman offset detection."""

import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from sync_analyzer.core.audio_sync_detector import ProfessionalSyncDetector

def test_wonderwoman_offset(master_path, dub_path):
    """Test offset detection with extended diagnostics."""

    print("="*80)
    print("WONDER WOMAN OFFSET DIAGNOSTIC TEST")
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
    print("Running analysis with all methods...")
    results = detector.analyze_sync(
        Path(master_path),
        Path(dub_path),
        methods=['mfcc', 'onset', 'spectral', 'correlation']
    )

    print("\n" + "="*80)
    print("INDIVIDUAL METHOD RESULTS:")
    print("="*80)

    for method_name, result in results.items():
        print(f"\n{method_name.upper()}:")
        print(f"  offset_samples:      {result.offset_samples}")
        print(f"  offset_seconds:      {result.offset_seconds:.6f}s")
        print(f"  offset_milliseconds: {result.offset_seconds * 1000:.3f}ms")
        print(f"  confidence:          {result.confidence:.4f}")

        # Show if this matches expected offset
        expected_offset = -8.0  # or +8.0, we'll check both
        error_from_minus8 = abs(result.offset_seconds - (-8.0))
        error_from_plus8 = abs(result.offset_seconds - 8.0)

        if error_from_minus8 < 0.5:
            print(f"  ✓ MATCHES expected -8.0s (error: {error_from_minus8:.3f}s)")
        elif error_from_plus8 < 0.5:
            print(f"  ✓ MATCHES expected +8.0s (error: {error_from_plus8:.3f}s)")
        else:
            print(f"  ✗ DOES NOT MATCH expected ±8.0s")
            print(f"    Error from -8.0s: {error_from_minus8:.3f}s")
            print(f"    Error from +8.0s: {error_from_plus8:.3f}s")

    # Get consensus
    consensus = detector.get_consensus_result(results)

    print("\n" + "="*80)
    print("CONSENSUS RESULT:")
    print("="*80)
    print(f"  method_used:         {consensus.method_used}")
    print(f"  offset_samples:      {consensus.offset_samples}")
    print(f"  offset_seconds:      {consensus.offset_seconds:.6f}s")
    print(f"  offset_milliseconds: {consensus.offset_seconds * 1000:.3f}ms")
    print(f"  confidence:          {consensus.confidence:.4f}")

    # Check against expected
    error_from_minus8 = abs(consensus.offset_seconds - (-8.0))
    error_from_plus8 = abs(consensus.offset_seconds - 8.0)

    print()
    if error_from_minus8 < 0.5:
        print(f"  ✓ CONSENSUS CORRECT: -8.0s (error: {error_from_minus8:.3f}s)")
    elif error_from_plus8 < 0.5:
        print(f"  ✓ CONSENSUS CORRECT: +8.0s (error: {error_from_plus8:.3f}s)")
    else:
        print(f"  ✗ CONSENSUS INCORRECT!")
        print(f"    Expected: ±8.0s")
        print(f"    Got: {consensus.offset_seconds:.6f}s")
        print(f"    Error from -8.0s: {error_from_minus8:.3f}s")
        print(f"    Error from +8.0s: {error_from_plus8:.3f}s")

    # Additional diagnostics
    print("\n" + "="*80)
    print("DIAGNOSTIC INFORMATION:")
    print("="*80)
    print(f"  Master duration:     {detector.master_duration:.2f}s")
    print(f"  Dub duration:        {detector.dub_duration:.2f}s")
    print(f"  Duration difference: {detector.master_duration - detector.dub_duration:.2f}s")
    print()
    print("  This could indicate:")
    if abs((detector.master_duration - detector.dub_duration) - 8.0) < 1.0:
        print("  ✓ Files have ~8 second length difference")
        print("  → Dub may be missing 8 seconds of content")
        print("  → OR dub starts 8 seconds into the master")
    else:
        print(f"  - Duration difference ({detector.master_duration - detector.dub_duration:.2f}s) doesn't match expected offset")

    print("\n" + "="*80)


if __name__ == "__main__":
    master = "/mnt/data/amcmurray/_insync_master_files/WonderWoman_Trailer_Dub_Master.mov"
    dub = "/mnt/data/amcmurray/Sync_dub/v1.3-presentation/optimized_sync_reports/wonderwoman_fullmix_stereo.wav"

    test_wonderwoman_offset(master, dub)
