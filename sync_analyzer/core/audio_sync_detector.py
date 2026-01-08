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
import subprocess
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
        self._spectral_window = None
        self._chroma_filter = None
        self._freqs = None
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
                logger.info("torchaudio not available; MFCC will use librosa")

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
        logger.info(f"[LOAD_AUDIO] Processing: {audio_path.name}")
        try:
            # Check if this is an Atmos file that needs special handling
            temp_wav_paths: List[str] = []
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
                    temp_wav_paths.append(temp_wav_path)
                    logger.info(f"[LOAD_AUDIO] Atmos bed extracted to: {temp_wav_path}")
            except ImportError as e:
                logger.debug(f"[LOAD_AUDIO] Atmos module not available: {e}")
            except Exception as e:
                import logging as _logging
                _logging.getLogger(__name__).warning(f"[LOAD_AUDIO] Failed to extract Atmos bed, using direct load: {e}")

            # If still pointing at an A/V container (MOV/MP4/MXF/MKV), demux to mono WAV to avoid audioread timing drift
            if actual_path == audio_path and actual_path.suffix.lower() in {".mov", ".mp4", ".mxf", ".mkv", ".avi"}:
                try:
                    import tempfile
                    temp_demux = tempfile.mktemp(suffix=".wav", prefix="demux_")
                    cmd = [
                        "ffmpeg",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-y",
                        "-i",
                        str(actual_path),
                        "-vn",
                        "-ac",
                        "1",
                        "-ar",
                        str(self.sample_rate),
                        "-c:a",
                        "pcm_s16le",
                        temp_demux,
                    ]
                    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                    if proc.returncode == 0 and Path(temp_demux).exists():
                        actual_path = Path(temp_demux)
                        temp_wav_paths.append(temp_demux)
                        logger.info(f"[LOAD_AUDIO] Demuxed container to WAV: {temp_demux}")
                    else:
                        logger.warning(f"[LOAD_AUDIO] ffmpeg demux failed ({proc.returncode}): {proc.stderr.strip()}")
                except Exception as e:
                    logger.warning(f"[LOAD_AUDIO] Demux to WAV failed, using direct load: {e}")
            
            # Load with librosa for consistent preprocessing
            audio, original_sr = librosa.load(
                str(actual_path), 
                sr=self.sample_rate,
                mono=True,
                dtype=np.float32
            )
            
            # Clean up temporary file if created
            if temp_wav_paths:
                import os
                for _tmp in temp_wav_paths:
                    try:
                        os.remove(_tmp)
                        logger.debug(f"[LOAD_AUDIO] Cleaned up temp file: {_tmp}")
                    except Exception:
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

    def detect_bars_tone(self, audio: np.ndarray, max_search_seconds: float = 120.0) -> float:
        """
        Detect bars and tone (1kHz reference tone) at the head of the audio file.

        Bars and tone is a standard test signal at the start of professional video/audio
        consisting of a sustained 1kHz sine wave at reference level. This function finds
        where the tone ends and program content begins.

        Args:
            audio: Audio samples (at self.sample_rate)
            max_search_seconds: Maximum duration to search for tone (default 120s)

        Returns:
            Timestamp in seconds where program content starts (0.0 if no tone detected)
        """
        try:
            # Limit search to first N seconds
            max_samples = int(min(max_search_seconds, len(audio) / self.sample_rate) * self.sample_rate)
            search_audio = audio[:max_samples]

            # Parameters for tone detection
            tone_freq = 1000  # 1kHz reference tone
            freq_tolerance = 50  # ±50Hz tolerance
            window_size = int(0.5 * self.sample_rate)  # 500ms analysis windows
            hop_size = int(0.1 * self.sample_rate)  # 100ms hop
            min_tone_duration = 5.0  # Minimum 5 seconds of continuous tone to be considered bars/tone

            tone_detected = []

            # Analyze windows for 1kHz tone presence
            for start in range(0, len(search_audio) - window_size, hop_size):
                window = search_audio[start:start + window_size]

                # Compute FFT
                fft = np.fft.rfft(window)
                freqs = np.fft.rfftfreq(len(window), 1.0 / self.sample_rate)
                magnitude = np.abs(fft)

                # Find peak frequency
                peak_idx = np.argmax(magnitude[1:]) + 1  # Skip DC component
                peak_freq = freqs[peak_idx]
                peak_mag = magnitude[peak_idx]

                # Calculate total energy and 1kHz band energy
                total_energy = np.sum(magnitude ** 2)

                # Find 1kHz band indices
                freq_min_idx = np.searchsorted(freqs, tone_freq - freq_tolerance)
                freq_max_idx = np.searchsorted(freqs, tone_freq + freq_tolerance)
                tone_band_energy = np.sum(magnitude[freq_min_idx:freq_max_idx] ** 2)

                # Tone is present if:
                # 1. Peak frequency is near 1kHz
                # 2. 1kHz band contains significant energy (>30% of total)
                is_tone = (
                    abs(peak_freq - tone_freq) < freq_tolerance and
                    tone_band_energy > 0.3 * total_energy and
                    peak_mag > 0.1 * np.max(magnitude)  # Peak is prominent
                )

                time_seconds = start / self.sample_rate
                tone_detected.append((time_seconds, is_tone))

            if not tone_detected:
                return 0.0

            # Find continuous tone region at the start
            tone_start = None
            tone_end = None
            consecutive_tone = 0
            consecutive_threshold = int(min_tone_duration / 0.1)  # Number of consecutive windows needed

            for i, (time_sec, is_tone) in enumerate(tone_detected):
                if is_tone:
                    if tone_start is None:
                        tone_start = time_sec
                    consecutive_tone += 1
                else:
                    # Check if we had enough consecutive tone windows
                    if consecutive_tone >= consecutive_threshold and tone_start is not None:
                        tone_end = time_sec
                        break
                    # Reset if not enough consecutive tone
                    if consecutive_tone < consecutive_threshold:
                        tone_start = None
                    consecutive_tone = 0

            # If tone was detected at the start and we found where it ends
            if tone_start is not None and tone_start < 1.0 and tone_end is not None:
                # Add small buffer after tone ends (0.5s for any silence/2-pop)
                program_start = tone_end + 0.5
                logger.info(f"Detected bars/tone from {tone_start:.1f}s to {tone_end:.1f}s, "
                           f"program starts at {program_start:.1f}s")
                return program_start

            # No significant tone detected at head
            logger.info("No bars/tone detected at head of file")
            return 0.0

        except Exception as e:
            logger.warning(f"Error detecting bars/tone: {e}, assuming no tone present")
            return 0.0

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
        
        # Spectral centroid + chroma (GPU if available)
        spectral_centroid = None
        chroma = None
        if self.use_gpu and self._device.startswith('cuda'):
            try:
                spectral_centroid, chroma = self._compute_spectral_chroma_gpu(audio)
            except Exception as e:
                logger.warning(f"GPU spectral/chroma failed, falling back to librosa: {e}")
        
        if spectral_centroid is None:
            spectral_centroid = librosa.feature.spectral_centroid(
                y=audio,
                sr=self.sample_rate,
                hop_length=self.hop_length
            )
        
        if chroma is None:
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

    def _compute_spectral_chroma_gpu(self, audio: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Compute spectral centroid and chroma features on GPU using torch."""
        import torch

        device = torch.device(self._device)
        wav = torch.from_numpy(audio.astype('float32')).to(device)
        if wav.dim() != 1:
            wav = wav.view(-1)

        if self._spectral_window is None or self._spectral_window.device != device:
            self._spectral_window = torch.hann_window(self.n_fft, device=device)

        try:
            stft = torch.stft(
                wav,
                n_fft=self.n_fft,
                hop_length=self.hop_length,
                window=self._spectral_window,
                center=True,
                pad_mode='reflect',
                return_complex=True
            )
        except TypeError:
            stft = torch.stft(
                wav,
                n_fft=self.n_fft,
                hop_length=self.hop_length,
                window=self._spectral_window,
                center=True,
                pad_mode='reflect',
                return_complex=False
            )
            stft = torch.view_as_complex(stft)

        magnitude = torch.abs(stft)
        power = magnitude * magnitude

        if self._freqs is None or self._freqs.device != device or self._freqs.numel() != power.shape[0]:
            self._freqs = torch.linspace(0.0, self.sample_rate / 2.0, power.shape[0], device=device)

        centroid = (power * self._freqs[:, None]).sum(dim=0) / (power.sum(dim=0) + 1e-8)
        spectral_centroid = centroid.unsqueeze(0).detach().cpu().numpy()

        if self._chroma_filter is None or self._chroma_filter.device != device or self._chroma_filter.shape[1] != power.shape[0]:
            chroma_fb = librosa.filters.chroma(sr=self.sample_rate, n_fft=self.n_fft, n_chroma=12)
            self._chroma_filter = torch.from_numpy(chroma_fb).to(device)

        chroma = torch.matmul(self._chroma_filter, power)
        chroma_norm = torch.norm(chroma, p=2, dim=0, keepdim=True) + 1e-8
        chroma = chroma / chroma_norm
        chroma = chroma.detach().cpu().numpy()

        return spectral_centroid, chroma
    
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
        Sample-accurate raw audio cross-correlation matching batch analysis precision.
        Uses FULL sample rate (no downsampling) for exact sample-level precision.
        """
        # CRITICAL: Use 30 seconds to EXACTLY match batch analysis
        # Batch uses: duration: float = 30.0 (line 608 in optimized_large_file_detector.py)
        max_samples = int(30.0 * self.sample_rate)  # 30 seconds at full sample rate
        master_segment = master_audio[:max_samples]
        dub_segment = dub_audio[:max_samples]

        # Ensure same length
        min_len = min(len(master_segment), len(dub_segment))
        master_segment = master_segment[:min_len]
        dub_segment = dub_segment[:min_len]

        if min_len == 0:
            return self._create_low_confidence_result("Raw Audio - Empty audio")

        # Normalize to reduce bias from loud passages
        master_segment = master_segment - np.mean(master_segment)
        dub_segment = dub_segment - np.mean(dub_segment)
        master_std = np.std(master_segment) + 1e-8
        dub_std = np.std(dub_segment) + 1e-8
        master_segment = master_segment / master_std
        dub_segment = dub_segment / dub_std

        # Cross-correlation at FULL sample rate using FFT for speed
        correlation = scipy.signal.correlate(master_segment, dub_segment, mode='full', method='fft')

        # Use correlation_lags for precise lag calculation
        from scipy.signal import correlation_lags
        lags = correlation_lags(len(master_segment), len(dub_segment), mode='full')

        # Find peak
        correlation_abs = np.abs(correlation)
        peak_idx = np.argmax(correlation_abs)
        peak_value = float(correlation_abs[peak_idx])

        # CRITICAL: If multiple peaks share the same max value (within numeric tolerance),
        # prefer the lag with the smallest absolute shift to avoid runaway offsets.
        # This matches batch analysis logic exactly.
        near_max_mask = np.isclose(correlation_abs, peak_value, rtol=1e-6, atol=1e-6)
        if np.any(near_max_mask):
            candidate_lags = lags[near_max_mask]
            candidate_idxs = np.nonzero(near_max_mask)[0]
            best_local_idx = int(candidate_idxs[np.argmin(np.abs(candidate_lags))])
            peak_idx = best_local_idx
            peak_value = float(correlation_abs[peak_idx])

        # Get offset in samples (NO downsampling - exact sample precision)
        offset_samples = int(lags[peak_idx])
        offset_seconds = offset_samples / float(self.sample_rate)

        # Calculate confidence from peak prominence
        peak_height = correlation_abs[peak_idx]
        mean_correlation = np.mean(correlation_abs)
        std_correlation = np.std(correlation_abs)

        snr = (peak_height - mean_correlation) / (std_correlation + 1e-8)
        confidence = min(max(snr / 8, 0.0), 1.0)

        return SyncResult(
            offset_samples=offset_samples,
            offset_seconds=offset_seconds,
            confidence=confidence,
            method_used="Raw Audio Cross-Correlation (Sample-Accurate)",
            correlation_peak=float(peak_value),
            quality_score=confidence,
            frame_rate=self.sample_rate,  # Full sample rate
            analysis_metadata={
                "downsample_factor": 1,  # No downsampling
                "segment_length_seconds": min_len / self.sample_rate,
                "correlation_length": len(correlation),
                "sample_rate": self.sample_rate,
                "precision": "sample-accurate"
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

    def refine_offset_sample_accurate(self,
                                      master_audio: np.ndarray,
                                      dub_audio: np.ndarray,
                                      coarse_offset_samples: int,
                                      refinement_window_seconds: float = 2.0,
                                      search_range_samples: int = 2048) -> Tuple[int, float, Dict[str, float]]:
        """
        Refine offset to sample-accurate precision using raw audio cross-correlation
        and phase correlation verification.

        Args:
            master_audio: Master audio samples
            dub_audio: Dub audio samples
            coarse_offset_samples: Initial offset estimate from MFCC/onset methods
            refinement_window_seconds: Size of audio window to use for refinement
            search_range_samples: How many samples +/- to search around coarse offset

        Returns:
            Tuple of (refined_offset_samples, phase_coherence, metadata)
        """
        logger.info(f"Refining offset from coarse estimate: {coarse_offset_samples} samples")

        # Calculate window size in samples
        window_samples = int(refinement_window_seconds * self.sample_rate)

        # Extract windows from both audio files centered around the coarse offset
        # If offset is negative, dub is ahead of master
        if coarse_offset_samples < 0:
            # Dub is ahead, so dub starts at sample abs(offset)
            dub_start = abs(coarse_offset_samples)
            master_start = 0
        else:
            # Master is ahead
            master_start = coarse_offset_samples
            dub_start = 0

        # Add search range to window for correlation
        extended_window = window_samples + 2 * search_range_samples

        # Extract windows with bounds checking
        master_end = min(master_start + extended_window, len(master_audio))
        dub_end = min(dub_start + extended_window, len(dub_audio))

        master_window = master_audio[master_start:master_end]
        dub_window = dub_audio[dub_start:dub_end]

        if len(master_window) < window_samples or len(dub_window) < window_samples:
            logger.warning("Insufficient audio for refinement, returning coarse offset")
            return coarse_offset_samples, 0.0, {"status": "insufficient_audio"}

        # Normalize windows
        master_window = master_window / (np.max(np.abs(master_window)) + 1e-8)
        dub_window = dub_window / (np.max(np.abs(dub_window)) + 1e-8)

        # Perform sample-accurate cross-correlation on a focused search window
        # Use only the center portion for correlation to reduce computation
        search_master = master_window[:window_samples + search_range_samples]
        search_dub = dub_window[:window_samples + search_range_samples]

        # Cross-correlation
        correlation = scipy.signal.correlate(search_master, search_dub, mode='valid')

        if len(correlation) == 0:
            logger.warning("Empty correlation result, returning coarse offset")
            return coarse_offset_samples, 0.0, {"status": "empty_correlation"}

        # Find peak with sub-sample precision using parabolic interpolation
        peak_idx = np.argmax(np.abs(correlation))

        # Parabolic interpolation for sub-sample accuracy
        if 0 < peak_idx < len(correlation) - 1:
            alpha = correlation[peak_idx - 1]
            beta = correlation[peak_idx]
            gamma = correlation[peak_idx + 1]

            # Parabolic peak interpolation
            denom = alpha - 2*beta + gamma
            if abs(denom) > 1e-10:
                p = 0.5 * (alpha - gamma) / denom
                sub_sample_offset = peak_idx + p
            else:
                sub_sample_offset = peak_idx
        else:
            sub_sample_offset = peak_idx

        # Calculate refinement relative to search window
        # The correlation gives us the offset within our search window
        samples_from_coarse = int(round(sub_sample_offset - search_range_samples))
        refined_offset_samples = coarse_offset_samples + samples_from_coarse

        logger.info(f"Refinement adjustment: {samples_from_coarse} samples")
        logger.info(f"Refined offset: {refined_offset_samples} samples")

        # Calculate phase coherence for verification
        # Align the audio at the refined offset and measure phase correlation
        if refined_offset_samples < 0:
            aligned_dub_start = abs(refined_offset_samples)
            aligned_master_start = 0
        else:
            aligned_master_start = refined_offset_samples
            aligned_dub_start = 0

        # Extract aligned windows for phase analysis
        phase_window_samples = min(window_samples,
                                   len(master_audio) - aligned_master_start,
                                   len(dub_audio) - aligned_dub_start)

        if phase_window_samples > 0:
            aligned_master = master_audio[aligned_master_start:aligned_master_start + phase_window_samples]
            aligned_dub = dub_audio[aligned_dub_start:aligned_dub_start + phase_window_samples]

            # Compute phase correlation using FFT
            # Higher phase correlation = better alignment
            master_fft = np.fft.rfft(aligned_master)
            dub_fft = np.fft.rfft(aligned_dub)

            # Cross-power spectrum
            cross_power = master_fft * np.conj(dub_fft)
            cross_power_norm = cross_power / (np.abs(cross_power) + 1e-8)

            # Inverse FFT gives phase correlation
            phase_corr = np.fft.irfft(cross_power_norm)
            phase_coherence = float(np.max(np.abs(phase_corr)) / len(phase_corr))

            # Also calculate simple correlation coefficient
            correlation_coef = np.corrcoef(aligned_master, aligned_dub)[0, 1]

            # RMS difference (lower is better)
            rms_diff = np.sqrt(np.mean((aligned_master - aligned_dub) ** 2))

            metadata = {
                "phase_coherence": phase_coherence,
                "correlation_coefficient": float(correlation_coef),
                "rms_difference": float(rms_diff),
                "refinement_samples": samples_from_coarse,
                "sub_sample_precision": float(sub_sample_offset - peak_idx),
                "peak_correlation": float(correlation[peak_idx]),
                "status": "success"
            }
        else:
            phase_coherence = 0.0
            metadata = {"status": "insufficient_aligned_audio"}

        return refined_offset_samples, phase_coherence, metadata

    def analyze_sync(self,
                    master_path: Path,
                    dub_path: Path,
                    methods: Optional[List[str]] = None,
                    skip_bars_tone: bool = True) -> Dict[str, SyncResult]:
        """
        Perform comprehensive sync analysis between master and dub audio.

        Args:
            master_path: Path to master audio file
            dub_path: Path to dub audio file
            methods: List of methods to use ['mfcc', 'onset', 'spectral', 'ai']
                    If None, uses all available methods
            skip_bars_tone: If True, auto-detect and skip bars/tone at head of master

        Returns:
            Dictionary mapping method names to SyncResult objects
        """
        if methods is None:
            # IMPORTANT: Include 'correlation' for sample-accurate precision
            # MFCC/Onset/Spectral use hop_length=512 (~23ms resolution)
            # Raw audio correlation gives exact sample-level precision
            methods = ['mfcc', 'onset', 'spectral', 'correlation']

        logger.info(f"Starting sync analysis: {master_path.name} vs {dub_path.name}")

        # Load audio files
        master_audio, _ = self.load_and_preprocess_audio(master_path)
        dub_audio, _ = self.load_and_preprocess_audio(dub_path)

        # Detect bars/tone in master file
        master_program_start = 0.0
        if skip_bars_tone:
            master_program_start = self.detect_bars_tone(master_audio)
            if master_program_start > 0:
                logger.info(f"Master has bars/tone, program starts at {master_program_start:.2f}s")

        # Trim master audio if bars/tone detected (for correlation analysis only)
        if master_program_start > 0:
            start_sample = int(master_program_start * self.sample_rate)
            master_audio_for_analysis = master_audio[start_sample:]
            logger.info(f"Using master audio from {master_program_start:.2f}s for correlation "
                       f"({len(master_audio_for_analysis)/self.sample_rate:.2f}s)")
        else:
            master_audio_for_analysis = master_audio

        # Extract features (use trimmed master for analysis)
        logger.info("Extracting audio features...")
        master_features = self.extract_audio_features(master_audio_for_analysis)
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

        # ALWAYS include raw audio cross-correlation for sample-accurate precision
        # This matches the batch analysis precision and avoids hop_length quantization
        if 'correlation' in methods or 'raw_audio' in methods:
            logger.info("Performing sample-accurate raw audio cross-correlation...")
            result = self.raw_audio_cross_correlation(master_audio_for_analysis, dub_audio)
            # Store under both 'correlation' and 'raw_audio' for compatibility
            results['correlation'] = result
            results['raw_audio'] = result
        elif all(result.confidence < 0.2 for result in results.values()):
            # Fallback if not explicitly requested but all other methods failed
            logger.info("All methods low confidence, adding raw audio cross-correlation...")
            result = self.raw_audio_cross_correlation(master_audio_for_analysis, dub_audio)
            results['raw_audio'] = result
            results['correlation'] = result

        # Adjust offsets to account for bars/tone in master (report from file start)
        if master_program_start > 0:
            logger.info(f"Adjusting offsets by +{master_program_start:.2f}s for bars/tone in master")
            adjusted_results = {}
            for method, result in results.items():
                # Add bars/tone duration to offset so it's relative to file start
                adjusted_offset_seconds = result.offset_seconds + master_program_start
                adjusted_offset_samples = int(adjusted_offset_seconds * self.sample_rate)

                # Update metadata to note bars/tone was detected
                metadata = dict(result.analysis_metadata)
                metadata['bars_tone_detected'] = True
                metadata['bars_tone_duration'] = master_program_start
                metadata['offset_before_adjustment'] = result.offset_seconds

                adjusted_results[method] = SyncResult(
                    offset_samples=adjusted_offset_samples,
                    offset_seconds=adjusted_offset_seconds,
                    confidence=result.confidence,
                    method_used=result.method_used,
                    correlation_peak=result.correlation_peak,
                    quality_score=result.quality_score,
                    frame_rate=result.frame_rate,
                    analysis_metadata=metadata
                )
            results = adjusted_results

        logger.info(f"Sync analysis complete. Results: {list(results.keys())}")
        return results
    
    def get_consensus_result(self, results: Dict[str, SyncResult], requested_methods: Optional[List[str]] = None) -> SyncResult:
        """
        Get consensus result from multiple sync detection methods.
        
        Args:
            results: Dictionary of results from different methods
            requested_methods: Optional list of methods that were requested by user.
                             If provided, only these methods will be considered for consensus.
                             This ensures user's method selection is respected.
            
        Returns:
            Consensus SyncResult with highest confidence method as primary
        """
        if not results:
            return self._create_low_confidence_result("No Analysis Methods")
        
        # If user specified methods, filter results to only include requested methods
        # This ensures that if user selects only "onset", we don't use MFCC results
        requested_results = {}
        if requested_methods:
            # Normalize method names (handle aliases like raw_audio -> correlation)
            method_aliases = {
                'raw_audio': 'correlation',
            }
            # Build set of allowed method names
            allowed_methods = set(requested_methods)
            # Add aliases
            for req_method in requested_methods:
                if req_method in method_aliases:
                    allowed_methods.add(method_aliases[req_method])
            
            # Filter results to only requested methods
            filtered_results = {
                method: result for method, result in results.items()
                if method in allowed_methods
            }
            if filtered_results:
                requested_results = filtered_results
                results = filtered_results  # Use filtered results for consensus
                logger.info(f"Consensus filtering to requested methods: {requested_methods} (found: {list(results.keys())})")
            elif results:
                # If filtering removed all results but we have some, log warning but continue
                # This handles edge cases where method names don't match exactly
                logger.warning(f"Requested methods {requested_methods} not found in results {list(results.keys())}, using all results")
        
        # Filter high-confidence results
        high_confidence_results = {
            method: result for method, result in results.items()
            if result.confidence >= self.confidence_threshold
        }
        
        # If user requested specific methods, prioritize them even if low confidence
        # Only use other methods if no requested methods exist
        if requested_results and not any(method in high_confidence_results for method in requested_results.keys()):
            # User requested methods but they all have low confidence
            # Still use the requested method with highest confidence (user's explicit choice)
            best_requested_method = max(requested_results.keys(),
                                       key=lambda x: requested_results[x].confidence)
            best_requested_result = requested_results[best_requested_method]
            logger.info(f"Using requested method '{best_requested_method}' despite low confidence ({best_requested_result.confidence:.2%}) - respecting user selection")
            return SyncResult(
                offset_samples=best_requested_result.offset_samples,
                offset_seconds=best_requested_result.offset_seconds,
                confidence=best_requested_result.confidence,
                method_used=f"Requested ({best_requested_method})",
                correlation_peak=best_requested_result.correlation_peak,
                quality_score=best_requested_result.quality_score,
                frame_rate=best_requested_result.frame_rate,
                analysis_metadata={
                    "note": "Low confidence but using requested method",
                    "requested_methods": requested_methods,
                    "all_methods": list(results.keys()),
                }
            )
        
        if high_confidence_results:
            # If user requested specific methods, prefer them over default priority
            if requested_methods and requested_results:
                # Filter high-confidence to only requested methods if available
                requested_high_confidence = {
                    method: result for method, result in high_confidence_results.items()
                    if method in requested_results
                }
                if requested_high_confidence:
                    # Use requested method with highest confidence
                    best_method = max(requested_high_confidence.keys(),
                                    key=lambda x: requested_high_confidence[x].confidence)
                    best_result = requested_high_confidence[best_method]
                    logger.info(f"Using requested method '{best_method}' from high-confidence results (respecting user selection)")
                    return SyncResult(
                        offset_samples=best_result.offset_samples,
                        offset_seconds=best_result.offset_seconds,
                        confidence=best_result.confidence,
                        method_used=f"Consensus ({best_method} primary)",
                        correlation_peak=best_result.correlation_peak,
                        quality_score=np.mean([r.quality_score for r in requested_high_confidence.values()]),
                        frame_rate=best_result.frame_rate,
                        analysis_metadata={
                            "primary_method": best_method,
                            "contributing_methods": list(requested_high_confidence.keys()),
                            "method_results": {m: r.offset_seconds for m, r in requested_high_confidence.items()},
                            "requested_methods": requested_methods,
                        }
                    )
            
            # Default priority: Onset/Spectral agreement > MFCC > Correlation
            # Reasoning: Onset and Spectral are better at finding content matches
            # when files have bars/tone, different edits, or dubbed content

            onset_result = high_confidence_results.get('onset')
            spectral_result = high_confidence_results.get('spectral')

            # Check if onset and spectral agree (within 2 seconds)
            if onset_result and spectral_result:
                offset_diff = abs(onset_result.offset_seconds - spectral_result.offset_seconds)
                if offset_diff < 2.0:
                    # They agree - use the higher confidence one
                    if spectral_result.confidence >= onset_result.confidence:
                        best_method = 'spectral'
                        best_result = spectral_result
                    else:
                        best_method = 'onset'
                        best_result = onset_result
                    logger.info(f"Using {best_method} method (onset/spectral agreement, diff={offset_diff:.3f}s)")
                else:
                    # They disagree - fall through to other logic
                    logger.warning(f"Onset/spectral disagreement: {offset_diff:.3f}s - using fallback selection")
                    # Use correlation if available (for identical content case)
                    if 'correlation' in high_confidence_results:
                        best_method = 'correlation'
                        best_result = high_confidence_results[best_method]
                        logger.info("Using correlation method (onset/spectral disagreement)")
                    else:
                        best_method = max(high_confidence_results.keys(),
                                        key=lambda x: high_confidence_results[x].confidence)
                        best_result = high_confidence_results[best_method]
            elif onset_result or spectral_result:
                # Only one of onset/spectral available - use it
                if spectral_result:
                    best_method = 'spectral'
                    best_result = spectral_result
                else:
                    best_method = 'onset'
                    best_result = onset_result
                logger.info(f"Using {best_method} method (only onset/spectral available)")
            elif 'mfcc' in high_confidence_results:
                best_method = 'mfcc'
                best_result = high_confidence_results[best_method]
                logger.info("Using MFCC method")
            elif 'correlation' in high_confidence_results:
                best_method = 'correlation'
                best_result = high_confidence_results[best_method]
                logger.info("Using correlation method (sample-accurate precision)")
            elif 'raw_audio' in high_confidence_results:
                best_method = 'raw_audio'
                best_result = high_confidence_results[best_method]
                logger.info("Using raw_audio method (sample-accurate precision)")
            else:
                # Use highest confidence result from other methods
                best_method = max(high_confidence_results.keys(),
                                key=lambda x: high_confidence_results[x].confidence)
                best_result = high_confidence_results[best_method]

            # Use the best result directly (no weighted average that could introduce errors)
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
