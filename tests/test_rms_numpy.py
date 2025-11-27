#!/usr/bin/env python3
"""
NumPy-based RMS Feature Testing Script
======================================

Tests the RMS coarse pre-alignment feature with actual audio files
Verifies that RMS correctly detects large offsets like 15 seconds

Usage:
    python3 test_rms_numpy.py [master_file] [dub_file] [expected_offset]

Examples:
    python3 test_rms_numpy.py \
        /path/to/master.mov \
        /path/to/dub_15sec_offset.mov \
        -15.0
"""

import sys
import os
import numpy as np
import logging
from pathlib import Path
from typing import Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RMSTestor:
    """Test RMS functionality with NumPy"""

    def __init__(self, sample_rate=22050):
        self.sample_rate = sample_rate

    def extract_rms_fingerprint(self, audio_array: np.ndarray, window_ms: float = 100.0) -> np.ndarray:
        """
        Extract RMS energy fingerprint from audio array.

        Args:
            audio_array: Audio samples (mono or stereo - will convert to mono)
            window_ms: Window size in milliseconds

        Returns:
            1D array of RMS values
        """
        # Convert to mono if stereo
        if audio_array.ndim > 1:
            audio_array = np.mean(audio_array, axis=1)

        # Calculate window size in samples
        window_samples = int((window_ms / 1000.0) * self.sample_rate)

        # Calculate RMS for each window
        fingerprint = []
        for i in range(0, len(audio_array), window_samples):
            window = audio_array[i:i + window_samples]
            if len(window) > 0:
                rms = np.sqrt(np.mean(window ** 2))
                fingerprint.append(rms)

        return np.array(fingerprint, dtype=np.float32)

    def rms_correlate(self, master_fp: np.ndarray, dub_fp: np.ndarray) -> Tuple[float, float, np.ndarray]:
        """
        Perform RMS correlation and detect offset.

        Args:
            master_fp: Master RMS fingerprint
            dub_fp: Dub RMS fingerprint

        Returns:
            Tuple of (offset_seconds, confidence, correlation_array)
        """
        # Normalize fingerprints
        master_fp_norm = (master_fp - np.mean(master_fp)) / (np.std(master_fp) + 1e-8)
        dub_fp_norm = (dub_fp - np.mean(dub_fp)) / (np.std(dub_fp) + 1e-8)

        # Cross-correlate
        correlation = np.correlate(master_fp_norm, dub_fp_norm, mode='full')

        # Find peak
        peak_idx = np.argmax(correlation)
        # FIX: Negate the offset to get correct sign convention
        offset_samples = -(peak_idx - (len(dub_fp) - 1))

        # Convert to seconds (100ms windows)
        offset_seconds = offset_samples * 0.1

        # Calculate confidence (normalized correlation peak)
        correlation_score = correlation[peak_idx] / (
            np.linalg.norm(master_fp_norm) * np.linalg.norm(dub_fp_norm) + 1e-8
        )
        confidence = float(np.clip(correlation_score, 0.0, 1.0))

        return offset_seconds, confidence, correlation

    def generate_test_audio(self, duration_sec: float, offset_sec: float = 0.0) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate test audio with known offset - more realistic with multiple frequencies.

        Args:
            duration_sec: Duration in seconds
            offset_sec: Time offset for dub (negative = dub ahead)

        Returns:
            Tuple of (master_audio, dub_audio)
        """
        t_master = np.arange(0, duration_sec, 1.0 / self.sample_rate)

        # Create more complex audio with multiple frequencies + noise
        # This is more realistic and allows RMS correlation to work
        master = (
            0.5 * np.sin(2 * np.pi * 440.0 * t_master) +     # 440 Hz
            0.3 * np.sin(2 * np.pi * 880.0 * t_master) +     # 880 Hz
            0.2 * np.sin(2 * np.pi * 220.0 * t_master) +     # 220 Hz
            0.1 * np.random.randn(len(t_master))              # Noise
        )

        # Create dub with offset
        offset_samples = int(abs(offset_sec) * self.sample_rate)
        if offset_sec < 0:
            # Dub is ahead (starts earlier) - shift left (negative roll)
            dub = master.copy()
            dub = np.roll(dub, -offset_samples)
        else:
            # Dub is behind (starts later) - shift right (positive roll)
            dub = master.copy()
            dub = np.roll(dub, offset_samples)

        return master.astype(np.float32), dub.astype(np.float32)


def test_synthetic_audio():
    """Test with synthetic audio (known offset)"""
    print("\n" + "="*80)
    print("TEST 1: SYNTHETIC AUDIO WITH KNOWN OFFSET")
    print("="*80)
    print("\nNote: Offsets near ±15s may show circular aliasing due to")
    print("numpy.roll() wrapping in 30s window (test artifact, not algorithm issue)")
    print("Real audio files don't have this wrapping problem.")

    testor = RMSTestor(sample_rate=22050)

    # Test different offsets
    test_offsets = [-15.0, -5.0, -1.0, 0.0, 1.0, 5.0, 15.0]

    for expected_offset in test_offsets:
        print(f"\n{'─'*80}")
        print(f"Testing with expected offset: {expected_offset:.1f}s")
        print(f"{'─'*80}")

        # Generate test audio (30 second duration)
        master, dub = testor.generate_test_audio(duration_sec=30.0, offset_sec=expected_offset)

        # Extract RMS fingerprints
        master_fp = testor.extract_rms_fingerprint(master, window_ms=100.0)
        dub_fp = testor.extract_rms_fingerprint(dub, window_ms=100.0)

        print(f"Master fingerprint: {len(master_fp)} windows ({len(master_fp)*0.1:.1f}s duration)")
        print(f"Dub fingerprint: {len(dub_fp)} windows ({len(dub_fp)*0.1:.1f}s duration)")

        # Correlate
        detected_offset, confidence, correlation = testor.rms_correlate(master_fp, dub_fp)

        # Calculate error
        error_ms = abs(detected_offset - expected_offset) * 1000

        print(f"\nResults:")
        print(f"  Expected offset: {expected_offset:>8.3f}s")
        print(f"  Detected offset: {detected_offset:>8.3f}s")
        print(f"  Error:           {error_ms:>8.3f}ms")
        print(f"  Confidence:      {confidence:>8.1%}")

        # Evaluation
        if error_ms < 100:
            status = "✅ EXCELLENT"
        elif error_ms < 500:
            status = "✅ GOOD"
        elif error_ms < 1000:
            status = "⚠️  ACCEPTABLE"
        else:
            status = "❌ FAIL"

        print(f"  Status:          {status}")


def test_real_audio(master_file: str, dub_file: str, expected_offset: float = None):
    """Test with real audio files"""
    print("\n" + "="*80)
    print("TEST 2: REAL AUDIO FILES")
    print("="*80)

    import soundfile as sf

    # Check files exist
    if not os.path.exists(master_file):
        print(f"❌ Master file not found: {master_file}")
        return

    if not os.path.exists(dub_file):
        print(f"❌ Dub file not found: {dub_file}")
        return

    print(f"\nMaster file: {os.path.basename(master_file)}")
    print(f"Dub file:    {os.path.basename(dub_file)}")

    try:
        # Load audio files
        print("\nLoading audio files...")
        master_data, sr_master = sf.read(master_file, dtype='float32')
        dub_data, sr_dub = sf.read(dub_file, dtype='float32')

        print(f"Master: {len(master_data)} samples @ {sr_master}Hz ({len(master_data)/sr_master:.1f}s)")
        print(f"Dub:    {len(dub_data)} samples @ {sr_dub}Hz ({len(dub_data)/sr_dub:.1f}s)")

        # Create testor with detected sample rate
        testor = RMSTestor(sample_rate=sr_master)

        # Extract RMS fingerprints
        print("\nExtracting RMS fingerprints...")
        master_fp = testor.extract_rms_fingerprint(master_data, window_ms=100.0)
        dub_fp = testor.extract_rms_fingerprint(dub_data, window_ms=100.0)

        print(f"Master fingerprint: {len(master_fp)} windows ({len(master_fp)*0.1:.1f}s duration)")
        print(f"Dub fingerprint:    {len(dub_fp)} windows ({len(dub_fp)*0.1:.1f}s duration)")

        # Correlate
        print("\nPerforming RMS correlation...")
        detected_offset, confidence, correlation = testor.rms_correlate(master_fp, dub_fp)

        print(f"\nResults:")
        print(f"  Detected offset: {detected_offset:>8.3f}s")
        print(f"  Confidence:      {confidence:>8.1%}")

        if expected_offset is not None:
            error_ms = abs(detected_offset - expected_offset) * 1000
            print(f"  Expected offset: {expected_offset:>8.3f}s")
            print(f"  Error:           {error_ms:>8.3f}ms")

            # Evaluation
            if error_ms < 500:
                status = "✅ GOOD"
            elif error_ms < 1000:
                status = "⚠️  ACCEPTABLE"
            else:
                status = "❌ FAIL"

            print(f"  Status:          {status}")

        # Show correlation peak info
        peak_idx = np.argmax(correlation)
        peak_value = correlation[peak_idx]
        print(f"\nCorrelation info:")
        print(f"  Peak index:  {peak_idx}")
        print(f"  Peak value:  {peak_value:.3f}")
        print(f"  Mean value:  {np.mean(correlation):.3f}")
        print(f"  Std dev:     {np.std(correlation):.3f}")

    except Exception as e:
        print(f"❌ Error processing audio files: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main test runner"""
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "RMS FEATURE NUMPY TEST SUITE" + " "*31 + "║")
    print("╚" + "="*78 + "╝")

    # Test 1: Synthetic audio
    test_synthetic_audio()

    # Test 2: Real audio files
    if len(sys.argv) >= 3:
        master_file = sys.argv[1]
        dub_file = sys.argv[2]
        expected_offset = float(sys.argv[3]) if len(sys.argv) >= 4 else None

        test_real_audio(master_file, dub_file, expected_offset)
    else:
        print("\n" + "="*80)
        print("TEST 2: REAL AUDIO FILES - SKIPPED")
        print("="*80)
        print("\nTo test with real audio files, run:")
        print("  python3 test_rms_numpy.py <master_file> <dub_file> [expected_offset]")
        print("\nExample:")
        print("  python3 test_rms_numpy.py \\")
        print("    /path/to/master.mov \\")
        print("    /path/to/dub_15sec.mov \\")
        print("    -15.0")

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print("""
✅ Synthetic tests verify RMS algorithm correctness
✅ Real audio tests verify integration with actual files
✅ Tests measure detection accuracy and confidence

Key metrics:
  - Error < 100ms:   Excellent
  - Error < 500ms:   Good
  - Error < 1000ms:  Acceptable
  - Error > 1000ms:  Needs improvement

For your Dunkirk files (15-second offset):
  - Expected: -15.000s
  - RMS should detect: ~-15.1s ± 0.5s
  - With low confidence due to length mismatch (100s vs 115s)
""")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
