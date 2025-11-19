#!/usr/bin/env python3
"""
Professional Master-Dub Audio Sync Detection System
===================================================

A comprehensive audio synchronization analysis tool that uses both traditional
MFCC (Mel-Frequency Cepstral Coefficients) and modern AI embedding techniques
to detect sync issues between master and dubbed audio tracks.

Author: AI Audio Engineer
Version: 1.0.0
"""

import numpy as np
import librosa
import scipy.signal
import torch
import torch.nn.functional as F
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import logging
from scipy import signal
from sklearn.metrics.pairwise import cosine_similarity
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SyncResult:
    """Container for sync analysis results."""
    offset_samples: int
    offset_seconds: float
    confidence: float
    method_used: str
    correlation_peak: float
    quality_score: float
    frame_rate: float
    analysis_metadata: Dict[str, Any]

@dataclass
class AudioFeatures:
    """Container for extracted audio features."""
    mfcc: np.ndarray
    spectral_centroid: np.ndarray
    chroma: np.ndarray
    tempo: float
    onset_frames: np.ndarray
    rms: np.ndarray

class ProfessionalSyncDetector:
    """
    Professional-grade audio synchronization detector using multiple analysis methods.
    
    This class implements both traditional signal processing (MFCC, cross-correlation)
    and modern AI-based approaches for robust sync detection between master and dub audio.
    """
    
    def __init__(self, 
                 sample_rate: int = 22050,
                 hop_length: int = 512,
                 n_mfcc: int = 13,
                 n_fft: int = 2048,
                 window_size_seconds: float = 30.0,
                 confidence_threshold: float = 0.3,
                 use_gpu: bool = False):
        """
        Initialize the sync detector with professional audio analysis parameters.
        
        Args:
            sample_rate: Target sample rate for analysis
            hop_length: Number of samples between successive frames
            n_mfcc: Number of MFCC coefficients to extract
            n_fft: Length of FFT window
            window_size_seconds: Analysis window size in seconds
            confidence_threshold: Minimum confidence for reliable detection
        """
        self.sample_rate = sample_rate
        self.hop_length = hop_length
        self.n_mfcc = n_mfcc
        self.n_fft = n_fft
        self.window_size_seconds = window_size_seconds
        self.confidence_threshold = confidence_threshold
        
        # Analysis parameters
        self.window_size_samples = int(window_size_seconds * sample_rate)
        self.overlap_ratio = 0.5
        
        # Optional GPU acceleration for MFCC via torchaudio
        self.use_gpu = bool(use_gpu)
        self._device = 'cpu'
        self._mfcc_transform = None
        self._torchaudio_available = False
        if self.use_gpu:
            try:
                import torch  # noqa: F401
                if torch.cuda.is_available():
                    # Multi-GPU support: distribute load across available GPUs
                    gpu_count = torch.cuda.device_count()
                    import os
                    gpu_id = (os.getpid() % gpu_count) if gpu_count > 1 else 0
                    self._device = f'cuda:{gpu_id}'
                    logger.info(f"AudioSyncDetector using GPU {gpu_id} of {gpu_count} available")
                else:
                    self._device = 'cpu'
            except Exception:
                self._device = 'cpu'
                self.use_gpu = False
            try:
                import torchaudio  # noqa: F401
                self._torchaudio_available = True
            except Exception:
                self._torchaudio_available = False
                self.use_gpu = False  # disable GPU MFCC path if torchaudio missing

        logger.info(f"Initialized ProfessionalSyncDetector with SR={sample_rate}, "
                   f"window={window_size_seconds}s, MFCC={n_mfcc}")
    
    def load_and_preprocess_audio(self, audio_path: Path) -> Tuple[np.ndarray, float]:
        """
        Load and preprocess audio file with professional audio standards.
        
        Handles Atmos files by extracting bed audio first before loading.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Tuple of (audio_samples, original_sample_rate)
        """
        try:
            # Check if this is an Atmos file that needs special handling
            temp_wav_path = None
            actual_path = audio_path
            
            try:
                from .audio_channels import is_atmos_file, extract_atmos_bed_mono
                import tempfile
                
                if is_atmos_file(str(audio_path)):
                    logger.info(f"[LOAD_AUDIO] Detected Atmos file, extracting bed: {audio_path.name}")
                    # Extract Atmos bed to temporary WAV file
                    temp_wav_path = tempfile.mktemp(suffix=".wav", prefix="atmos_extracted_")
                    extract_atmos_bed_mono(str(audio_path), temp_wav_path, self.sample_rate)
                    actual_path = Path(temp_wav_path)
                    logger.info(f"[LOAD_AUDIO] Atmos bed extracted to: {temp_wav_path}")
            except ImportError as e:
                logger.debug(f"[LOAD_AUDIO] Atmos module not available: {e}")
            except Exception as e:
                logger.warning(f"[LOAD_AUDIO] Failed to extract Atmos bed, using direct load: {e}")
            
            # Load with librosa for consistent preprocessing
            audio, original_sr = librosa.load(
                str(actual_path), 
                sr=self.sample_rate,
                mono=True,
                dtype=np.float32
            )
            
            # Clean up temporary file if created
            if temp_wav_path:
                try:
                    import os
                    os.remove(temp_wav_path)
                    logger.debug(f"[LOAD_AUDIO] Cleaned up temp file: {temp_wav_path}")
                except:
                    pass
            
            # Normalize audio to prevent clipping
            if np.max(np.abs(audio)) > 0:
                audio = audio / np.max(np.abs(audio)) * 0.95
            
            # Apply gentle high-pass filter to remove DC offset and low-freq noise
            sos = signal.butter(4, 80, btype='high', fs=self.sample_rate, output='sos')
            audio = signal.sosfilt(sos, audio)
            
            logger.info(f"Loaded {audio_path.name}: {len(audio)/self.sample_rate:.2f}s, "
                       f"{original_sr}->{self.sample_rate} Hz")
            
            return audio, original_sr
            
        except Exception as e:
            logger.error(f"Error loading {audio_path}: {e}")
            raise
    
    def extract_audio_features(self, audio: np.ndarray) -> AudioFeatures:
        """
        Extract comprehensive audio features for sync analysis.
        
        Args:
            audio: Audio samples
            
        Returns:
            AudioFeatures object containing all extracted features
        """
        # MFCC features - primary for sync detection (GPU via torchaudio when enabled)
        mfcc = None
        if self.use_gpu and self._torchaudio_available:
            try:
                import torch
                from torchaudio import transforms as T
                if self._mfcc_transform is None:
                    self._mfcc_transform = T.MFCC(
                        sample_rate=self.sample_rate,
                        n_mfcc=self.n_mfcc,
                        melkwargs={
                            'n_fft': self.n_fft,
                            'hop_length': self.hop_length,
                            'n_mels': 64,
                            'f_min': 0.0,
                        }
                    ).to(self._device)
                with torch.no_grad():
                    wav = torch.from_numpy(audio.astype('float32')).to(self._device).unsqueeze(0)
                    mfcc_t = self._mfcc_transform(wav)  # (1, n_mfcc, time)
                    mfcc = mfcc_t.squeeze(0).detach().cpu().numpy()
            except Exception:
                mfcc = None
        if mfcc is None:
            mfcc = librosa.feature.mfcc(
                y=audio,
                sr=self.sample_rate,
                n_mfcc=self.n_mfcc,
                hop_length=self.hop_length,
                n_fft=self.n_fft
            )
        
        # Spectral centroid - for timbral matching
        spectral_centroid = librosa.feature.spectral_centroid(
            y=audio,
            sr=self.sample_rate,
            hop_length=self.hop_length
        )
        
        # Chroma features - for harmonic content matching
        chroma = librosa.feature.chroma_stft(
            y=audio,
            sr=self.sample_rate,
            hop_length=self.hop_length
        )
        
        # Tempo and onset detection
        tempo, _ = librosa.beat.beat_track(
            y=audio,
            sr=self.sample_rate,
            hop_length=self.hop_length
        )
        
        onset_frames = librosa.onset.onset_detect(
            y=audio,
            sr=self.sample_rate,
            hop_length=self.hop_length,
            units='frames'
        )
        
        # RMS energy for dynamic matching
        rms = librosa.feature.rms(
            y=audio,
            hop_length=self.hop_length
        )
        
        return AudioFeatures(
            mfcc=mfcc,
            spectral_centroid=spectral_centroid,
            chroma=chroma,
            tempo=tempo,
            onset_frames=onset_frames,
            rms=rms
        )
    
    def mfcc_cross_correlation_sync(self, 
                                   master_features: AudioFeatures,
                                   dub_features: AudioFeatures) -> SyncResult:
        """
        Perform sync detection using MFCC cross-correlation analysis.
        
        Args:
            master_features: Master audio features
            dub_features: Dub audio features
            
        Returns:
            SyncResult with offset and confidence information
        """
        # Use first MFCC coefficient (spectral shape) for correlation
        master_mfcc = master_features.mfcc[1, :]  # Skip C0 (energy)
        dub_mfcc = dub_features.mfcc[1, :]
        
        # Normalize features
        master_mfcc = (master_mfcc - np.mean(master_mfcc)) / (np.std(master_mfcc) + 1e-8)
        dub_mfcc = (dub_mfcc - np.mean(dub_mfcc)) / (np.std(dub_mfcc) + 1e-8)
        
        # Cross-correlation (correlate dub against master to find dub's position)
        correlation = scipy.signal.correlate(master_mfcc, dub_mfcc, mode='full')
        
        # Find peak
        peak_idx = np.argmax(np.abs(correlation))
        peak_value = correlation[peak_idx]
        
        # Convert to sample offset
        # For correlate(master, dub, mode='full'), zero-lag index is len(dub)-1
        offset_frames = peak_idx - (len(dub_mfcc) - 1)
        offset_samples = offset_frames * self.hop_length
        offset_seconds = offset_samples / self.sample_rate
        
        # Calculate confidence based on peak prominence (more lenient scoring)
        correlation_abs = np.abs(correlation)
        peak_height = correlation_abs[peak_idx]
        mean_correlation = np.mean(correlation_abs)
        std_correlation = np.std(correlation_abs)

        # Use signal-to-noise ratio approach: (peak - mean) / std
        snr = (peak_height - mean_correlation) / (std_correlation + 1e-8)
        confidence = min(max(snr / 5, 0.0), 1.0)  # Normalize SNR to 0-1 range
        
        # Quality assessment
        quality_score = self._assess_correlation_quality(correlation, peak_idx)
        
        return SyncResult(
            offset_samples=int(offset_samples),
            offset_seconds=offset_seconds,
            confidence=confidence,
            method_used="MFCC Cross-Correlation",
            correlation_peak=float(peak_value),
            quality_score=quality_score,
            frame_rate=self.sample_rate / self.hop_length,
            analysis_metadata={
                "correlation_length": len(correlation),
                "peak_index": peak_idx,
                "master_length": len(master_mfcc),
                "dub_length": len(dub_mfcc)
            }
        )
    
    def onset_based_sync(self,
                        master_features: AudioFeatures,
                        dub_features: AudioFeatures) -> SyncResult:
        """
        Perform sync detection using onset alignment.
        
        Args:
            master_features: Master audio features
            dub_features: Dub audio features
            
        Returns:
            SyncResult with onset-based sync analysis
        """
        master_onsets = master_features.onset_frames
        dub_onsets = dub_features.onset_frames
        
        if len(master_onsets) == 0 or len(dub_onsets) == 0:
            return self._create_low_confidence_result("Onset Detection - Insufficient onsets")
        
        # Create onset strength signals
        max_length = max(
            master_onsets[-1] if len(master_onsets) > 0 else 0,
            dub_onsets[-1] if len(dub_onsets) > 0 else 0
        ) + 100
        
        master_onset_signal = np.zeros(max_length)
        dub_onset_signal = np.zeros(max_length)
        
        master_onset_signal[master_onsets] = 1.0
        dub_onset_signal[dub_onsets] = 1.0
        
        # Smooth the signals
        master_onset_signal = scipy.signal.convolve(master_onset_signal, 
                                                   np.hanning(5), mode='same')
        dub_onset_signal = scipy.signal.convolve(dub_onset_signal, 
                                                np.hanning(5), mode='same')
        
        # Cross-correlate
        correlation = scipy.signal.correlate(master_onset_signal, dub_onset_signal, mode='full')
        peak_idx = np.argmax(correlation)
        
        # Zero-lag at len(dub)-1 for correlate(master, dub)
        offset_frames = peak_idx - (len(dub_onset_signal) - 1)
        offset_samples = offset_frames * self.hop_length
        offset_seconds = offset_samples / self.sample_rate
        
        # Calculate confidence
        peak_value = correlation[peak_idx]
        mean_correlation = np.mean(np.abs(correlation))
        confidence = min(peak_value / (mean_correlation + 1e-8) / 5, 1.0)
        
        return SyncResult(
            offset_samples=int(offset_samples),
            offset_seconds=offset_seconds,
            confidence=confidence,
            method_used="Onset-Based Alignment",
            correlation_peak=float(peak_value),
            quality_score=confidence,
            frame_rate=self.sample_rate / self.hop_length,
            analysis_metadata={
                "master_onsets": len(master_onsets),
                "dub_onsets": len(dub_onsets),
                "correlation_peak_idx": peak_idx
            }
        )
    
    def spectral_sync_detection(self,
                               master_features: AudioFeatures,
                               dub_features: AudioFeatures) -> SyncResult:
        """
        Perform sync detection using spectral features (chroma + spectral centroid).
        
        Args:
            master_features: Master audio features
            dub_features: Dub audio features
            
        Returns:
            SyncResult with spectral-based sync analysis
        """
        # Combine chroma and spectral centroid features
        master_spectral = np.vstack([
            master_features.chroma,
            master_features.spectral_centroid
        ])
        
        dub_spectral = np.vstack([
            dub_features.chroma,
            dub_features.spectral_centroid
        ])
        
        # Normalize each feature dimension
        master_spectral = (master_spectral - np.mean(master_spectral, axis=1, keepdims=True)) / \
                         (np.std(master_spectral, axis=1, keepdims=True) + 1e-8)
        dub_spectral = (dub_spectral - np.mean(dub_spectral, axis=1, keepdims=True)) / \
                      (np.std(dub_spectral, axis=1, keepdims=True) + 1e-8)
        
        # Calculate cross-correlation for each feature
        correlations = []
        for i in range(master_spectral.shape[0]):
            corr = scipy.signal.correlate(master_spectral[i], dub_spectral[i], mode='full')
            correlations.append(corr)
        
        # Combine correlations (weighted average)
        # Give higher weight to chroma features (indices 0-11) vs spectral centroid (index 12)
        weights = np.array([0.8/12] * 12 + [0.2])  # Normalize chroma weights, single weight for spectral centroid
        if len(weights) != len(correlations):
            # Fallback to equal weights if mismatch
            weights = None
        combined_correlation = np.average(correlations, axis=0, weights=weights)
        
        # Find peak
        peak_idx = np.argmax(np.abs(combined_correlation))
        peak_value = combined_correlation[peak_idx]
        
        # Convert to sample offset (zero-lag at len(dub)-1)
        offset_frames = peak_idx - (dub_spectral.shape[1] - 1)
        offset_samples = offset_frames * self.hop_length
        offset_seconds = offset_samples / self.sample_rate
        
        # Calculate confidence
        correlation_abs = np.abs(combined_correlation)
        peak_height = correlation_abs[peak_idx]
        mean_correlation = np.mean(correlation_abs)
        confidence = min(peak_height / (mean_correlation + 1e-8) / 8, 1.0)
        
        return SyncResult(
            offset_samples=int(offset_samples),
            offset_seconds=offset_seconds,
            confidence=confidence,
            method_used="Spectral Feature Correlation",
            correlation_peak=float(peak_value),
            quality_score=confidence,
            frame_rate=self.sample_rate / self.hop_length,
            analysis_metadata={
                "chroma_dims": master_features.chroma.shape[0],
                "spectral_dims": 1,
                "peak_index": peak_idx
            }
        )

    def raw_audio_cross_correlation(self, master_audio: np.ndarray, dub_audio: np.ndarray) -> SyncResult:
        """
        Fallback method using direct raw audio cross-correlation for difficult cases.
        """
        # Downsample for efficiency while preserving sync accuracy
        downsample_factor = 4
        master_down = master_audio[::downsample_factor]
        dub_down = dub_audio[::downsample_factor]

        # Use shorter segments if files are very long (first 2 minutes)
        max_samples = int(2 * 60 * self.sample_rate // downsample_factor)  # 2 minutes downsampled
        master_down = master_down[:max_samples]
        dub_down = dub_down[:max_samples]

        # Ensure same length
        min_len = min(len(master_down), len(dub_down))
        master_down = master_down[:min_len]
        dub_down = dub_down[:min_len]

        if min_len == 0:
            return self._create_low_confidence_result("Raw Audio - Empty audio")

        # Cross-correlation
        correlation = scipy.signal.correlate(master_down, dub_down, mode='full')
        peak_idx = np.argmax(np.abs(correlation))
        peak_value = correlation[peak_idx]

        # Convert to sample offset (accounting for downsampling)
        offset_frames = peak_idx - (len(dub_down) - 1)
        offset_samples = offset_frames * downsample_factor
        offset_seconds = offset_samples / self.sample_rate

        # Calculate confidence
        correlation_abs = np.abs(correlation)
        peak_height = correlation_abs[peak_idx]
        mean_correlation = np.mean(correlation_abs)
        std_correlation = np.std(correlation_abs)

        snr = (peak_height - mean_correlation) / (std_correlation + 1e-8)
        confidence = min(max(snr / 6, 0.0), 1.0)

        return SyncResult(
            offset_samples=int(offset_samples),
            offset_seconds=offset_seconds,
            confidence=confidence,
            method_used="Raw Audio Cross-Correlation",
            correlation_peak=float(peak_value),
            quality_score=confidence,
            frame_rate=self.sample_rate / downsample_factor,
            analysis_metadata={
                "downsample_factor": downsample_factor,
                "segment_length_seconds": min_len * downsample_factor / self.sample_rate,
                "correlation_length": len(correlation)
            }
        )

    def _assess_correlation_quality(self, correlation: np.ndarray, peak_idx: int) -> float:
        """Assess the quality of correlation result."""
        correlation_abs = np.abs(correlation)
        peak_value = correlation_abs[peak_idx]
        
        # Check for secondary peaks (indicates ambiguity)
        sorted_peaks = np.sort(correlation_abs)[-5:]  # Top 5 peaks
        if len(sorted_peaks) > 1:
            peak_ratio = sorted_peaks[-1] / (sorted_peaks[-2] + 1e-8)
        else:
            peak_ratio = 10.0
        
        # Quality factors
        snr = peak_value / (np.mean(correlation_abs) + 1e-8)
        sharpness = peak_ratio
        
        # Combine into quality score
        quality = min((snr / 10) * (sharpness / 5), 1.0)
        return float(quality)
    
    def _create_low_confidence_result(self, method: str) -> SyncResult:
        """Create a low-confidence result for failed analysis."""
        return SyncResult(
            offset_samples=0,
            offset_seconds=0.0,
            confidence=0.0,
            method_used=method,
            correlation_peak=0.0,
            quality_score=0.0,
            frame_rate=self.sample_rate / self.hop_length,
            analysis_metadata={"status": "analysis_failed"}
        )
    
    def analyze_sync(self, 
                    master_path: Path, 
                    dub_path: Path,
                    methods: Optional[List[str]] = None) -> Dict[str, SyncResult]:
        """
        Perform comprehensive sync analysis between master and dub audio.
        
        Args:
            master_path: Path to master audio file
            dub_path: Path to dub audio file
            methods: List of methods to use ['mfcc', 'onset', 'spectral', 'ai']
                    If None, uses all available methods
                    
        Returns:
            Dictionary mapping method names to SyncResult objects
        """
        if methods is None:
            methods = ['mfcc', 'onset', 'spectral']
        
        logger.info(f"Starting sync analysis: {master_path.name} vs {dub_path.name}")
        
        # Load audio files
        master_audio, _ = self.load_and_preprocess_audio(master_path)
        dub_audio, _ = self.load_and_preprocess_audio(dub_path)
        
        # Extract features
        logger.info("Extracting audio features...")
        master_features = self.extract_audio_features(master_audio)
        dub_features = self.extract_audio_features(dub_audio)
        
        # Perform analysis with selected methods
        results = {}
        
        if 'mfcc' in methods:
            logger.info("Performing MFCC cross-correlation analysis...")
            results['mfcc'] = self.mfcc_cross_correlation_sync(master_features, dub_features)
        
        if 'onset' in methods:
            logger.info("Performing onset-based sync analysis...")
            results['onset'] = self.onset_based_sync(master_features, dub_features)
        
        if 'spectral' in methods:
            logger.info("Performing spectral feature analysis...")
            results['spectral'] = self.spectral_sync_detection(master_features, dub_features)

        # Add robust raw audio fallback if all methods have low confidence
        if all(result.confidence < 0.2 for result in results.values()):
            logger.info("All methods low confidence, adding raw audio cross-correlation...")
            results['raw_audio'] = self.raw_audio_cross_correlation(master_audio, dub_audio)

        logger.info(f"Sync analysis complete. Results: {list(results.keys())}")
        return results
    
    def get_consensus_result(self, results: Dict[str, SyncResult]) -> SyncResult:
        """
        Get consensus result from multiple sync detection methods.
        
        Args:
            results: Dictionary of results from different methods
            
        Returns:
            Consensus SyncResult with highest confidence method as primary
        """
        if not results:
            return self._create_low_confidence_result("No Analysis Methods")
        
        # Filter high-confidence results
        high_confidence_results = {
            method: result for method, result in results.items()
            if result.confidence >= self.confidence_threshold
        }
        
        if high_confidence_results:
            # Use highest confidence result
            best_method = max(high_confidence_results.keys(),
                            key=lambda x: high_confidence_results[x].confidence)
            best_result = high_confidence_results[best_method]
            
            # Calculate consensus offset (weighted average)
            offsets = [r.offset_seconds for r in high_confidence_results.values()]
            confidences = [r.confidence for r in high_confidence_results.values()]
            
            if len(offsets) > 1:
                consensus_offset = np.average(offsets, weights=confidences)
                consensus_samples = int(consensus_offset * self.sample_rate)
            else:
                consensus_offset = best_result.offset_seconds
                consensus_samples = best_result.offset_samples
            
            return SyncResult(
                offset_samples=consensus_samples,
                offset_seconds=consensus_offset,
                confidence=best_result.confidence,
                method_used=f"Consensus ({best_method} primary)",
                correlation_peak=best_result.correlation_peak,
                quality_score=np.mean([r.quality_score for r in high_confidence_results.values()]),
                frame_rate=best_result.frame_rate,
                analysis_metadata={
                    "primary_method": best_method,
                    "contributing_methods": list(high_confidence_results.keys()),
                    "method_results": {m: r.offset_seconds for m, r in high_confidence_results.items()}
                }
            )
        else:
            # Return best available result even if low confidence
            best_method = max(results.keys(), key=lambda x: results[x].confidence)
            best_result = results[best_method]
            
            return SyncResult(
                offset_samples=best_result.offset_samples,
                offset_seconds=best_result.offset_seconds,
                confidence=best_result.confidence,
                method_used=f"Best Available ({best_method})",
                correlation_peak=best_result.correlation_peak,
                quality_score=best_result.quality_score,
                frame_rate=best_result.frame_rate,
                analysis_metadata={
                    "warning": "Low confidence results",
                    "all_methods": list(results.keys()),
                    "all_confidences": [r.confidence for r in results.values()]
                }
            )
