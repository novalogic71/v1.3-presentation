#!/usr/bin/env python3
"""
Audio Channel Layout Detector
=============================

Automatically detects audio channel layout by analyzing audio content.
Uses spectral analysis, correlation, and frequency band analysis to determine
channel roles (L, R, C, LFE, Ls, Rs) with confidence scores.

Features:
- LFE detection via low-frequency ratio (<120Hz)
- Center/dialogue detection via mid-band energy (300Hz-3kHz)
- Stereo pair detection via pairwise correlation
- Confidence scoring for each channel assignment

Author: Sync Analyzer Team
Version: 1.0.0
"""

import os
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

import numpy as np
import scipy.signal
import scipy.fft

logger = logging.getLogger(__name__)


@dataclass
class ChannelAnalysis:
    """Analysis results for a single audio channel."""
    channel_index: int
    rms_level: float  # dB
    peak_level: float  # dB
    low_freq_ratio: float  # Ratio of energy <120Hz
    mid_freq_ratio: float  # Ratio of energy 300Hz-3kHz (dialogue band)
    high_freq_ratio: float  # Ratio of energy >3kHz
    spectral_centroid: float  # Hz - brightness indicator
    crest_factor: float  # Peak/RMS ratio - dynamics indicator
    is_silent: bool  # True if channel is effectively silent


@dataclass
class ChannelPair:
    """A detected stereo pair of channels."""
    channel_a: int
    channel_b: int
    correlation: float  # 0-1, higher = more correlated
    pair_type: str  # 'front_lr', 'surround_lr', 'unknown'


@dataclass
class ChannelLayoutResult:
    """Final channel layout detection result."""
    channel_count: int
    layout_name: str  # e.g., "5.1", "stereo", "7.1"
    channel_mapping: Dict[int, str]  # {0: "L", 1: "R", 2: "C", ...}
    confidence: float  # Overall confidence 0-1
    channel_confidences: Dict[int, float]  # Per-channel confidence
    channel_analyses: List[ChannelAnalysis]
    detected_pairs: List[ChannelPair]
    warnings: List[str] = field(default_factory=list)


class AudioChannelDetector:
    """
    Detects audio channel layout by analyzing audio content.
    
    Uses multiple analysis techniques:
    1. Frequency band analysis for LFE and Center detection
    2. Pairwise correlation for stereo pair detection
    3. Spectral analysis for channel characterization
    """
    
    # Frequency band definitions
    LFE_FREQ_MAX = 120  # Hz - LFE typically <120Hz
    DIALOGUE_FREQ_MIN = 300  # Hz
    DIALOGUE_FREQ_MAX = 3000  # Hz - dialogue/center channel band
    CORRELATION_FREQ_MIN = 100  # Hz
    CORRELATION_FREQ_MAX = 5000  # Hz - band for stereo pair correlation
    
    # Detection thresholds
    LFE_RATIO_THRESHOLD = 0.6  # >60% low freq energy suggests LFE
    CENTER_RATIO_THRESHOLD = 0.5  # >50% mid freq energy suggests Center
    CORRELATION_THRESHOLD = 0.7  # >0.7 correlation suggests stereo pair
    SILENCE_THRESHOLD_DB = -60  # dB - below this is silent
    
    def __init__(self, sample_rate: int = 48000, analysis_duration: float = 60.0):
        """
        Initialize the detector.
        
        Args:
            sample_rate: Sample rate for analysis (default 48kHz)
            analysis_duration: Seconds of audio to analyze (default 60s)
        """
        self.sample_rate = sample_rate
        self.analysis_duration = analysis_duration
        logger.info(f"AudioChannelDetector initialized (sr={sample_rate}, duration={analysis_duration}s)")
    
    def detect_layout(self, audio_path: str, skip_seconds: float = 60.0) -> ChannelLayoutResult:
        """
        Detect the audio channel layout of a file.
        
        Args:
            audio_path: Path to audio/video file
            skip_seconds: Seconds to skip at start (avoid bars/tone)
            
        Returns:
            ChannelLayoutResult with detected layout and confidence
        """
        logger.info(f"Detecting channel layout: {Path(audio_path).name}")
        
        # Step 1: Get channel count and extract mono channels
        channel_count = self._get_channel_count(audio_path)
        logger.info(f"Channel count: {channel_count}")
        
        if channel_count == 0:
            return ChannelLayoutResult(
                channel_count=0,
                layout_name="unknown",
                channel_mapping={},
                confidence=0.0,
                channel_confidences={},
                channel_analyses=[],
                detected_pairs=[],
                warnings=["Could not determine channel count"]
            )
        
        # Step 2: Extract and analyze each channel
        channel_analyses = []
        mono_channels = self._extract_mono_channels(audio_path, channel_count, skip_seconds)
        
        for ch_idx, channel_data in enumerate(mono_channels):
            analysis = self._analyze_channel(ch_idx, channel_data)
            channel_analyses.append(analysis)
            logger.info(f"  Ch{ch_idx}: RMS={analysis.rms_level:.1f}dB, "
                       f"LowFreq={analysis.low_freq_ratio:.1%}, "
                       f"MidFreq={analysis.mid_freq_ratio:.1%}, "
                       f"Centroid={analysis.spectral_centroid:.0f}Hz")
        
        # Step 3: Detect stereo pairs via correlation
        detected_pairs = self._detect_stereo_pairs(mono_channels, channel_analyses)
        for pair in detected_pairs:
            logger.info(f"  Pair detected: Ch{pair.channel_a}-Ch{pair.channel_b} "
                       f"correlation={pair.correlation:.2f} ({pair.pair_type})")
        
        # Step 4: Determine channel layout
        layout_result = self._determine_layout(
            channel_count, channel_analyses, detected_pairs
        )
        
        logger.info(f"Detected layout: {layout_result.layout_name} "
                   f"(confidence: {layout_result.confidence:.1%})")
        logger.info(f"Channel mapping: {layout_result.channel_mapping}")
        
        return layout_result
    
    def _get_channel_count(self, audio_path: str) -> int:
        """Get the number of audio channels in a file."""
        try:
            cmd = [
                'ffprobe', '-v', 'error',
                '-select_streams', 'a:0',
                '-show_entries', 'stream=channels',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                audio_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip())
        except Exception as e:
            logger.warning(f"Error getting channel count: {e}")
        return 0
    
    def _extract_mono_channels(
        self, 
        audio_path: str, 
        channel_count: int,
        skip_seconds: float
    ) -> List[np.ndarray]:
        """Extract each channel as a separate mono numpy array."""
        mono_channels = []
        
        for ch_idx in range(channel_count):
            try:
                # Use ffmpeg to extract single channel
                cmd = [
                    'ffmpeg', '-hide_banner', '-loglevel', 'error',
                    '-ss', str(skip_seconds),
                    '-t', str(self.analysis_duration),
                    '-i', audio_path,
                    '-filter_complex', f'[0:a]pan=mono|c0=c{ch_idx}[out]',
                    '-map', '[out]',
                    '-ar', str(self.sample_rate),
                    '-f', 'f32le',
                    '-'
                ]
                result = subprocess.run(cmd, capture_output=True, timeout=120)
                
                if result.returncode == 0 and len(result.stdout) > 0:
                    audio_data = np.frombuffer(result.stdout, dtype=np.float32)
                    mono_channels.append(audio_data)
                else:
                    logger.warning(f"Failed to extract channel {ch_idx}")
                    mono_channels.append(np.zeros(int(self.sample_rate * self.analysis_duration)))
                    
            except Exception as e:
                logger.warning(f"Error extracting channel {ch_idx}: {e}")
                mono_channels.append(np.zeros(int(self.sample_rate * self.analysis_duration)))
        
        return mono_channels
    
    def _analyze_channel(self, ch_idx: int, audio_data: np.ndarray) -> ChannelAnalysis:
        """Perform spectral and level analysis on a single channel."""
        sr = self.sample_rate
        
        # Handle empty or very short audio
        if len(audio_data) < sr:
            return ChannelAnalysis(
                channel_index=ch_idx,
                rms_level=-100.0,
                peak_level=-100.0,
                low_freq_ratio=0.0,
                mid_freq_ratio=0.0,
                high_freq_ratio=0.0,
                spectral_centroid=0.0,
                crest_factor=1.0,
                is_silent=True
            )
        
        # RMS and Peak level
        rms = np.sqrt(np.mean(audio_data ** 2))
        peak = np.max(np.abs(audio_data))
        
        rms_db = 20 * np.log10(rms + 1e-10)
        peak_db = 20 * np.log10(peak + 1e-10)
        crest_factor = peak / (rms + 1e-10)
        
        is_silent = rms_db < self.SILENCE_THRESHOLD_DB
        
        if is_silent:
            return ChannelAnalysis(
                channel_index=ch_idx,
                rms_level=rms_db,
                peak_level=peak_db,
                low_freq_ratio=0.0,
                mid_freq_ratio=0.0,
                high_freq_ratio=0.0,
                spectral_centroid=0.0,
                crest_factor=crest_factor,
                is_silent=True
            )
        
        # FFT for frequency analysis
        n_fft = min(8192, len(audio_data))
        freqs = np.fft.rfftfreq(n_fft, 1/sr)
        
        # Compute power spectrum (average over multiple windows)
        n_windows = min(100, len(audio_data) // n_fft)
        power_spectrum = np.zeros(len(freqs))
        
        for i in range(n_windows):
            start = i * n_fft
            window = audio_data[start:start + n_fft] * np.hanning(n_fft)
            spectrum = np.abs(np.fft.rfft(window)) ** 2
            power_spectrum += spectrum
        
        power_spectrum /= n_windows
        total_power = np.sum(power_spectrum) + 1e-10
        
        # Frequency band ratios
        low_mask = freqs < self.LFE_FREQ_MAX
        mid_mask = (freqs >= self.DIALOGUE_FREQ_MIN) & (freqs <= self.DIALOGUE_FREQ_MAX)
        high_mask = freqs > self.DIALOGUE_FREQ_MAX
        
        low_freq_ratio = np.sum(power_spectrum[low_mask]) / total_power
        mid_freq_ratio = np.sum(power_spectrum[mid_mask]) / total_power
        high_freq_ratio = np.sum(power_spectrum[high_mask]) / total_power
        
        # Spectral centroid (brightness)
        spectral_centroid = np.sum(freqs * power_spectrum) / total_power
        
        return ChannelAnalysis(
            channel_index=ch_idx,
            rms_level=rms_db,
            peak_level=peak_db,
            low_freq_ratio=low_freq_ratio,
            mid_freq_ratio=mid_freq_ratio,
            high_freq_ratio=high_freq_ratio,
            spectral_centroid=spectral_centroid,
            crest_factor=crest_factor,
            is_silent=is_silent
        )
    
    def _detect_stereo_pairs(
        self, 
        mono_channels: List[np.ndarray],
        channel_analyses: List[ChannelAnalysis]
    ) -> List[ChannelPair]:
        """Detect stereo pairs by computing pairwise correlation."""
        pairs = []
        n_channels = len(mono_channels)
        
        if n_channels < 2:
            return pairs
        
        # Bandpass filter for correlation (100Hz - 5kHz)
        sr = self.sample_rate
        nyquist = sr / 2
        low = self.CORRELATION_FREQ_MIN / nyquist
        high = min(self.CORRELATION_FREQ_MAX / nyquist, 0.99)
        
        try:
            b, a = scipy.signal.butter(4, [low, high], btype='band')
        except Exception:
            # Fallback if filter design fails
            b, a = [1], [1]
        
        # Filter all channels
        filtered_channels = []
        for ch_data in mono_channels:
            if len(ch_data) > 100:
                try:
                    filtered = scipy.signal.filtfilt(b, a, ch_data)
                except Exception:
                    filtered = ch_data
            else:
                filtered = ch_data
            filtered_channels.append(filtered)
        
        # Compute pairwise correlations
        correlations = {}
        for i in range(n_channels):
            # Skip silent channels
            if channel_analyses[i].is_silent:
                continue
            for j in range(i + 1, n_channels):
                if channel_analyses[j].is_silent:
                    continue
                
                ch_i = filtered_channels[i]
                ch_j = filtered_channels[j]
                
                # Normalize and compute correlation
                min_len = min(len(ch_i), len(ch_j))
                if min_len < 1000:
                    continue
                
                ch_i_norm = ch_i[:min_len]
                ch_j_norm = ch_j[:min_len]
                
                # Normalize
                ch_i_norm = (ch_i_norm - np.mean(ch_i_norm)) / (np.std(ch_i_norm) + 1e-10)
                ch_j_norm = (ch_j_norm - np.mean(ch_j_norm)) / (np.std(ch_j_norm) + 1e-10)
                
                # Correlation coefficient
                correlation = np.abs(np.mean(ch_i_norm * ch_j_norm))
                correlations[(i, j)] = correlation
        
        # Sort pairs by correlation (highest first)
        sorted_pairs = sorted(correlations.items(), key=lambda x: x[1], reverse=True)
        
        # Assign pair types
        assigned_channels = set()
        pair_order = 0
        
        for (ch_a, ch_b), corr in sorted_pairs:
            if corr < self.CORRELATION_THRESHOLD:
                continue
            if ch_a in assigned_channels or ch_b in assigned_channels:
                continue
            
            # Determine pair type based on order
            if pair_order == 0:
                pair_type = 'front_lr'
            elif pair_order == 1:
                pair_type = 'surround_lr'
            else:
                pair_type = 'unknown'
            
            pairs.append(ChannelPair(
                channel_a=ch_a,
                channel_b=ch_b,
                correlation=corr,
                pair_type=pair_type
            ))
            
            assigned_channels.add(ch_a)
            assigned_channels.add(ch_b)
            pair_order += 1
        
        return pairs
    
    def _determine_layout(
        self,
        channel_count: int,
        channel_analyses: List[ChannelAnalysis],
        detected_pairs: List[ChannelPair]
    ) -> ChannelLayoutResult:
        """Determine the channel layout based on analysis results."""
        
        channel_mapping = {}
        channel_confidences = {}
        warnings = []
        
        # Track which channels have been assigned
        assigned = set()
        
        # Step 1: Detect LFE channel (highest low-frequency ratio)
        lfe_candidates = [
            (ch.channel_index, ch.low_freq_ratio) 
            for ch in channel_analyses 
            if not ch.is_silent and ch.low_freq_ratio > self.LFE_RATIO_THRESHOLD
        ]
        
        if lfe_candidates:
            lfe_candidates.sort(key=lambda x: x[1], reverse=True)
            lfe_ch, lfe_ratio = lfe_candidates[0]
            channel_mapping[lfe_ch] = "LFE"
            channel_confidences[lfe_ch] = min(1.0, lfe_ratio / 0.8)  # Scale confidence
            assigned.add(lfe_ch)
            logger.info(f"  LFE detected: Ch{lfe_ch} (low_freq_ratio={lfe_ratio:.1%})")
        
        # Step 2: Detect Center channel (highest mid-frequency ratio, not in a pair)
        paired_channels = set()
        for pair in detected_pairs:
            paired_channels.add(pair.channel_a)
            paired_channels.add(pair.channel_b)
        
        center_candidates = [
            (ch.channel_index, ch.mid_freq_ratio)
            for ch in channel_analyses
            if not ch.is_silent 
            and ch.channel_index not in assigned 
            and ch.channel_index not in paired_channels
            and ch.mid_freq_ratio > self.CENTER_RATIO_THRESHOLD
        ]
        
        if center_candidates:
            center_candidates.sort(key=lambda x: x[1], reverse=True)
            center_ch, center_ratio = center_candidates[0]
            channel_mapping[center_ch] = "C"
            channel_confidences[center_ch] = min(1.0, center_ratio / 0.7)
            assigned.add(center_ch)
            logger.info(f"  Center detected: Ch{center_ch} (mid_freq_ratio={center_ratio:.1%})")
        
        # Step 3: Assign stereo pairs
        for pair in detected_pairs:
            if pair.channel_a in assigned or pair.channel_b in assigned:
                continue
            
            # Determine L/R based on typical channel order
            # Usually L comes before R in channel order
            if pair.channel_a < pair.channel_b:
                left_ch, right_ch = pair.channel_a, pair.channel_b
            else:
                left_ch, right_ch = pair.channel_b, pair.channel_a
            
            if pair.pair_type == 'front_lr':
                channel_mapping[left_ch] = "L"
                channel_mapping[right_ch] = "R"
            elif pair.pair_type == 'surround_lr':
                channel_mapping[left_ch] = "Ls"
                channel_mapping[right_ch] = "Rs"
            else:
                channel_mapping[left_ch] = f"L{len(assigned)//2 + 1}"
                channel_mapping[right_ch] = f"R{len(assigned)//2 + 1}"
            
            channel_confidences[left_ch] = pair.correlation
            channel_confidences[right_ch] = pair.correlation
            assigned.add(left_ch)
            assigned.add(right_ch)
        
        # Step 4: Handle unassigned channels
        for ch in channel_analyses:
            if ch.channel_index not in assigned:
                if ch.is_silent:
                    channel_mapping[ch.channel_index] = "Silent"
                    channel_confidences[ch.channel_index] = 1.0
                else:
                    channel_mapping[ch.channel_index] = f"Unknown_{ch.channel_index}"
                    channel_confidences[ch.channel_index] = 0.3
                    warnings.append(f"Channel {ch.channel_index} could not be identified")
        
        # Step 5: Determine layout name
        layout_name = self._get_layout_name(channel_count, channel_mapping)
        
        # Step 6: Calculate overall confidence
        if channel_confidences:
            overall_confidence = np.mean(list(channel_confidences.values()))
        else:
            overall_confidence = 0.0
        
        return ChannelLayoutResult(
            channel_count=channel_count,
            layout_name=layout_name,
            channel_mapping=channel_mapping,
            confidence=overall_confidence,
            channel_confidences=channel_confidences,
            channel_analyses=channel_analyses,
            detected_pairs=detected_pairs,
            warnings=warnings
        )
    
    def _get_layout_name(self, channel_count: int, mapping: Dict[int, str]) -> str:
        """Determine the standard layout name based on channel mapping."""
        channels_found = set(mapping.values())
        
        # Check for standard layouts
        if channel_count == 1:
            return "mono"
        elif channel_count == 2:
            if 'L' in channels_found and 'R' in channels_found:
                return "stereo"
            return "2.0"
        elif channel_count == 6:
            if all(ch in channels_found for ch in ['L', 'R', 'C', 'LFE', 'Ls', 'Rs']):
                return "5.1"
            elif all(ch in channels_found for ch in ['L', 'R', 'C', 'LFE']):
                return "5.1 (partial)"
            return "6ch"
        elif channel_count == 8:
            if 'LFE' in channels_found:
                return "7.1"
            return "8ch"
        else:
            return f"{channel_count}ch"


def detect_audio_layout(audio_path: str, skip_seconds: float = 60.0) -> Dict[str, Any]:
    """
    Convenience function to detect audio channel layout.
    
    Args:
        audio_path: Path to audio/video file
        skip_seconds: Seconds to skip at start (avoid bars/tone)
        
    Returns:
        Dictionary with layout info and confidence
    """
    detector = AudioChannelDetector()
    result = detector.detect_layout(audio_path, skip_seconds)
    
    return {
        "channel_count": result.channel_count,
        "layout_name": result.layout_name,
        "channel_mapping": result.channel_mapping,
        "confidence": result.confidence,
        "channel_confidences": result.channel_confidences,
        "warnings": result.warnings,
        "channel_details": [
            {
                "index": ch.channel_index,
                "rms_db": round(ch.rms_level, 1),
                "peak_db": round(ch.peak_level, 1),
                "low_freq_ratio": round(ch.low_freq_ratio, 3),
                "mid_freq_ratio": round(ch.mid_freq_ratio, 3),
                "spectral_centroid_hz": round(ch.spectral_centroid, 0),
                "is_silent": ch.is_silent,
                "assigned_role": result.channel_mapping.get(ch.channel_index, "Unknown")
            }
            for ch in result.channel_analyses
        ],
        "detected_pairs": [
            {
                "channels": [pair.channel_a, pair.channel_b],
                "correlation": round(pair.correlation, 3),
                "type": pair.pair_type
            }
            for pair in result.detected_pairs
        ]
    }


if __name__ == "__main__":
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("Usage: python audio_channel_detector.py <audio_file>")
        sys.exit(1)
    
    logging.basicConfig(level=logging.INFO)
    
    audio_file = sys.argv[1]
    result = detect_audio_layout(audio_file)
    
    print(json.dumps(result, indent=2))

