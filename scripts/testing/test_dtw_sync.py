#!/usr/bin/env python3
"""
Quick DTW Sync Detector Test

Tests Dynamic Time Warping for sync detection on a specific file pair.
"""

import sys
import os
import time
import numpy as np
import librosa
from pathlib import Path
from typing import Tuple, List, Optional
import matplotlib.pyplot as plt
import logging

# Add project root to Python path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DTWSyncResult:
    """Results from DTW sync detection."""
    def __init__(self,
                 mean_offset_seconds: float,
                 offset_path: np.ndarray,
                 dtw_distance: float,
                 alignment_path: List[Tuple[int, int]],
                 confidence: float,
                 drift_detected: bool,
                 drift_magnitude_seconds: float,
                 processing_time: float):
        self.mean_offset_seconds = mean_offset_seconds
        self.offset_path = offset_path
        self.dtw_distance = dtw_distance
        self.alignment_path = alignment_path
        self.confidence = confidence
        self.drift_detected = drift_detected
        self.drift_magnitude_seconds = drift_magnitude_seconds
        self.processing_time = processing_time

    def __repr__(self):
        return (f"DTWSyncResult(mean_offset={self.mean_offset_seconds:.3f}s, "
                f"drift={self.drift_detected}, drift_mag={self.drift_magnitude_seconds:.3f}s, "
                f"confidence={self.confidence:.3f}, time={self.processing_time:.2f}s)")


class QuickDTWDetector:
    """
    Quick DTW sync detector for testing.

    Uses librosa's optimized DTW with Sakoe-Chiba band constraint for speed.
    """

    def __init__(self,
                 sample_rate: int = 22050,
                 hop_length: int = 512,
                 n_mfcc: int = 13,
                 window_constraint: int = 100,
                 max_duration: float = 300.0):
        """
        Args:
            sample_rate: Audio sample rate for analysis
            hop_length: STFT hop length (frames between samples)
            n_mfcc: Number of MFCC coefficients
            window_constraint: Sakoe-Chiba band width (frames from diagonal)
            max_duration: Maximum audio duration to analyze (seconds)
        """
        self.sample_rate = sample_rate
        self.hop_length = hop_length
        self.n_mfcc = n_mfcc
        self.window_constraint = window_constraint
        self.max_duration = max_duration

    def detect_sync(self,
                    master_path: str,
                    dub_path: str,
                    feature_type: str = 'mfcc') -> DTWSyncResult:
        """
        Detect sync using DTW alignment.

        Args:
            master_path: Path to master audio/video
            dub_path: Path to dub audio/video
            feature_type: Feature to use ('mfcc', 'chroma')

        Returns:
            DTWSyncResult with alignment path and offset information
        """
        start_time = time.time()

        logger.info(f"Loading master: {Path(master_path).name}")
        master_features = self._extract_features(master_path, feature_type)
        logger.info(f"  Master features: {master_features.shape} ({master_features.shape[1]} frames)")

        logger.info(f"Loading dub: {Path(dub_path).name}")
        dub_features = self._extract_features(dub_path, feature_type)
        logger.info(f"  Dub features: {dub_features.shape} ({dub_features.shape[1]} frames)")

        logger.info(f"Running DTW (window={self.window_constraint} frames)...")
        dtw_start = time.time()
        distance, path = self._dtw_align(master_features, dub_features)
        dtw_time = time.time() - dtw_start
        logger.info(f"  DTW completed in {dtw_time:.2f}s, distance={distance:.2f}")

        # Convert alignment path to offsets
        offset_path = self._path_to_offsets(path, master_features.shape[1])

        # Calculate statistics
        mean_offset_frames = np.mean(offset_path)
        mean_offset_seconds = mean_offset_frames * self.hop_length / self.sample_rate

        # Detect drift (significant offset variation)
        offset_std = np.std(offset_path)
        drift_frames = np.max(offset_path) - np.min(offset_path)
        drift_detected = offset_std > 5.0  # > 5 frames variation
        drift_magnitude = drift_frames * self.hop_length / self.sample_rate

        # Calculate confidence based on DTW distance
        confidence = self._calculate_confidence(distance, master_features.shape[1])

        processing_time = time.time() - start_time

        logger.info(f"Results:")
        logger.info(f"  Mean offset: {mean_offset_seconds:.3f}s ({mean_offset_frames:.1f} frames)")
        logger.info(f"  Offset range: {np.min(offset_path):.1f} to {np.max(offset_path):.1f} frames")
        logger.info(f"  Drift: {'YES' if drift_detected else 'NO'} "
                   f"({drift_magnitude:.3f}s, std={offset_std:.2f} frames)")
        logger.info(f"  Confidence: {confidence:.3f}")
        logger.info(f"  Total time: {processing_time:.2f}s")

        return DTWSyncResult(
            mean_offset_seconds=mean_offset_seconds,
            offset_path=offset_path,
            dtw_distance=distance,
            alignment_path=path,
            confidence=confidence,
            drift_detected=drift_detected,
            drift_magnitude_seconds=drift_magnitude,
            processing_time=processing_time
        )

    def _extract_features(self, audio_path: str, feature_type: str) -> np.ndarray:
        """Extract features for DTW comparison."""
        # Load audio (limit duration for speed)
        logger.info(f"  Loading audio (max {self.max_duration}s)...")
        y, sr = librosa.load(audio_path, sr=self.sample_rate,
                            duration=self.max_duration, mono=True)
        logger.info(f"  Loaded {len(y)/sr:.1f}s audio @ {sr}Hz")

        if feature_type == 'mfcc':
            logger.info(f"  Extracting MFCC (n_mfcc={self.n_mfcc})...")
            features = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=self.n_mfcc,
                                           hop_length=self.hop_length)
        elif feature_type == 'chroma':
            logger.info(f"  Extracting chroma...")
            features = librosa.feature.chroma_cqt(y=y, sr=sr,
                                                 hop_length=self.hop_length)
        else:
            raise ValueError(f"Unknown feature type: {feature_type}")

        # Normalize features
        features = (features - np.mean(features, axis=1, keepdims=True)) / \
                   (np.std(features, axis=1, keepdims=True) + 1e-8)

        return features

    def _dtw_align(self,
                   master: np.ndarray,
                   dub: np.ndarray) -> Tuple[float, List[Tuple[int, int]]]:
        """
        Perform DTW alignment with Sakoe-Chiba band constraint.

        Args:
            master: Master features (n_features x n_frames_master)
            dub: Dub features (n_features x n_frames_dub)

        Returns:
            (distance, path) where path is list of (master_idx, dub_idx) tuples
        """
        # Transpose for librosa.sequence.dtw (expects frames x features)
        master_T = master.T
        dub_T = dub.T

        # Run DTW with Sakoe-Chiba band constraint
        # This limits the search to ±window_constraint frames from diagonal
        D, wp = librosa.sequence.dtw(X=master_T,
                                     Y=dub_T,
                                     metric='euclidean',
                                     step_sizes_sigma=np.array([[1, 1], [0, 1], [1, 0]]),
                                     weights_add=np.array([0, 0, 0]),
                                     weights_mul=np.array([1, 1, 1]),
                                     subseq=False,
                                     backtrack=True,
                                     global_constraints=False,
                                     band_rad=self.window_constraint)

        # Extract distance and path
        distance = D[-1, -1]  # Accumulated distance at end
        path = list(zip(wp[0], wp[1]))  # Convert to list of tuples

        return distance, path

    def _path_to_offsets(self,
                        path: List[Tuple[int, int]],
                        n_master_frames: int) -> np.ndarray:
        """
        Convert DTW alignment path to per-frame offset array.

        Args:
            path: DTW alignment path [(master_idx, dub_idx), ...]
            n_master_frames: Number of frames in master

        Returns:
            Array of offsets (dub_frame - master_frame) for each master frame
        """
        offsets = np.zeros(n_master_frames)

        # Map path to offsets
        for master_idx, dub_idx in path:
            if master_idx < n_master_frames:
                offsets[master_idx] = dub_idx - master_idx

        return offsets

    def _calculate_confidence(self, distance: float, n_frames: int) -> float:
        """
        Calculate confidence score from DTW distance.

        Lower distance = better alignment = higher confidence
        """
        # Normalize by number of frames
        normalized_distance = distance / n_frames

        # Convert to confidence (0-1 scale)
        # Heuristic: distance < 2.0 per frame is good
        confidence = np.clip(1.0 - (normalized_distance / 4.0), 0.0, 1.0)

        return confidence

    def visualize_alignment(self,
                           result: DTWSyncResult,
                           output_path: str = None):
        """
        Visualize DTW alignment path and offset over time.

        Creates plot showing:
        1. Alignment path (master frame vs dub frame)
        2. Offset over time (shows drift)
        """
        logger.info("Generating alignment visualization...")

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

        # Plot 1: Alignment path
        # Sample path for visualization (too many points otherwise)
        sample_interval = max(1, len(result.alignment_path) // 1000)
        sampled_path = result.alignment_path[::sample_interval]
        master_frames, dub_frames = zip(*sampled_path)

        ax1.plot(master_frames, dub_frames, 'b-', linewidth=0.8, alpha=0.7, label='DTW path')
        ax1.plot([0, len(result.offset_path)],
                [0, len(result.offset_path)],
                'r--', linewidth=2, label='Perfect sync (diagonal)')
        ax1.set_xlabel('Master Frame', fontsize=12)
        ax1.set_ylabel('Dub Frame', fontsize=12)
        ax1.set_title('DTW Alignment Path', fontsize=14, fontweight='bold')
        ax1.legend(fontsize=10)
        ax1.grid(True, alpha=0.3)

        # Plot 2: Offset over time
        time_seconds = np.arange(len(result.offset_path)) * \
                      self.hop_length / self.sample_rate
        offset_seconds = result.offset_path * self.hop_length / self.sample_rate

        ax2.plot(time_seconds, offset_seconds, 'g-', linewidth=2, label='Frame-by-frame offset')
        ax2.axhline(y=result.mean_offset_seconds, color='r', linestyle='--',
                   linewidth=2, label=f'Mean: {result.mean_offset_seconds:.3f}s')

        # Add drift range
        if result.drift_detected:
            min_offset = np.min(offset_seconds)
            max_offset = np.max(offset_seconds)
            ax2.axhspan(min_offset, max_offset, alpha=0.2, color='orange',
                       label=f'Drift range: {result.drift_magnitude_seconds:.3f}s')

        ax2.set_xlabel('Time (seconds)', fontsize=12)
        ax2.set_ylabel('Offset (seconds)', fontsize=12)
        ax2.set_title(f'Sync Offset Over Time (Drift: {"YES" if result.drift_detected else "NO"})',
                     fontsize=14, fontweight='bold')
        ax2.legend(fontsize=10)
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()

        if output_path:
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            logger.info(f"✅ Visualization saved: {output_path}")
        else:
            logger.info("Displaying plot...")
            plt.show()

        plt.close()


def compare_with_mfcc(master_path: str, dub_path: str):
    """Compare DTW result with standard MFCC cross-correlation."""
    logger.info("\n" + "="*70)
    logger.info("COMPARING DTW vs MFCC Cross-Correlation")
    logger.info("="*70)

    try:
        from sync_analyzer.core.audio_sync_detector import ProfessionalSyncDetector

        logger.info("\nRunning MFCC cross-correlation...")
        mfcc_detector = ProfessionalSyncDetector()
        mfcc_results = mfcc_detector.analyze_sync(master_path, dub_path, methods=['mfcc'])

        if 'mfcc' in mfcc_results:
            mfcc_offset = mfcc_results['mfcc'].offset_seconds
            mfcc_conf = mfcc_results['mfcc'].confidence
            logger.info(f"  MFCC offset: {mfcc_offset:.3f}s (confidence: {mfcc_conf:.3f})")
            return mfcc_offset, mfcc_conf
        else:
            logger.warning("  MFCC analysis failed")
            return None, None

    except Exception as e:
        logger.error(f"  Error running MFCC comparison: {e}")
        return None, None


def main():
    if len(sys.argv) != 3:
        print("Usage: python test_dtw_sync.py <master_file> <dub_file>")
        print("\nExample:")
        print("  python test_dtw_sync.py master.mp4 dub.mxf")
        sys.exit(1)

    master_file = sys.argv[1]
    dub_file = sys.argv[2]

    if not os.path.exists(master_file):
        print(f"Error: Master file not found: {master_file}")
        sys.exit(1)
    if not os.path.exists(dub_file):
        print(f"Error: Dub file not found: {dub_file}")
        sys.exit(1)

    print("="*70)
    print("DTW SYNC DETECTION TEST")
    print("="*70)
    print(f"Master: {Path(master_file).name}")
    print(f"Dub:    {Path(dub_file).name}")
    print("="*70)

    # Initialize detector
    detector = QuickDTWDetector(
        sample_rate=22050,
        hop_length=512,
        n_mfcc=13,
        window_constraint=100,  # ±100 frames from diagonal
        max_duration=300.0      # First 5 minutes
    )

    # Run DTW
    try:
        result = detector.detect_sync(master_file, dub_file, feature_type='mfcc')

        print("\n" + "="*70)
        print("DTW RESULTS")
        print("="*70)
        print(f"Mean Offset:      {result.mean_offset_seconds:+.3f}s")
        print(f"Confidence:       {result.confidence:.3f} ({result.confidence*100:.1f}%)")
        print(f"Drift Detected:   {'YES ⚠️' if result.drift_detected else 'NO ✓'}")
        print(f"Drift Magnitude:  {result.drift_magnitude_seconds:.3f}s")
        print(f"DTW Distance:     {result.dtw_distance:.2f}")
        print(f"Processing Time:  {result.processing_time:.2f}s")

        # Compare with MFCC
        mfcc_offset, mfcc_conf = compare_with_mfcc(master_file, dub_file)

        if mfcc_offset is not None:
            diff = abs(result.mean_offset_seconds - mfcc_offset)
            print("\n" + "="*70)
            print("COMPARISON: DTW vs MFCC")
            print("="*70)
            print(f"DTW offset:   {result.mean_offset_seconds:+.3f}s (confidence: {result.confidence:.3f})")
            print(f"MFCC offset:  {mfcc_offset:+.3f}s (confidence: {mfcc_conf:.3f})")
            print(f"Difference:   {diff:.3f}s")

            if diff < 0.5:
                print("✅ DTW and MFCC agree (within 0.5s)")
            elif diff < 1.0:
                print("⚠️  DTW and MFCC differ by 0.5-1.0s (review needed)")
            else:
                print("❌ DTW and MFCC significantly differ (>1.0s)")
                if result.drift_detected:
                    print("   → Likely due to drift (DTW captures this, MFCC doesn't)")

        # Generate visualization
        output_dir = Path(master_file).parent
        viz_filename = f"dtw_alignment_{Path(master_file).stem}_vs_{Path(dub_file).stem}.png"
        viz_path = output_dir / viz_filename

        print("\n" + "="*70)
        detector.visualize_alignment(result, str(viz_path))
        print("="*70)

        return result

    except Exception as e:
        logger.error(f"Error during DTW analysis: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
