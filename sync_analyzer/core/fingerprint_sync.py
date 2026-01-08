"""
Audio Fingerprint-based Sync Detection

Uses Chromaprint/AcoustID for robust audio fingerprinting and cross-correlation
to detect sync offsets between master and dub audio files.

Fingerprinting is particularly effective for:
- Same audio content with different encoding/compression
- Broadcast audio with minor processing differences
- Dubbed content where the underlying audio pattern is preserved
"""

import logging
import subprocess
import tempfile
import os
import time
from dataclasses import dataclass
from typing import Optional, Tuple, List
import numpy as np
from scipy import signal

logger = logging.getLogger(__name__)

# Chromaprint generates ~11.6 fingerprint frames per second
FINGERPRINT_SAMPLE_RATE = 11.6025


@dataclass
class FingerprintSyncResult:
    """Result of fingerprint-based sync detection."""
    offset_seconds: float
    confidence: float
    method: str = "fingerprint"
    master_duration: float = 0.0
    dub_duration: float = 0.0
    fingerprint_frames_master: int = 0
    fingerprint_frames_dub: int = 0
    correlation_peak: float = 0.0


class FingerprintSyncDetector:
    """
    Detects audio sync offset using Chromaprint audio fingerprinting.
    
    This method is robust to:
    - Different audio codecs and compression
    - Sample rate differences
    - Minor audio processing (normalization, limiting)
    """
    
    def __init__(self, fpcalc_path: str = None):
        """
        Initialize the fingerprint detector.
        
        Args:
            fpcalc_path: Path to fpcalc binary. Auto-detected if not provided.
        """
        self.fpcalc_path = fpcalc_path or self._find_fpcalc()
        if not self.fpcalc_path:
            raise RuntimeError(
                "fpcalc (Chromaprint) not found. Install with: "
                "brew install chromaprint (macOS/Linux) or "
                "sudo apt install libchromaprint-tools (Ubuntu)"
            )
        logger.info(f"FingerprintSyncDetector initialized with fpcalc: {self.fpcalc_path}")
    
    def _find_fpcalc(self) -> Optional[str]:
        """Find fpcalc binary in PATH or common locations."""
        # Check PATH
        try:
            result = subprocess.run(
                ["which", "fpcalc"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        
        # Check common locations
        common_paths = [
            "/home/linuxbrew/.linuxbrew/bin/fpcalc",
            "/usr/local/bin/fpcalc",
            "/usr/bin/fpcalc",
            "/opt/homebrew/bin/fpcalc",
        ]
        for path in common_paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
        
        return None
    
    def _extract_audio_to_wav(self, input_path: str, duration: float = None) -> str:
        """
        Extract audio from video/audio file to temporary WAV.
        
        Args:
            input_path: Path to input media file
            duration: Optional max duration in seconds
            
        Returns:
            Path to temporary WAV file
        """
        # Create temp file
        fd, wav_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        
        # Build ffmpeg command
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vn",  # No video
            "-ac", "1",  # Mono
            "-ar", "16000",  # 16kHz sample rate
            "-acodec", "pcm_s16le",
        ]
        
        if duration:
            cmd.extend(["-t", str(duration)])
        
        cmd.append(wav_path)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 min timeout
            )
            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr}")
                raise RuntimeError(f"Failed to extract audio: {result.stderr}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("FFmpeg timeout extracting audio")
        
        return wav_path
    
    def _get_fingerprint_raw(self, audio_path: str, max_duration: int = 600) -> Tuple[List[int], float]:
        """
        Get raw fingerprint data using fpcalc.
        
        Args:
            audio_path: Path to audio file
            max_duration: Maximum duration to fingerprint (seconds)
            
        Returns:
            Tuple of (fingerprint_array, duration)
        """
        cmd = [
            self.fpcalc_path,
            "-raw",  # Output raw fingerprint (integers)
            "-length", str(max_duration),
            audio_path
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                logger.error(f"fpcalc error: {result.stderr}")
                raise RuntimeError(f"fpcalc failed: {result.stderr}")
            
            # Parse output
            duration = 0.0
            fingerprint = []
            
            for line in result.stdout.strip().split('\n'):
                if line.startswith('DURATION='):
                    duration = float(line.split('=')[1])
                elif line.startswith('FINGERPRINT='):
                    fp_str = line.split('=')[1]
                    fingerprint = [int(x) for x in fp_str.split(',') if x]
            
            return fingerprint, duration
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("fpcalc timeout")
    
    def _fingerprint_to_signal(self, fingerprint: List[int]) -> np.ndarray:
        """
        Convert fingerprint integers to a continuous signal for correlation.
        
        Each fingerprint value is a 32-bit unsigned integer representing spectral features.
        We extract bit patterns to create a more detailed signal.
        """
        if not fingerprint:
            return np.array([])
        
        # Convert to numpy array - use uint32 since fpcalc outputs unsigned integers
        # that can exceed int32 max (2.1B vs 4.3B)
        fp_array = np.array(fingerprint, dtype=np.uint32)
        
        # Extract multiple bit planes for richer signal
        # This gives us 32 binary signals that we can correlate
        bit_signals = []
        for bit in range(32):
            bit_plane = (fp_array >> bit) & 1
            bit_signals.append(bit_plane)
        
        # Stack and average to get a continuous signal
        signal_matrix = np.vstack(bit_signals)
        combined_signal = signal_matrix.mean(axis=0)
        
        # Normalize
        combined_signal = (combined_signal - combined_signal.mean()) / (combined_signal.std() + 1e-8)
        
        return combined_signal
    
    def _cross_correlate(
        self,
        master_signal: np.ndarray,
        dub_signal: np.ndarray
    ) -> Tuple[int, float, float]:
        """
        Cross-correlate two fingerprint signals to find offset.
        
        Returns:
            Tuple of (offset_frames, confidence, peak_value)
        """
        if len(master_signal) == 0 or len(dub_signal) == 0:
            return 0, 0.0, 0.0
        
        # Cross-correlation
        correlation = signal.correlate(master_signal, dub_signal, mode='full')
        
        # Find peak
        abs_corr = np.abs(correlation)
        peak_idx = np.argmax(abs_corr)
        peak_value = abs_corr[peak_idx]
        
        # Offset calculation: for correlate(master, dub, mode='full'),
        # zero-lag is at len(dub) - 1
        offset_frames = peak_idx - (len(dub_signal) - 1)
        
        # Calculate confidence based on peak prominence
        mean_corr = np.mean(abs_corr)
        std_corr = np.std(abs_corr)
        
        # Peak prominence relative to noise floor
        prominence = (peak_value - mean_corr) / (std_corr + 1e-8)
        confidence = min(1.0, max(0.0, prominence / 5.0))
        
        return offset_frames, confidence, peak_value
    
    def detect_sync(
        self,
        master_path: str,
        dub_path: str,
        max_duration: int = 600,
        progress_callback: Optional[callable] = None
    ) -> FingerprintSyncResult:
        """
        Detect sync offset between master and dub using audio fingerprinting.
        
        Args:
            master_path: Path to master audio/video file
            dub_path: Path to dub audio/video file
            max_duration: Maximum duration to analyze (seconds)
            progress_callback: Optional callback for progress updates
            
        Returns:
            FingerprintSyncResult with offset and confidence
        """
        start_time = time.time()
        temp_files = []
        
        try:
            # Step 1: Extract fingerprints
            if progress_callback:
                progress_callback(10, "Extracting master fingerprint...")
            
            logger.info(f"Fingerprinting master: {master_path}")
            master_fp, master_duration = self._get_fingerprint_raw(master_path, max_duration)
            logger.info(f"Master fingerprint: {len(master_fp)} frames, {master_duration:.1f}s")
            
            if progress_callback:
                progress_callback(40, "Extracting dub fingerprint...")
            
            logger.info(f"Fingerprinting dub: {dub_path}")
            dub_fp, dub_duration = self._get_fingerprint_raw(dub_path, max_duration)
            logger.info(f"Dub fingerprint: {len(dub_fp)} frames, {dub_duration:.1f}s")
            
            if len(master_fp) == 0 or len(dub_fp) == 0:
                raise RuntimeError("Failed to extract fingerprints")
            
            # Step 2: Convert to signals
            if progress_callback:
                progress_callback(60, "Processing fingerprints...")
            
            master_signal = self._fingerprint_to_signal(master_fp)
            dub_signal = self._fingerprint_to_signal(dub_fp)
            
            # Step 3: Cross-correlate
            if progress_callback:
                progress_callback(80, "Computing cross-correlation...")
            
            offset_frames, confidence, peak_value = self._cross_correlate(master_signal, dub_signal)
            
            # Convert frames to seconds
            offset_seconds = offset_frames / FINGERPRINT_SAMPLE_RATE
            
            elapsed = time.time() - start_time
            logger.info(
                f"Fingerprint sync detection complete in {elapsed:.2f}s: "
                f"offset={offset_seconds:.3f}s, confidence={confidence:.2%}"
            )
            
            if progress_callback:
                progress_callback(100, "Analysis complete!")
            
            return FingerprintSyncResult(
                offset_seconds=offset_seconds,
                confidence=confidence,
                method="fingerprint",
                master_duration=master_duration,
                dub_duration=dub_duration,
                fingerprint_frames_master=len(master_fp),
                fingerprint_frames_dub=len(dub_fp),
                correlation_peak=peak_value
            )
            
        finally:
            # Cleanup temp files
            for f in temp_files:
                try:
                    os.unlink(f)
                except Exception:
                    pass


def detect_fingerprint_offset(
    master_path: str,
    dub_path: str,
    max_duration: int = 600
) -> dict:
    """
    Convenience function to detect sync offset using fingerprinting.
    
    Args:
        master_path: Path to master file
        dub_path: Path to dub file
        max_duration: Max duration to analyze
        
    Returns:
        Dict with offset_seconds, confidence, and metadata
    """
    detector = FingerprintSyncDetector()
    result = detector.detect_sync(master_path, dub_path, max_duration)
    
    return {
        "method": "fingerprint",
        "offset_seconds": result.offset_seconds,
        "confidence": result.confidence,
        "master_duration": result.master_duration,
        "dub_duration": result.dub_duration,
        "fingerprint_frames_master": result.fingerprint_frames_master,
        "fingerprint_frames_dub": result.fingerprint_frames_dub,
        "correlation_peak": result.correlation_peak
    }


# Quick test
if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) != 3:
        print("Usage: python fingerprint_sync.py <master_file> <dub_file>")
        sys.exit(1)
    
    master = sys.argv[1]
    dub = sys.argv[2]
    
    print(f"Master: {master}")
    print(f"Dub: {dub}")
    print()
    
    result = detect_fingerprint_offset(master, dub)
    
    print(f"Offset: {result['offset_seconds']:.3f} seconds")
    print(f"Confidence: {result['confidence']:.2%}")
    print(f"Master duration: {result['master_duration']:.1f}s")
    print(f"Dub duration: {result['dub_duration']:.1f}s")

