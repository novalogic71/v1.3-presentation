#!/usr/bin/env python3
"""
Optimized Large File Audio Sync Detector
Based on techniques from the Dub_Openl3 production system
Handles large video files with chunking and GPU acceleration
"""

import os
import sys
import json
import numpy as np
import soundfile as sf
import subprocess
import tempfile
import logging
from contextlib import nullcontext
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime

class OptimizedLargeFileDetector:
    """
    Intelligent multi-pass sync detector for large video files using adaptive chunking strategies
    """

    def __init__(self, gpu_enabled=True, chunk_size=30.0, max_chunks=10, enable_multi_pass=True):
        self.gpu_enabled = gpu_enabled
        self.chunk_size = chunk_size  # seconds
        self.max_chunks = max_chunks
        self.sample_rate = 22050
        self.temp_dir = tempfile.mkdtemp(prefix="sync_analysis_")
        self.logger = self._setup_logging()

        # Enhanced multi-pass analysis settings
        self.enable_multi_pass = enable_multi_pass
        self.refinement_chunk_size = 10.0  # Smaller chunks for pass 2
        self.gap_analysis_threshold = 0.3  # Confidence threshold for gap analysis
        self.drift_detection_sensitivity = 0.05  # 50ms drift sensitivity

        # Localized drift detection thresholds (seconds)
        self.localized_offset_max_seconds = 10.0   # Ignore huge outliers when clustering events
        self.localized_min_delta_seconds = 0.5      # Minimum deviation from baseline to flag an event
        self.localized_max_gap_seconds = 30.0       # Allowable gap when merging neighboring chunks
        self.localized_min_segments = 2             # Require at least N chunks to describe an event
        self.localized_min_duration = 45.0          # Require at least this duration unless confidence is strong

        # GPU detection and setup
        self.gpu_available = False
        self.device = "cpu"
        self._mfcc_transform = None
        self._torchaudio_available = False
        if gpu_enabled:
            self._detect_gpu()
    
    def _setup_logging(self):
        """Setup logging"""
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        return logging.getLogger(__name__)
    
    def _detect_gpu(self):
        """Detect GPU availability using PyTorch when present."""
        try:
            import torch  # type: ignore
            self.gpu_available = bool(torch.cuda.is_available())
            
            if self.gpu_available:
                # Multi-GPU support: distribute load across available GPUs
                gpu_count = torch.cuda.device_count()
                import os
                gpu_id = (os.getpid() % gpu_count) if gpu_count > 1 else 0
                self.device = f"cuda:{gpu_id}"
                self.logger.info(f"CUDA GPU {gpu_id}/{gpu_count-1} detected via PyTorch; enabling acceleration")
            else:
                self.device = "cpu"
                self.logger.info("PyTorch CUDA not available; running on CPU")
            # Check torchaudio availability for GPU MFCCs
            try:
                import torchaudio  # type: ignore
                _ = torchaudio.__version__  # access to avoid linters
                self._torchaudio_available = True
            except Exception:
                self._torchaudio_available = False
                self.logger.debug("torchaudio not available; MFCC will use librosa")
        except Exception:
            # If PyTorch isn't installed, simply run on CPU
            self.gpu_available = False
            self.device = "cpu"
            self.logger.info("PyTorch not available; running on CPU")
    
    def extract_audio_from_video(self, video_path: str) -> Optional[str]:
        """Extract audio from video file using ffmpeg with optimized parameters"""
        try:
            if not os.path.exists(video_path):
                self.logger.error(f"Video file not found: {video_path}")
                return None
            
            # Generate output filename
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            audio_file = os.path.join(self.temp_dir, f"{base_name}.wav")

            # Atmos-aware extraction: use the dedicated pipeline when applicable
            try:
                from .audio_channels import is_atmos_file, extract_atmos_bed_mono
                if is_atmos_file(video_path):
                    self.logger.info("Atmos content detected; extracting bed audio for chunked analysis")
                    extract_atmos_bed_mono(video_path, audio_file, self.sample_rate)
                    if os.path.exists(audio_file) and os.path.getsize(audio_file) > 0:
                        return audio_file
            except Exception as exc:
                self.logger.warning(f"Atmos extraction failed, falling back to ffmpeg: {exc}")
            
            # Extract audio with optimized settings
            cmd = [
                "ffmpeg", "-i", video_path, 
                "-vn",  # No video
                "-acodec", "pcm_s16le",  # 16-bit PCM
                "-ar", str(self.sample_rate),  # Sample rate
                "-ac", "1",  # Mono
                "-y",  # Overwrite
                audio_file
            ]
            
            self.logger.info(f"Extracting audio from {os.path.basename(video_path)}...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.error(f"FFmpeg failed: {result.stderr}")
                return None
            
            self.logger.info(f"Audio extracted: {audio_file}")
            return audio_file
            
        except Exception as e:
            self.logger.error(f"Error extracting audio: {e}")
            return None
    
    def get_audio_duration(self, audio_path: str) -> float:
        """Get audio duration efficiently (ffprobe only)."""
        try:
            cmd = ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", audio_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return float(result.stdout.strip())
        except Exception as e:
            self.logger.error(f"Error getting duration: {e}")
        return 0.0
    
    def create_audio_chunks(self, audio_path: str, duration: float) -> List[Tuple[float, float]]:
        """Create continuous overlapping audio chunks for drift detection"""
        chunks = []
        
        if duration <= self.chunk_size:
            # Small file - but still use overlapping chunks for consistency (ALWAYS long method)
            # Create overlapping chunks even for short files
            mini_chunk_size = min(self.chunk_size, duration / 3)  # At least 3 chunks for short files
            step_size = mini_chunk_size * 0.5
            current_start = 0.0
            while current_start < duration:
                chunk_end = min(current_start + mini_chunk_size, duration)
                chunks.append((current_start, chunk_end))
                if chunk_end >= duration:
                    break
                current_start += step_size
        else:
            # Enhanced continuous monitoring approach
            # Use smaller step size for better coverage  
            step_size = self.chunk_size * 0.3  # 70% overlap for more thorough analysis
            
            current_start = 0.0
            while current_start < duration - 10:  # Ensure at least 10s chunk at end
                chunk_end = min(current_start + self.chunk_size, duration)
                chunks.append((current_start, chunk_end))
                
                # Stop if we're within one step of the end
                if chunk_end >= duration:
                    break
                    
                current_start += step_size
            
            # Ensure we capture the very end if missed
            if chunks and chunks[-1][1] < duration - 5:  # If more than 5s left
                chunks.append((max(0, duration - self.chunk_size), duration))
        
        # Apply max chunks limit (use provided limit or smart default)
        if self.max_chunks > 0:  # If max_chunks is specified, use it
            max_allowed = self.max_chunks
        else:  # Use smart default based on duration
            max_allowed = min(200, int(duration / 15))  # Allow more chunks for long files
            
        if len(chunks) > max_allowed:
            # Subsample to stay within limits while maintaining coverage
            step = len(chunks) // max_allowed
            chunks = chunks[::step]
        
        self.logger.info(f"Created {len(chunks)} overlapping chunks for {duration:.1f}s audio (continuous monitoring)")
        return chunks
    
    def extract_chunk_features(self, audio_path: str, start_time: float, end_time: float) -> Dict[str, Any]:
        """Extract features from audio chunk with GPU acceleration if available"""
        try:
            # Load audio chunk using soundfile (audio already resampled to self.sample_rate by ffmpeg)
            info = sf.info(audio_path)
            sr = self.sample_rate  # Use resampled rate, not metadata rate
            start_frame = int(start_time * sr)
            n_frames = int((end_time - start_time) * sr)
            y, _ = sf.read(audio_path, start=start_frame, frames=n_frames, dtype='float32', always_2d=False)
            if y.ndim > 1:
                y = y.mean(axis=1)
            
            if len(y) == 0:
                return {}
            
            features = {}
            
            # 1. MFCC features (prefer torchaudio on GPU when available)
            mfcc = None
            if self.gpu_enabled and self._torchaudio_available:
                try:
                    import torch
                    import torchaudio
                    from torchaudio import transforms as T
                    # Lazy init of transform (bind to device)
                    if self._mfcc_transform is None:
                        self._mfcc_transform = T.MFCC(
                            sample_rate=self.sample_rate,
                            n_mfcc=13,
                            melkwargs={
                                'n_fft': 2048,
                                'n_mels': 40,
                                'hop_length': 512,
                                'f_min': 0.0,
                            }
                        ).to(self.device)
                    with torch.no_grad():
                        wav = torch.from_numpy(y.astype('float32')).to(self.device).unsqueeze(0)  # (1, N)
                        mfcc_t = self._mfcc_transform(wav)  # (1, n_mfcc, time)
                        mfcc_np = mfcc_t.squeeze(0).detach().cpu().numpy()  # (n_mfcc, time)
                        mfcc = mfcc_np
                except Exception as e:
                    self.logger.debug(f"GPU MFCC failed, falling back to librosa: {e}")
                    mfcc = None
            if mfcc is None:
                try:
                    import librosa  # lazy import; may fail in constrained envs
                    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
                except Exception as e:
                    self.logger.debug(f"librosa MFCC failed, skipping MFCC: {e}")
                    mfcc = None
            features['mfcc'] = mfcc
            
            # 2-6. Basic features without requiring librosa, to remain robust
            try:
                import numpy as _np
                # Zero crossing rate
                zcr = ((_np.diff(_np.sign(y)) != 0).sum() / max(len(y), 1))
                features['zcr'] = _np.array([zcr], dtype=_np.float32)
                # RMS energy (frame-agnostic)
                rms = _np.sqrt(_np.mean(y**2) + 1e-12)
                features['rms'] = _np.array([rms], dtype=_np.float32)
            except Exception:
                pass
            
            features['chunk_duration'] = len(y) / sr
            features['chunk_start'] = start_time
            features['chunk_end'] = end_time
            
            return features
            
        except Exception as e:
            self.logger.error(f"Error extracting chunk features: {e}")
            return {}

    def classify_audio_content(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify audio content type for adaptive parameter tuning

        Returns:
            Dict with content_type, confidence, and processing_hints
        """
        try:
            if not features or 'mfcc' not in features:
                return {'content_type': 'unknown', 'confidence': 0.0}

            mfcc = features['mfcc']
            if mfcc is None or mfcc.size == 0:
                return {'content_type': 'unknown', 'confidence': 0.0}

            # Calculate audio characteristics
            mfcc_mean = np.mean(mfcc, axis=1) if mfcc.ndim > 1 else np.array([np.mean(mfcc)])
            mfcc_var = np.var(mfcc, axis=1) if mfcc.ndim > 1 else np.array([np.var(mfcc)])

            # Get additional features
            zcr = features.get('zcr', np.array([0.0]))
            rms = features.get('rms', np.array([0.0]))

            avg_zcr = np.mean(zcr) if len(zcr) > 0 else 0.0
            avg_rms = np.mean(rms) if len(rms) > 0 else 0.0

            # Simple heuristic classification (can be enhanced with ML later)
            spectral_rolloff = np.mean(mfcc_var[:min(5, len(mfcc_var))]) if len(mfcc_var) > 0 else 0.0

            # Classification logic
            if avg_rms < 0.01:  # Very quiet
                content_type = 'silence'
                confidence = 0.8
                processing_hints = {
                    'skip_analysis': True,
                    'reliability_penalty': 0.5
                }
            elif avg_zcr > 0.1 and spectral_rolloff > 0.5:  # High frequency variation
                content_type = 'dialogue'
                confidence = 0.7
                processing_hints = {
                    'prefer_mfcc': True,
                    'onset_weight': 0.8,
                    'spectral_weight': 0.6
                }
            elif spectral_rolloff < 0.2 and avg_rms > 0.05:  # Low frequency, higher energy
                content_type = 'music'
                confidence = 0.6
                processing_hints = {
                    'prefer_spectral': True,
                    'onset_weight': 1.2,
                    'mfcc_weight': 0.8
                }
            else:
                content_type = 'mixed'
                confidence = 0.4
                processing_hints = {
                    'balanced_approach': True,
                    'onset_weight': 1.0,
                    'mfcc_weight': 1.0,
                    'spectral_weight': 1.0
                }

            return {
                'content_type': content_type,
                'confidence': confidence,
                'processing_hints': processing_hints,
                'characteristics': {
                    'avg_zcr': avg_zcr,
                    'avg_rms': avg_rms,
                    'spectral_rolloff': spectral_rolloff,
                    'mfcc_variance': float(np.mean(mfcc_var)) if len(mfcc_var) > 0 else 0.0
                }
            }

        except Exception as e:
            self.logger.error(f"Error in content classification: {e}")
            return {'content_type': 'unknown', 'confidence': 0.0}
    
    def compute_chunk_similarity(self, features1: Dict, features2: Dict, content_info1: Dict = None, content_info2: Dict = None) -> Dict[str, float]:
        """
        Compute similarity between two feature sets with content-aware weighting

        Args:
            features1: Features from first audio chunk
            features2: Features from second audio chunk
            content_info1: Content classification for first chunk
            content_info2: Content classification for second chunk

        Returns:
            Dictionary of similarity scores including content-aware overall score
        """
        similarities = {}

        if not features1 or not features2:
            return {'overall': 0.0}

        try:
            # MFCC similarity (weighted heavily as most reliable)
            if 'mfcc' in features1 and 'mfcc' in features2:
                mfcc1_flat = features1['mfcc'].flatten()
                mfcc2_flat = features2['mfcc'].flatten()

                # Ensure same length
                min_len = min(len(mfcc1_flat), len(mfcc2_flat))
                mfcc1_flat = mfcc1_flat[:min_len]
                mfcc2_flat = mfcc2_flat[:min_len]

                mfcc_corr = np.corrcoef(mfcc1_flat, mfcc2_flat)[0, 1]
                similarities['mfcc'] = mfcc_corr if not np.isnan(mfcc_corr) else 0.0

            # Onset similarity
            if 'onsets' in features1 and 'onsets' in features2:
                onsets1 = features1['onsets']
                onsets2 = features2['onsets']

                if len(onsets1) > 0 and len(onsets2) > 0:
                    # Compare onset timing patterns
                    onset_sim = 1.0 / (1.0 + abs(len(onsets1) - len(onsets2)))
                    similarities['onsets'] = onset_sim
                else:
                    similarities['onsets'] = 0.0

            # Energy similarity
            if 'rms' in features1 and 'rms' in features2:
                rms1_flat = features1['rms'].flatten()
                rms2_flat = features2['rms'].flatten()

                min_len = min(len(rms1_flat), len(rms2_flat))
                rms1_flat = rms1_flat[:min_len]
                rms2_flat = rms2_flat[:min_len]

                rms_corr = np.corrcoef(rms1_flat, rms2_flat)[0, 1]
                similarities['rms'] = rms_corr if not np.isnan(rms_corr) else 0.0

            # Content-aware weighted overall similarity
            weights = self._get_adaptive_weights(content_info1, content_info2)
            overall = 0.0
            total_weight = 0.0

            for feature, weight in weights.items():
                if feature in similarities:
                    overall += similarities[feature] * weight
                    total_weight += weight

            similarities['overall'] = overall / total_weight if total_weight > 0 else 0.0
            similarities['content_adaptive'] = True

            return similarities

        except Exception as e:
            self.logger.error(f"Error computing similarity: {e}")
            return {'overall': 0.0}

    def _get_adaptive_weights(self, content_info1: Dict = None, content_info2: Dict = None) -> Dict[str, float]:
        """
        Get adaptive feature weights based on content classification

        Returns:
            Dictionary of feature weights optimized for detected content type
        """
        # Default weights
        default_weights = {'mfcc': 0.6, 'onsets': 0.25, 'rms': 0.15}

        if not content_info1 or not content_info2:
            return default_weights

        # Get processing hints from both chunks
        hints1 = content_info1.get('processing_hints', {})
        hints2 = content_info2.get('processing_hints', {})

        # Average the weights from both chunks' hints
        weights = default_weights.copy()

        # Apply MFCC weight adjustments
        mfcc_weight1 = hints1.get('mfcc_weight', 1.0)
        mfcc_weight2 = hints2.get('mfcc_weight', 1.0)
        weights['mfcc'] *= (mfcc_weight1 + mfcc_weight2) / 2

        # Apply onset weight adjustments
        onset_weight1 = hints1.get('onset_weight', 1.0)
        onset_weight2 = hints2.get('onset_weight', 1.0)
        weights['onsets'] *= (onset_weight1 + onset_weight2) / 2

        # Apply spectral weight adjustments (affects RMS)
        spectral_weight1 = hints1.get('spectral_weight', 1.0)
        spectral_weight2 = hints2.get('spectral_weight', 1.0)
        weights['rms'] *= (spectral_weight1 + spectral_weight2) / 2

        # Normalize weights to sum to original total
        total_weight = sum(weights.values())
        original_total = sum(default_weights.values())

        if total_weight > 0:
            scale_factor = original_total / total_weight
            weights = {k: v * scale_factor for k, v in weights.items()}

        return weights

    def ensemble_confidence_scoring(self, chunk_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhanced ensemble confidence scoring that considers multiple factors

        Args:
            chunk_result: Result from chunk analysis

        Returns:
            Enhanced result with ensemble confidence score
        """
        try:
            # Get basic measurements
            offset_detection = chunk_result.get('offset_detection', {})
            similarities = chunk_result.get('similarities', {})
            master_content = chunk_result.get('master_content', {})
            dub_content = chunk_result.get('dub_content', {})

            base_confidence = offset_detection.get('confidence', 0.0)
            correlation_peak = offset_detection.get('correlation_peak', 0.0)
            similarity_score = similarities.get('overall', 0.0)

            # Content-based confidence adjustments
            content_confidence_factor = 1.0
            if master_content and dub_content:
                master_type = master_content.get('content_type', 'unknown')
                dub_type = dub_content.get('content_type', 'unknown')

                # Penalty for mismatched content types
                if master_type != dub_type and master_type != 'unknown' and dub_type != 'unknown':
                    content_confidence_factor *= 0.8

                # Boost for high-quality content types
                if master_type == 'dialogue':
                    content_confidence_factor *= 1.2
                elif master_type == 'music':
                    content_confidence_factor *= 1.1
                elif master_type == 'silence':
                    content_confidence_factor *= 0.3  # Very low confidence for silence

            # Signal quality factors
            signal_quality_factor = 1.0

            # Boost confidence if both correlation and similarity are high
            if base_confidence > 0.5 and similarity_score > 0.5:
                signal_quality_factor *= 1.3

            # Penalty for very low similarity even with high correlation
            if similarity_score < 0.2 and base_confidence > 0.3:
                signal_quality_factor *= 0.7

            # Boost for very high correlation peaks
            if abs(correlation_peak) > 0.8:
                signal_quality_factor *= 1.1

            # Temporal consistency factor (for sequential chunks)
            temporal_factor = 1.0
            chunk_index = chunk_result.get('chunk_index', 0)

            # This would require access to previous chunks - placeholder for now
            # In a full implementation, you'd check offset consistency with neighbors

            # Calculate ensemble confidence
            ensemble_confidence = base_confidence * content_confidence_factor * signal_quality_factor * temporal_factor

            # Clamp to valid range
            ensemble_confidence = min(max(ensemble_confidence, 0.0), 1.0)

            # Enhanced quality assessment based on ensemble confidence
            if ensemble_confidence > 0.8:
                quality = 'Excellent'
            elif ensemble_confidence > 0.6:
                quality = 'Good'
            elif ensemble_confidence > 0.4:
                quality = 'Fair'
            else:
                quality = 'Poor'

            # Create enhanced result
            enhanced_result = chunk_result.copy()
            enhanced_result['ensemble_confidence'] = ensemble_confidence
            enhanced_result['confidence_factors'] = {
                'base_confidence': base_confidence,
                'content_factor': content_confidence_factor,
                'signal_quality_factor': signal_quality_factor,
                'temporal_factor': temporal_factor
            }
            enhanced_result['quality'] = quality

            return enhanced_result

        except Exception as e:
            self.logger.error(f"Error in ensemble confidence scoring: {e}")
            return chunk_result

    def detect_offset_cross_correlation(self, audio1_path: str, audio2_path: str,
                                      start_time: float = 0.0, duration: float = 30.0) -> Dict[str, Any]:
        """Detect offset using cross-correlation on a specific segment"""
        try:
            # Load audio segments with soundfile (pre-resampled by ffmpeg extract)
            info1 = sf.info(audio1_path)
            sr1 = self.sample_rate  # Use resampled rate, not metadata rate
            s1 = int(start_time * sr1)
            n1 = int(duration * sr1)
            y1, _ = sf.read(audio1_path, start=s1, frames=n1, dtype='float32', always_2d=False)
            if y1.ndim > 1:
                y1 = y1.mean(axis=1)

            info2 = sf.info(audio2_path)
            sr2 = self.sample_rate  # Use resampled rate, not metadata rate
            s2 = int(start_time * sr2)
            n2 = int(duration * sr2)
            y2, _ = sf.read(audio2_path, start=s2, frames=n2, dtype='float32', always_2d=False)
            if y2.ndim > 1:
                y2 = y2.mean(axis=1)
            
            if len(y1) == 0 or len(y2) == 0:
                return {'offset_seconds': 0.0, 'confidence': 0.0}
            
            # Ensure same length
            min_len = min(len(y1), len(y2))
            y1 = y1[:min_len]
            y2 = y2[:min_len]
            # Cross-correlation (GPU-accelerated via PyTorch when available)
            max_corr_idx = None
            max_corr_val = None
            used_gpu = False
            if self.gpu_available:
                try:
                    import torch
                    import torch.nn.functional as F
                    with torch.no_grad():
                        x = torch.from_numpy(y1.astype(np.float32)).to(self.device).view(1, 1, -1)
                        w = torch.from_numpy(y2.astype(np.float32)[::-1].copy()).to(self.device).view(1, 1, -1)
                        # full correlation via conv1d with padding
                        pad = w.shape[-1] - 1
                        corr = F.conv1d(x, w, padding=pad).view(-1)
                        max_corr_idx_t = torch.argmax(corr)
                        max_corr_idx = int(max_corr_idx_t.item())
                        max_corr_val = float(corr[max_corr_idx_t].item())
                        used_gpu = self.device.startswith('cuda')
                except Exception as e:
                    self.logger.debug(f"GPU cross-correlation fallback to numpy due to: {e}")
                    max_corr_idx = None
                    used_gpu = False
            if max_corr_idx is None:
                # CPU fallback
                correlation = np.correlate(y1, y2, mode='full')
                max_corr_idx = int(np.argmax(correlation))
                max_corr_val = float(correlation[max_corr_idx])
                used_gpu = False

            # For np.correlate(y1, y2, mode='full'), zero-lag index is len(y2) - 1
            # Use y2 (dub) as the reference to convert index -> lag
            offset_samples = max_corr_idx - (len(y2) - 1)
            # Use the resampled rate (22050 Hz) not the original file rate
            # Files were resampled by FFmpeg extraction to self.sample_rate
            offset_seconds = offset_samples / float(self.sample_rate)

            # Improved confidence calculation using signal-to-noise ratio approach
            if max_corr_idx is not None and used_gpu:
                # For GPU path, get full correlation array
                import torch
                with torch.no_grad():
                    x = torch.from_numpy(y1.astype(np.float32)).to(self.device).view(1, 1, -1)
                    w = torch.from_numpy(y2.astype(np.float32)[::-1].copy()).to(self.device).view(1, 1, -1)
                    pad = w.shape[-1] - 1
                    corr_full = torch.nn.functional.conv1d(x, w, padding=pad).view(-1).detach().cpu().numpy()
            else:
                # For CPU path, use existing correlation
                corr_full = np.correlate(y1, y2, mode='full')

            # Calculate confidence using peak-to-average ratio
            corr_abs = np.abs(corr_full)
            peak_val = corr_abs[max_corr_idx] if max_corr_idx < len(corr_abs) else max_corr_val
            mean_corr = np.mean(corr_abs)
            std_corr = np.std(corr_abs)

            # SNR-based confidence calculation
            snr = (peak_val - mean_corr) / (std_corr + 1e-8)
            confidence = min(max(snr / 8, 0.0), 1.0)  # Normalize to 0-1 range
            
            return {
                'offset_seconds': float(offset_seconds),
                'offset_samples': int(offset_samples),
                'confidence': float(confidence),
                'correlation_peak': float(max_corr_val),
                'gpu_used': bool(used_gpu)
            }
            
        except Exception as e:
            self.logger.error(f"Error in cross-correlation: {e}")
            return {'offset_seconds': 0.0, 'confidence': 0.0}
    
    def analyze_sync_chunked(self, master_path: str, dub_path: str) -> Dict[str, Any]:
        """Enhanced multi-pass chunked sync analysis method"""
        self.logger.info(f"Starting intelligent multi-pass sync analysis:")
        self.logger.info(f"  Master: {os.path.basename(master_path)}")
        self.logger.info(f"  Dub: {os.path.basename(dub_path)}")
        self.logger.info(f"  Multi-pass enabled: {self.enable_multi_pass}")

        try:
            # Extract audio from videos
            master_audio = self.extract_audio_from_video(master_path)
            dub_audio = self.extract_audio_from_video(dub_path)

            if not master_audio or not dub_audio:
                return {'error': 'Failed to extract audio from video files'}

            # Get durations
            master_duration = self.get_audio_duration(master_audio)
            dub_duration = self.get_audio_duration(dub_audio)

            self.logger.info(f"Durations - Master: {master_duration:.1f}s, Dub: {dub_duration:.1f}s")

            # PASS 1: Coarse analysis with standard chunking
            self.logger.info("🔍 PASS 1: Coarse drift detection")
            pass1_results = self._analyze_pass1_coarse(master_audio, dub_audio, master_duration, dub_duration)

            # Determine if Pass 2 refinement is needed
            final_result = pass1_results
            if self.enable_multi_pass and self._should_perform_pass2(pass1_results):
                self.logger.info("🎯 PASS 2: Targeted refinement triggered")
                pass2_results = self._analyze_pass2_targeted(
                    master_audio, dub_audio, master_duration, dub_duration, pass1_results
                )
                # Combine results from both passes
                final_result = self._combine_multipass_results(pass1_results, pass2_results)
                final_result['multi_pass_analysis'] = True
            else:
                final_result['multi_pass_analysis'] = False

            # Clean up temp files
            self._cleanup_temp_files([master_audio, dub_audio])

            return final_result

        except Exception as e:
            self.logger.error(f"Error in multi-pass analysis: {e}")
            return {'error': str(e)}

    def _analyze_pass1_coarse(self, master_audio: str, dub_audio: str, master_duration: float, dub_duration: float) -> Dict[str, Any]:
        """
        Pass 1: Coarse analysis using standard chunking with content classification
        """
        # Create standard chunks for initial analysis
        chunks = self.create_audio_chunks(master_audio, min(master_duration, dub_duration))
        self.logger.info(f"Pass 1: Analyzing {len(chunks)} coarse chunks")

        chunk_results = []
        try:
            from tqdm import tqdm
            iterator = tqdm(enumerate(chunks), total=len(chunks), desc="Pass 1 chunks", unit="chunk")
        except Exception:
            iterator = enumerate(chunks)

        for i, (start, end) in iterator:
            # Extract features from both files
            master_features = self.extract_chunk_features(master_audio, start, end)
            dub_features = self.extract_chunk_features(dub_audio, start, end)

            # Classify content type for adaptive processing
            master_content = self.classify_audio_content(master_features)
            dub_content = self.classify_audio_content(dub_features)

            # Skip silence regions (but keep them in results for timeline)
            if (master_content.get('content_type') == 'silence' and
                dub_content.get('content_type') == 'silence'):
                chunk_result = {
                    'chunk_index': i,
                    'start_time': start,
                    'end_time': end,
                    'duration': end - start,
                    'content_type': 'silence',
                    'similarities': {'overall': 0.0, 'skipped': True},
                    'offset_detection': {'offset_seconds': 0.0, 'confidence': 0.0},
                    'quality': 'Skipped'
                }
                chunk_results.append(chunk_result)
                continue

            # Compute content-aware similarity
            similarities = self.compute_chunk_similarity(
                master_features, dub_features, master_content, dub_content
            )

            # Detect offset for this chunk
            offset_result = self.detect_offset_cross_correlation(
                master_audio, dub_audio, start, end - start)

            chunk_result = {
                'chunk_index': i,
                'start_time': start,
                'end_time': end,
                'duration': end - start,
                'master_content': master_content,
                'dub_content': dub_content,
                'similarities': similarities,
                'offset_detection': offset_result,
                'quality': self._assess_chunk_quality(similarities, offset_result),
                'pass_number': 1
            }

            # Apply ensemble confidence scoring
            enhanced_chunk_result = self.ensemble_confidence_scoring(chunk_result)
            chunk_results.append(enhanced_chunk_result)

        # Aggregate results from Pass 1
        pass1_result = self._aggregate_chunk_results(chunk_results, master_duration, dub_duration)
        pass1_result['pass_1_chunks'] = len(chunks)
        pass1_result['pass_1_results'] = chunk_results

        return pass1_result

    def _should_perform_pass2(self, pass1_results: Dict[str, Any]) -> bool:
        """
        Determine if Pass 2 targeted refinement is needed based on Pass 1 results
        """
        try:
            # Check if drift was detected
            drift_analysis = pass1_results.get('drift_analysis', {})
            has_significant_drift = drift_analysis.get('has_drift', False)

            # Check if there are low confidence regions
            chunk_results = pass1_results.get('pass_1_results', [])
            low_confidence_chunks = [
                chunk for chunk in chunk_results
                if chunk.get('offset_detection', {}).get('confidence', 0) < self.gap_analysis_threshold
            ]

            # Check if there are gaps between reliable chunks
            reliable_chunks = [
                chunk for chunk in chunk_results
                if chunk.get('quality', 'Poor') in ['Excellent', 'Good']
            ]

            has_gaps = len(reliable_chunks) < len(chunk_results) * 0.7  # <70% reliable

            # Decision criteria
            trigger_pass2 = (
                has_significant_drift or
                len(low_confidence_chunks) > len(chunk_results) * 0.3 or  # >30% low confidence
                has_gaps
            )

            if trigger_pass2:
                self.logger.info(f"Pass 2 triggered: drift={has_significant_drift}, "
                               f"low_conf={len(low_confidence_chunks)}, gaps={has_gaps}")

            return trigger_pass2

        except Exception as e:
            self.logger.error(f"Error determining Pass 2 need: {e}")
            return False

    def _analyze_pass2_targeted(self, master_audio: str, dub_audio: str, master_duration: float,
                               dub_duration: float, pass1_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pass 2: Targeted refinement in problematic regions identified in Pass 1
        """
        # Identify regions needing refinement
        target_regions = self._identify_refinement_regions(pass1_results)

        if not target_regions:
            self.logger.info("No regions identified for Pass 2 refinement")
            return pass1_results

        self.logger.info(f"Pass 2: Refining {len(target_regions)} targeted regions")

        pass2_chunks = []
        for region in target_regions:
            # Create smaller chunks within each target region
            region_chunks = self._create_refinement_chunks(
                region['start'], region['end'], self.refinement_chunk_size
            )
            pass2_chunks.extend(region_chunks)

        self.logger.info(f"Pass 2: Analyzing {len(pass2_chunks)} refinement chunks")

        chunk_results = []
        try:
            from tqdm import tqdm
            iterator = tqdm(enumerate(pass2_chunks), total=len(pass2_chunks), desc="Pass 2 chunks", unit="chunk")
        except Exception:
            iterator = enumerate(pass2_chunks)

        for i, (start, end) in iterator:
            # Extract features from both files
            master_features = self.extract_chunk_features(master_audio, start, end)
            dub_features = self.extract_chunk_features(dub_audio, start, end)

            # Classify content type
            master_content = self.classify_audio_content(master_features)
            dub_content = self.classify_audio_content(dub_features)

            # Compute content-aware similarity
            similarities = self.compute_chunk_similarity(
                master_features, dub_features, master_content, dub_content
            )

            # Detect offset for this chunk
            offset_result = self.detect_offset_cross_correlation(
                master_audio, dub_audio, start, end - start)

            chunk_result = {
                'chunk_index': i,
                'start_time': start,
                'end_time': end,
                'duration': end - start,
                'master_content': master_content,
                'dub_content': dub_content,
                'similarities': similarities,
                'offset_detection': offset_result,
                'quality': self._assess_chunk_quality(similarities, offset_result),
                'pass_number': 2,
                'refinement_chunk': True
            }

            # Apply ensemble confidence scoring
            enhanced_chunk_result = self.ensemble_confidence_scoring(chunk_result)
            chunk_results.append(enhanced_chunk_result)

        # Aggregate results from Pass 2
        pass2_result = self._aggregate_chunk_results(chunk_results, master_duration, dub_duration)
        pass2_result['pass_2_chunks'] = len(pass2_chunks)
        pass2_result['pass_2_results'] = chunk_results
        pass2_result['target_regions'] = target_regions

        return pass2_result

    def _identify_refinement_regions(self, pass1_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Identify regions that need refinement based on Pass 1 results
        """
        try:
            chunk_results = pass1_results.get('pass_1_results', [])
            regions = []

            # Find low confidence chunks and gaps
            for i, chunk in enumerate(chunk_results):
                confidence = chunk.get('offset_detection', {}).get('confidence', 0)
                quality = chunk.get('quality', 'Poor')

                # Flag low confidence or poor quality chunks for refinement
                if confidence < self.gap_analysis_threshold or quality == 'Poor':
                    # Expand region to include neighboring chunks for context
                    start_idx = max(0, i - 1)
                    end_idx = min(len(chunk_results) - 1, i + 1)

                    region_start = chunk_results[start_idx]['start_time']
                    region_end = chunk_results[end_idx]['end_time']

                    regions.append({
                        'start': region_start,
                        'end': region_end,
                        'reason': f'Low confidence/quality at chunk {i}',
                        'original_chunk_index': i,
                        'confidence': confidence,
                        'quality': quality
                    })

            # Merge overlapping regions
            merged_regions = self._merge_overlapping_regions(regions)

            return merged_regions

        except Exception as e:
            self.logger.error(f"Error identifying refinement regions: {e}")
            return []

    def _create_refinement_chunks(self, start_time: float, end_time: float, chunk_size: float) -> List[Tuple[float, float]]:
        """
        Create smaller refinement chunks within a target region
        """
        chunks = []
        duration = end_time - start_time

        if duration <= chunk_size:
            # If region is smaller than chunk size, use the entire region
            chunks.append((start_time, end_time))
        else:
            # Create overlapping chunks within the region
            overlap = chunk_size * 0.5  # 50% overlap for refinement
            current_start = start_time

            while current_start < end_time:
                current_end = min(current_start + chunk_size, end_time)
                chunks.append((current_start, current_end))

                if current_end >= end_time:
                    break
                current_start += (chunk_size - overlap)

        return chunks

    def _merge_overlapping_regions(self, regions: List[Dict]) -> List[Dict]:
        """
        Merge overlapping refinement regions
        """
        if not regions:
            return []

        # Sort regions by start time
        sorted_regions = sorted(regions, key=lambda x: x['start'])
        merged = [sorted_regions[0]]

        for current in sorted_regions[1:]:
            last_merged = merged[-1]

            # If regions overlap or are very close, merge them
            if current['start'] <= last_merged['end'] + 5:  # 5 second tolerance
                last_merged['end'] = max(last_merged['end'], current['end'])
                last_merged['reason'] += f" + {current['reason']}"
            else:
                merged.append(current)

        return merged

    def _combine_multipass_results(self, pass1_results: Dict[str, Any], pass2_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Combine results from Pass 1 and Pass 2 analysis
        """
        try:
            # Start with Pass 1 as base
            combined_result = pass1_results.copy()

            # Integrate Pass 2 refinement data
            pass1_chunks = pass1_results.get('pass_1_results', [])
            pass2_chunks = pass2_results.get('pass_2_results', [])

            # Create combined timeline with both coarse and fine-grained data
            all_chunks = pass1_chunks + pass2_chunks

            # Update drift analysis with more refined data
            refined_drift_analysis = self._analyze_sync_drift(
                [chunk for chunk in all_chunks if chunk.get('quality', 'Poor') != 'Poor'],
                all_chunks
            )

            combined_result.update({
                'drift_analysis': refined_drift_analysis,
                'timeline': refined_drift_analysis.get('timeline', []),
                'total_chunks_analyzed': len(all_chunks),
                'pass_1_chunks': pass1_results.get('pass_1_chunks', 0),
                'pass_2_chunks': pass2_results.get('pass_2_chunks', 0),
                'refinement_regions': pass2_results.get('target_regions', []),
                'combined_chunks': all_chunks
            })

            # Recalculate overall metrics with combined data
            acceptable_chunks = [
                chunk for chunk in all_chunks
                if chunk.get('quality', 'Poor') in ['Excellent', 'Good', 'Fair']
            ]

            if acceptable_chunks:
                # Recalculate weighted average offset
                total_weighted_offset = 0.0
                total_weights = 0.0

                for chunk in acceptable_chunks:
                    offset = chunk['offset_detection'].get('offset_seconds', 0)
                    confidence = chunk['offset_detection'].get('confidence', 0)

                    if confidence > 0:
                        total_weighted_offset += offset * confidence
                        total_weights += confidence

                if total_weights > 0:
                    final_offset = total_weighted_offset / total_weights
                    combined_result['offset_seconds'] = float(final_offset)
                    combined_result['offset_milliseconds'] = float(final_offset * 1000)

                # Update confidence with refined data
                confidences = [chunk['offset_detection'].get('confidence', 0) for chunk in acceptable_chunks]
                combined_result['confidence'] = float(np.mean(confidences)) if confidences else 0.0

                combined_result['chunks_reliable'] = len(acceptable_chunks)

            self.logger.info(f"Combined analysis: {len(pass1_chunks)} coarse + {len(pass2_chunks)} refinement chunks")

            return combined_result

        except Exception as e:
            self.logger.error(f"Error combining multipass results: {e}")
            return pass1_results

    def _assess_chunk_quality(self, similarities: Dict, offset_result: Dict) -> str:
        """Assess the quality of a chunk analysis"""
        overall_sim = similarities.get('overall', 0)
        confidence = offset_result.get('confidence', 0)

        # More realistic thresholds based on real-world performance
        if (overall_sim > 0.6 and confidence > 0.4) or (overall_sim > 0.7) or (confidence > 0.6):
            return 'Excellent'
        elif (overall_sim > 0.4 and confidence > 0.2) or (overall_sim > 0.5) or (confidence > 0.3):
            return 'Good'
        elif (overall_sim > 0.2 and confidence > 0.1) or (overall_sim > 0.3) or (confidence > 0.15):
            return 'Fair'
        else:
            return 'Poor'
    
    def _aggregate_chunk_results(self, chunk_results: List[Dict], 
                               master_duration: float, dub_duration: float) -> Dict[str, Any]:
        """Aggregate results from all chunks into final recommendation"""
        
        # Accept more chunks with lower thresholds for continuous monitoring
        # Include "Poor" quality chunks if they have reasonable confidence
        acceptable_chunks = []
        for chunk in chunk_results:
            quality = chunk.get('quality', 'Poor')
            confidence = chunk.get('offset_detection', {}).get('confidence', 0)
            similarity = chunk.get('similarities', {}).get('overall', 0)

            # Even more lenient acceptance criteria - focus on any meaningful signal
            if (quality in ['Excellent', 'Good', 'Fair'] or
                (quality == 'Poor' and (confidence > 0.01 or similarity > 0.1))):  # Accept if any signal exists
                acceptable_chunks.append(chunk)
        
        if not acceptable_chunks:
            # Fallback: choose best-confidence chunk even if "Poor" to avoid 0-offset
            best_chunk = None
            try:
                best_chunk = max(
                    chunk_results,
                    key=lambda c: float(c.get('offset_detection', {}).get('confidence', 0.0))
                ) if chunk_results else None
            except Exception:
                best_chunk = None
            if best_chunk and best_chunk.get('offset_detection'):
                od = best_chunk['offset_detection']
                offset = float(od.get('offset_seconds') or 0.0)
                confidence = float(od.get('confidence') or 0.0)
                return {
                    'analysis_date': datetime.now().isoformat(),
                    'sync_status': 'Low-Quality Estimate',
                    'confidence': confidence,
                    'offset_seconds': offset,
                    'quality': 'Poor',
                    'chunks_analyzed': len(chunk_results),
                    'chunks_reliable': 0,
                    'recommendation': 'Low-quality estimate used from best chunk; verify manually',
                    'master_duration': master_duration,
                    'dub_duration': dub_duration,
                    'low_quality_fallback': True,
                    'chunk_details': chunk_results
                }
            # Absolute fallback
            return {
                'analysis_date': datetime.now().isoformat(),
                'sync_status': 'Analysis Failed',
                'confidence': 0.0,
                'offset_seconds': 0.0,
                'quality': 'Poor',
                'chunks_analyzed': len(chunk_results),
                'chunks_reliable': 0,
                'recommendation': 'Manual analysis required - automated detection failed',
                'master_duration': master_duration,
                'dub_duration': dub_duration,
                'chunk_details': chunk_results
            }
        
        # Calculate weighted average offset (weight by confidence)
        total_weighted_offset = 0.0
        total_weights = 0.0
        
        for chunk in acceptable_chunks:
            offset = chunk['offset_detection'].get('offset_seconds', 0)
            confidence = chunk['offset_detection'].get('confidence', 0)
            
            if confidence > 0:
                total_weighted_offset += offset * confidence
                total_weights += confidence
        
        final_offset = total_weighted_offset / total_weights if total_weights > 0 else 0.0
        
        # Calculate sync drift metrics
        chunk_offsets = [chunk['offset_detection'].get('offset_seconds', 0) for chunk in acceptable_chunks]
        drift_analysis = self._analyze_sync_drift(acceptable_chunks, chunk_results)
        
        # Calculate overall confidence
        confidences = [chunk['offset_detection'].get('confidence', 0) for chunk in acceptable_chunks]
        avg_confidence = np.mean(confidences) if confidences else 0.0
        
        # Calculate overall similarity
        similarities = [chunk['similarities'].get('overall', 0) for chunk in acceptable_chunks]
        avg_similarity = np.mean(similarities) if similarities else 0.0
        
        # Determine sync status
        if abs(final_offset) < 0.01 and avg_similarity > 0.8:
            sync_status = 'Perfect Sync'
            recommendation = 'Files are perfectly synchronized'
        elif abs(final_offset) < 0.04:  # Under 40ms
            sync_status = 'Excellent Sync'
            recommendation = 'Sync is within broadcast standards'
        elif abs(final_offset) < 0.1:  # Under 100ms
            sync_status = 'Good Sync'
            recommendation = f'Minor sync offset of {final_offset*1000:.1f}ms detected'
        elif abs(final_offset) < 1.0:  # Under 1 second
            sync_status = 'Sync Issues Detected'
            recommendation = f'Significant sync offset of {final_offset:.3f}s requires correction'
        else:
            sync_status = 'Major Sync Issues'
            recommendation = f'Major sync offset of {final_offset:.3f}s requires immediate correction'
        
        # Assess overall quality
        if avg_confidence > 0.8 and avg_similarity > 0.8:
            overall_quality = 'Excellent'
        elif avg_confidence > 0.6 and avg_similarity > 0.6:
            overall_quality = 'Good'
        elif avg_confidence > 0.4 and avg_similarity > 0.4:
            overall_quality = 'Fair'
        else:
            overall_quality = 'Poor'
        
        return {
            'analysis_date': datetime.now().isoformat(),
            'sync_status': sync_status,
            'confidence': float(avg_confidence),
            'offset_seconds': float(final_offset),
            'offset_milliseconds': float(final_offset * 1000),
            'similarity_score': float(avg_similarity),
            'quality': overall_quality,
            'chunks_analyzed': len(chunk_results),
            'chunks_reliable': len(acceptable_chunks),
            'recommendation': recommendation,
            'master_duration': master_duration,
            'dub_duration': dub_duration,
            'duration_difference': dub_duration - master_duration,
            'drift_analysis': drift_analysis,
            'timeline': drift_analysis.get('timeline', []),
            'localized_events': drift_analysis.get('localized_events', []),
            'gpu_used': self.gpu_available,
            'chunk_details': chunk_results
        }

    @staticmethod
    def _weighted_median(values: List[float], weights: Optional[List[float]] = None) -> float:
        """Compute a weighted median with graceful fallbacks for degenerate input."""
        if not values:
            return 0.0

        data = np.asarray(values, dtype=float)
        if weights is None:
            return float(np.median(data))

        weights_arr = np.asarray(weights, dtype=float)
        if weights_arr.shape != data.shape:
            weights_arr = np.resize(weights_arr, data.shape)

        mask = np.isfinite(data) & np.isfinite(weights_arr)
        if not np.any(mask):
            return float(np.median(data))

        data = data[mask]
        weights_arr = np.clip(weights_arr[mask], 1e-6, None)

        sorter = np.argsort(data)
        data_sorted = data[sorter]
        weights_sorted = weights_arr[sorter]
        cumulative = np.cumsum(weights_sorted)
        cutoff = cumulative[-1] / 2.0
        idx = int(np.searchsorted(cumulative, cutoff, side='left'))
        idx = min(idx, len(data_sorted) - 1)
        return float(data_sorted[idx])

    def _detect_localized_offset_events(self, timeline: List[Dict[str, Any]],
                                         baseline_offset: float) -> List[Dict[str, Any]]:
        """Identify clusters of offsets that deviate from baseline, signalling drift/extra scenes."""
        if not timeline:
            return []

        filtered = [
            entry for entry in timeline
            if abs(entry.get('offset_seconds', 0.0)) <= self.localized_offset_max_seconds
        ]

        if len(filtered) < self.localized_min_segments:
            return []

        filtered.sort(key=lambda x: x.get('start_time', 0.0))

        clusters: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None

        for entry in filtered:
            offset = float(entry.get('offset_seconds', 0.0))
            delta = offset - baseline_offset
            confidence = float(entry.get('confidence', 0.0))
            weight = max(confidence, 1e-3)

            if abs(delta) < self.localized_min_delta_seconds:
                if current:
                    clusters.append(current)
                    current = None
                continue

            sign = 1 if delta > 0 else -1
            start_time = float(entry.get('start_time', 0.0))
            end_time = float(entry.get('end_time', start_time))

            if (current and sign == current['sign'] and
                    start_time <= current['end_time'] + self.localized_max_gap_seconds):
                current['segments'].append((entry, weight, delta))
                current['end_time'] = max(current['end_time'], end_time)
                current['total_weight'] += weight
                current['total_confidence'] += confidence
            else:
                if current:
                    clusters.append(current)
                current = {
                    'sign': sign,
                    'start_time': start_time,
                    'end_time': end_time,
                    'segments': [(entry, weight, delta)],
                    'total_weight': weight,
                    'total_confidence': confidence
                }

        if current:
            clusters.append(current)

        localized_events: List[Dict[str, Any]] = []
        for cluster in clusters:
            segments = cluster['segments']
            if len(segments) < self.localized_min_segments:
                continue

            duration = cluster['end_time'] - cluster['start_time']
            if duration < self.localized_min_duration and cluster['total_weight'] < 0.3:
                continue

            weights = np.array([w for _, w, _ in segments], dtype=float)
            offsets = np.array([seg['offset_seconds'] for seg, _, _ in segments], dtype=float)
            avg_offset = float(np.average(offsets, weights=weights)) if weights.sum() else float(np.mean(offsets))
            avg_delta = avg_offset - baseline_offset

            avg_conf = cluster['total_confidence'] / len(segments)
            classification = 'EXTRA_CONTENT' if cluster['sign'] > 0 else 'MISSING_CONTENT'
            trend_slope = 0.0
            if len(segments) >= 3:
                times = np.array([seg['start_time'] for seg, _, _ in segments], dtype=float)
                try:
                    trend_slope = float(np.polyfit(times, offsets, 1)[0])
                except Exception:
                    trend_slope = 0.0
            if abs(trend_slope) >= 0.01:
                classification = 'DRIFT'

            localized_events.append({
                'start_time': float(cluster['start_time']),
                'end_time': float(cluster['end_time']),
                'duration_seconds': float(duration),
                'avg_offset_seconds': avg_offset,
                'delta_from_baseline': float(avg_delta),
                'segment_count': len(segments),
                'total_weight': float(cluster['total_weight']),
                'avg_confidence': float(avg_conf),
                'classification': classification,
                'trend_slope': float(trend_slope)
            })

        localized_events.sort(key=lambda e: abs(e['delta_from_baseline']), reverse=True)
        return localized_events

    def _analyze_sync_drift(self, acceptable_chunks: List[Dict], all_chunks: List[Dict]) -> Dict[str, Any]:
        """Analyze sync drift across time using chunk data"""
        if not acceptable_chunks:
            return {
                'has_drift': False,
                'drift_magnitude': 0.0,
                'timeline': [],
                'drift_summary': 'No reliable chunks for drift analysis',
                'baseline_offset': 0.0,
                'localized_events': []
            }

        # Create timeline of sync offsets
        timeline = []
        chunk_offsets = []
        
        # Process all chunks to create complete timeline
        for chunk in all_chunks:
            chunk_data = {
                'start_time': chunk.get('start_time', 0),
                'end_time': chunk.get('end_time', 0),
                'offset_seconds': 0.0,
                'confidence': 0.0,
                'reliable': False,
                'quality': chunk.get('quality', 'Poor')
            }
            
            if 'offset_detection' in chunk and chunk['offset_detection']:
                offset = chunk['offset_detection'].get('offset_seconds', 0)
                confidence = chunk['offset_detection'].get('confidence', 0)
                chunk_data.update({
                    'offset_seconds': offset,
                    'confidence': confidence,
                    'reliable': chunk in acceptable_chunks
                })
                
                if chunk in acceptable_chunks:
                    chunk_offsets.append(offset)
            
            timeline.append(chunk_data)
        
        # Sort timeline by start time
        timeline.sort(key=lambda x: x['start_time'])
        
        # Determine baseline offset preference: use reliable chunks when available
        if chunk_offsets:
            baseline_offset = float(np.median(chunk_offsets))
        else:
            timeline_offsets = [entry['offset_seconds'] for entry in timeline]
            timeline_weights = [max(entry.get('confidence', 0.0), 1e-3) for entry in timeline]
            baseline_offset = self._weighted_median(timeline_offsets, timeline_weights)

        # Calculate drift metrics
        if len(chunk_offsets) < 2:
            drift_magnitude = 0.0
            has_significant_drift = False
        else:
            drift_magnitude = max(chunk_offsets) - min(chunk_offsets)
            has_significant_drift = drift_magnitude > 0.1  # >100ms drift

        # Analyze drift patterns
        drift_regions = []
        if has_significant_drift:
            # Find regions with significantly different offsets
            median_offset = np.median(chunk_offsets) if chunk_offsets else 0
            for entry in timeline:
                if entry['reliable'] and abs(entry['offset_seconds'] - median_offset) > 0.05:
                    drift_regions.append({
                        'time_range': f"{entry['start_time']:.1f}s-{entry['end_time']:.1f}s",
                        'offset_seconds': entry['offset_seconds'],
                        'deviation_from_median': entry['offset_seconds'] - median_offset
                    })

        localized_events = self._detect_localized_offset_events(timeline, baseline_offset)

        # Generate summary
        if not has_significant_drift:
            drift_summary = f"Consistent sync across file (drift: {drift_magnitude*1000:.1f}ms)"
        else:
            drift_summary = f"Significant sync drift detected: {drift_magnitude:.3f}s variation ({len(drift_regions)} problem regions)"
        if localized_events:
            top_event = localized_events[0]
            drift_summary += (
                f" • Localized {top_event['classification'].lower().replace('_', ' ')} "
                f"around {top_event['start_time']:.1f}s→{top_event['end_time']:.1f}s "
                f"(Δ {top_event['delta_from_baseline']:+.2f}s)"
            )

        return {
            'has_drift': has_significant_drift,
            'drift_magnitude': float(drift_magnitude),
            'drift_magnitude_ms': float(drift_magnitude * 1000),
            'median_offset': float(np.median(chunk_offsets)) if chunk_offsets else 0.0,
            'offset_range': {
                'min': float(min(chunk_offsets)) if chunk_offsets else 0.0,
                'max': float(max(chunk_offsets)) if chunk_offsets else 0.0
            },
            'timeline': timeline,
            'drift_regions': drift_regions,
            'drift_summary': drift_summary,
            'baseline_offset': float(baseline_offset),
            'localized_events': localized_events,
            'total_reliable_chunks': len([t for t in timeline if t['reliable']])
        }
    
    def _cleanup_temp_files(self, file_paths: List[str]):
        """Clean up temporary files"""
        for file_path in file_paths:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    self.logger.info(f"Cleaned up: {file_path}")
                except Exception as e:
                    self.logger.warning(f"Failed to cleanup {file_path}: {e}")
    
    def __del__(self):
        """Cleanup temp directory on destruction"""
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            import shutil
            try:
                shutil.rmtree(self.temp_dir)
            except:
                pass
