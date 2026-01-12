"""
SmartVerifier - Intelligent verification system for GPU sync analysis

This module provides automatic verification triggers based on multiple indicators
to catch potentially incorrect GPU (Wav2Vec2) results and verify them with
more reliable MFCC+Onset analysis.

Author: Sync Analyzer Team
Version: 1.0.0
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

import numpy as np
import librosa
import scipy.signal

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result of verification check."""
    needs_verification: bool
    triggered_indicators: List[str]
    severity_score: float  # 0.0 - 1.0, higher = more likely needs verification
    recommendation: str


@dataclass
class OnsetCheckResult:
    """Result of quick onset cross-check."""
    onset_offset: float
    onset_confidence: float
    gpu_deviation: float  # How far onset differs from GPU
    agrees_with_gpu: bool


class SmartVerifier:
    """
    Intelligent verification system that determines when GPU results need
    additional MFCC+Onset verification.
    
    Uses multiple indicators to assess confidence:
    - Large offset magnitude
    - Low GPU confidence score
    - Offset vs file duration ratio
    - Component disagreement (for multi-component jobs)
    - Quick onset cross-check
    """
    
    # Default thresholds for indicators
    INDICATORS = {
        'large_offset': 10.0,          # seconds - offsets > 10s get flagged
        'low_confidence': 0.70,        # GPU confidence below 70% triggers
        'offset_vs_duration': 0.5,     # offset > 50% of shorter file
        'component_disagreement': 0.5,  # seconds - component spread threshold
        'onset_deviation': 2.0,        # seconds - onset vs GPU difference
    }
    
    # Severity weights for each indicator
    SEVERITY_WEIGHTS = {
        'large_offset': 0.25,
        'low_confidence': 0.30,
        'offset_vs_duration': 0.20,
        'first_in_batch': 0.05,
        'component_disagreement': 0.30,
        'onset_deviation': 0.35,
    }
    
    # Threshold for triggering verification
    VERIFICATION_THRESHOLD = 0.30  # 30% severity triggers verification
    
    def __init__(self, 
                 sample_rate: int = 22050,
                 hop_length: int = 512,
                 custom_thresholds: Optional[Dict[str, float]] = None):
        """
        Initialize SmartVerifier.
        
        Args:
            sample_rate: Sample rate for onset detection
            hop_length: Hop length for onset detection
            custom_thresholds: Optional custom thresholds to override defaults
        """
        self.sample_rate = sample_rate
        self.hop_length = hop_length
        
        # Apply custom thresholds if provided
        self.thresholds = self.INDICATORS.copy()
        if custom_thresholds:
            self.thresholds.update(custom_thresholds)
        
        logger.info(f"SmartVerifier initialized with thresholds: {self.thresholds}")
    
    def check_indicators(self,
                        gpu_offset: float,
                        gpu_confidence: float,
                        master_duration: Optional[float] = None,
                        dub_duration: Optional[float] = None,
                        other_component_offsets: Optional[List[float]] = None,
                        is_first_in_batch: bool = False) -> VerificationResult:
        """
        Check all indicators and determine if verification is needed.
        
        Args:
            gpu_offset: Offset from GPU analysis (seconds)
            gpu_confidence: Confidence from GPU analysis (0-1)
            master_duration: Duration of master file (seconds)
            dub_duration: Duration of dub/component file (seconds)
            other_component_offsets: List of offsets from other components
            is_first_in_batch: Whether this is the first job in batch
            
        Returns:
            VerificationResult with triggered indicators and recommendation
        """
        triggered = []
        severity = 0.0
        
        # Check: Large offset
        if abs(gpu_offset) > self.thresholds['large_offset']:
            triggered.append(f"large_offset ({abs(gpu_offset):.1f}s > {self.thresholds['large_offset']}s)")
            severity += self.SEVERITY_WEIGHTS['large_offset']
            logger.debug(f"Indicator triggered: large_offset ({gpu_offset:.1f}s)")
        
        # Check: Low confidence
        if gpu_confidence < self.thresholds['low_confidence']:
            triggered.append(f"low_confidence ({gpu_confidence:.1%} < {self.thresholds['low_confidence']:.0%})")
            severity += self.SEVERITY_WEIGHTS['low_confidence']
            logger.debug(f"Indicator triggered: low_confidence ({gpu_confidence:.1%})")
        
        # Check: Offset vs duration ratio
        if master_duration and dub_duration:
            shorter_duration = min(master_duration, dub_duration)
            if shorter_duration > 0:
                ratio = abs(gpu_offset) / shorter_duration
                if ratio > self.thresholds['offset_vs_duration']:
                    triggered.append(f"offset_vs_duration ({ratio:.1%} > {self.thresholds['offset_vs_duration']:.0%})")
                    severity += self.SEVERITY_WEIGHTS['offset_vs_duration']
                    logger.debug(f"Indicator triggered: offset_vs_duration ({ratio:.1%})")
        
        # Check: First in batch (lower weight, just adds uncertainty)
        if is_first_in_batch:
            triggered.append("first_in_batch (no prior reference)")
            severity += self.SEVERITY_WEIGHTS['first_in_batch']
            logger.debug("Indicator triggered: first_in_batch")
        
        # Check: Component disagreement
        if other_component_offsets and len(other_component_offsets) > 0:
            all_offsets = [gpu_offset] + other_component_offsets
            spread = max(all_offsets) - min(all_offsets)
            if spread > self.thresholds['component_disagreement']:
                triggered.append(f"component_disagreement (spread={spread:.2f}s > {self.thresholds['component_disagreement']}s)")
                severity += self.SEVERITY_WEIGHTS['component_disagreement']
                logger.debug(f"Indicator triggered: component_disagreement ({spread:.2f}s)")
        
        # Determine if verification is needed
        needs_verification = severity >= self.VERIFICATION_THRESHOLD
        
        # Build recommendation
        if not triggered:
            recommendation = "GPU result appears reliable - no verification needed"
        elif needs_verification:
            recommendation = f"Verification recommended: {len(triggered)} indicator(s) triggered with {severity:.0%} severity"
        else:
            recommendation = f"Minor concerns ({len(triggered)} indicator(s)) but below threshold - GPU result likely OK"
        
        result = VerificationResult(
            needs_verification=needs_verification,
            triggered_indicators=triggered,
            severity_score=min(severity, 1.0),
            recommendation=recommendation
        )
        
        logger.info(f"SmartVerifier: needs_verify={needs_verification}, severity={severity:.0%}, "
                   f"indicators={len(triggered)}")
        
        return result
    
    def quick_onset_check(self,
                         master_path: str,
                         dub_path: str,
                         gpu_offset: float,
                         max_duration: float = 120.0) -> OnsetCheckResult:
        """
        Perform quick onset-based cross-check against GPU result.
        
        This is a fast check that extracts onsets from the first portion of
        both files and cross-correlates them to get an independent offset estimate.
        
        Args:
            master_path: Path to master audio file
            dub_path: Path to dub/component file
            gpu_offset: Offset reported by GPU analysis
            max_duration: Maximum duration to analyze (seconds)
            
        Returns:
            OnsetCheckResult with onset-based offset and comparison
        """
        logger.info(f"Quick onset check: comparing against GPU offset {gpu_offset:.2f}s")
        
        try:
            # Load audio (limited duration for speed)
            master_audio, _ = librosa.load(
                master_path, 
                sr=self.sample_rate, 
                duration=max_duration,
                mono=True
            )
            dub_audio, _ = librosa.load(
                dub_path, 
                sr=self.sample_rate, 
                duration=max_duration,
                mono=True
            )
            
            # Extract onset frames
            master_onsets = librosa.onset.onset_detect(
                y=master_audio,
                sr=self.sample_rate,
                hop_length=self.hop_length,
                units='frames'
            )
            dub_onsets = librosa.onset.onset_detect(
                y=dub_audio,
                sr=self.sample_rate,
                hop_length=self.hop_length,
                units='frames'
            )
            
            # Check for sufficient onsets
            if len(master_onsets) < 5 or len(dub_onsets) < 5:
                logger.warning("Insufficient onsets for cross-check")
                return OnsetCheckResult(
                    onset_offset=gpu_offset,  # Fall back to GPU
                    onset_confidence=0.0,
                    gpu_deviation=0.0,
                    agrees_with_gpu=True  # Can't disagree with no data
                )
            
            # Create onset signals
            max_length = max(
                master_onsets[-1] if len(master_onsets) > 0 else 0,
                dub_onsets[-1] if len(dub_onsets) > 0 else 0
            ) + 100
            
            master_signal = np.zeros(max_length)
            dub_signal = np.zeros(max_length)
            master_signal[master_onsets] = 1.0
            dub_signal[dub_onsets] = 1.0
            
            # Smooth signals
            window = np.hanning(5)
            master_signal = scipy.signal.convolve(master_signal, window, mode='same')
            dub_signal = scipy.signal.convolve(dub_signal, window, mode='same')
            
            # Cross-correlate
            correlation = scipy.signal.correlate(master_signal, dub_signal, mode='full')
            peak_idx = np.argmax(correlation)
            
            # Calculate offset
            offset_frames = peak_idx - (len(dub_signal) - 1)
            offset_samples = offset_frames * self.hop_length
            onset_offset = offset_samples / self.sample_rate
            
            # Calculate confidence
            peak_value = correlation[peak_idx]
            mean_corr = np.mean(np.abs(correlation))
            onset_confidence = min(peak_value / (mean_corr + 1e-8) / 5, 1.0)
            
            # Compare with GPU
            gpu_deviation = abs(onset_offset - gpu_offset)
            agrees = gpu_deviation < self.thresholds['onset_deviation']
            
            logger.info(f"Onset check: offset={onset_offset:.2f}s, conf={onset_confidence:.1%}, "
                       f"deviation={gpu_deviation:.2f}s, agrees={agrees}")
            
            return OnsetCheckResult(
                onset_offset=onset_offset,
                onset_confidence=onset_confidence,
                gpu_deviation=gpu_deviation,
                agrees_with_gpu=agrees
            )
            
        except Exception as e:
            logger.error(f"Onset check failed: {e}")
            return OnsetCheckResult(
                onset_offset=gpu_offset,
                onset_confidence=0.0,
                gpu_deviation=0.0,
                agrees_with_gpu=True  # Can't disagree on error
            )
    
    def full_check(self,
                   gpu_offset: float,
                   gpu_confidence: float,
                   master_path: str,
                   dub_path: str,
                   master_duration: Optional[float] = None,
                   dub_duration: Optional[float] = None,
                   other_component_offsets: Optional[List[float]] = None,
                   is_first_in_batch: bool = False,
                   skip_onset_check: bool = False) -> Tuple[VerificationResult, Optional[OnsetCheckResult]]:
        """
        Perform full verification check including optional onset cross-check.
        
        This combines indicator checking with onset cross-verification for
        the most thorough assessment of whether GPU results need verification.
        
        Args:
            gpu_offset: Offset from GPU analysis
            gpu_confidence: Confidence from GPU analysis
            master_path: Path to master file
            dub_path: Path to dub file
            master_duration: Duration of master file
            dub_duration: Duration of dub file
            other_component_offsets: Offsets from other components
            is_first_in_batch: Whether first in batch
            skip_onset_check: Skip onset check for speed
            
        Returns:
            Tuple of (VerificationResult, OnsetCheckResult or None)
        """
        # First check basic indicators
        indicator_result = self.check_indicators(
            gpu_offset=gpu_offset,
            gpu_confidence=gpu_confidence,
            master_duration=master_duration,
            dub_duration=dub_duration,
            other_component_offsets=other_component_offsets,
            is_first_in_batch=is_first_in_batch
        )
        
        onset_result = None
        
        # If indicators suggest verification might be needed, do onset check
        if not skip_onset_check and indicator_result.severity_score > 0.15:
            onset_result = self.quick_onset_check(
                master_path=master_path,
                dub_path=dub_path,
                gpu_offset=gpu_offset
            )
            
            # Update verification result based on onset check
            if onset_result and not onset_result.agrees_with_gpu:
                indicator_result.triggered_indicators.append(
                    f"onset_deviation ({onset_result.gpu_deviation:.2f}s)"
                )
                indicator_result.severity_score = min(
                    indicator_result.severity_score + self.SEVERITY_WEIGHTS['onset_deviation'],
                    1.0
                )
                indicator_result.needs_verification = True
                indicator_result.recommendation = (
                    f"Onset check disagrees with GPU ({onset_result.gpu_deviation:.2f}s deviation) - "
                    "verification strongly recommended"
                )
        
        return indicator_result, onset_result


# Convenience function for simple usage
def should_verify_gpu_result(
    gpu_offset: float,
    gpu_confidence: float,
    master_duration: Optional[float] = None,
    dub_duration: Optional[float] = None,
    other_component_offsets: Optional[List[float]] = None
) -> bool:
    """
    Simple helper to check if GPU result should be verified.
    
    Args:
        gpu_offset: Offset from GPU analysis
        gpu_confidence: Confidence from GPU analysis  
        master_duration: Duration of master file
        dub_duration: Duration of dub file
        other_component_offsets: Offsets from other components
        
    Returns:
        True if verification is recommended
    """
    verifier = SmartVerifier()
    result = verifier.check_indicators(
        gpu_offset=gpu_offset,
        gpu_confidence=gpu_confidence,
        master_duration=master_duration,
        dub_duration=dub_duration,
        other_component_offsets=other_component_offsets
    )
    return result.needs_verification

