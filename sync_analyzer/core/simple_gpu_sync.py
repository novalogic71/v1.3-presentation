#!/usr/bin/env python3
"""
Simple GPU Sync Detector - Wav2Vec2 Only
=========================================

A streamlined, GPU-accelerated sync detector using only Wav2Vec2 embeddings.
Designed for speed and simplicity - one model, one method, fast results.

Author: AI Audio Engineer
Version: 1.0.0
"""

import os
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

import torch
import torchaudio
import numpy as np
import scipy.signal

logger = logging.getLogger(__name__)


@dataclass
class SimpleSyncResult:
    """Simple sync detection result."""
    offset_seconds: float
    offset_samples: int
    confidence: float
    sample_rate: int
    method: str = "wav2vec2_gpu"
    processing_time: float = 0.0
    bars_tone_detected: bool = False
    bars_tone_duration: float = 0.0
    

class SimpleGPUSyncDetector:
    """
    Simple GPU-accelerated sync detector using Wav2Vec2 embeddings.
    
    This is a streamlined alternative to the multi-method detector.
    One model, one method, fast and reliable.
    """
    
    def __init__(
        self,
        model_name: str = "facebook/wav2vec2-base-960h",
        device: Optional[str] = None,
        local_model_path: Optional[str] = None,
    ):
        """
        Initialize the simple GPU sync detector.
        
        Args:
            model_name: HuggingFace model name
            device: Device to use ('cuda', 'cpu', or None for auto)
            local_model_path: Path to local model (offline mode)
        """
        import time
        start = time.time()
        
        # Auto-detect device
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        logger.info(f"SimpleGPUSyncDetector initializing on {self.device}")
        
        # Load model
        self._load_model(model_name, local_model_path)
        
        # Wav2Vec2 expects 16kHz
        self.target_sr = 16000
        
        # Frame rate: Wav2Vec2 outputs ~50 frames per second (20ms per frame)
        self.frame_rate = 50  # frames per second
        self.frame_duration = 0.02  # 20ms per frame
        
        logger.info(f"Model loaded in {time.time() - start:.2f}s")
    
    def _load_model(self, model_name: str, local_path: Optional[str] = None):
        """Load the Wav2Vec2 model."""
        # Use FeatureExtractor instead of Processor - we don't need the tokenizer
        from transformers import Wav2Vec2Model, Wav2Vec2FeatureExtractor
        
        # Check for local model first
        if local_path and os.path.exists(local_path):
            logger.info(f"Loading local model from {local_path}")
            self.processor = Wav2Vec2FeatureExtractor.from_pretrained(local_path)
            self.model = Wav2Vec2Model.from_pretrained(local_path)
        else:
            # Check environment for local-only mode
            local_only = os.environ.get("HF_LOCAL_ONLY", "0").lower() in ("1", "true", "yes")
            
            # Try common local cache paths
            cache_dirs = [
                os.environ.get("AI_MODEL_CACHE_DIR"),
                os.environ.get("HF_HOME"),
                os.path.expanduser("~/.cache/huggingface"),
                "/app/ai_models",
            ]
            
            for cache_dir in cache_dirs:
                if cache_dir:
                    model_path = os.path.join(cache_dir, "models--facebook--wav2vec2-base-960h")
                    if os.path.exists(model_path):
                        logger.info(f"Loading model from cache: {model_path}")
                        self.processor = Wav2Vec2FeatureExtractor.from_pretrained(model_name, cache_dir=cache_dir, local_files_only=True)
                        self.model = Wav2Vec2Model.from_pretrained(model_name, cache_dir=cache_dir, local_files_only=True)
                        break
            else:
                if local_only:
                    raise RuntimeError(f"Model not found locally and HF_LOCAL_ONLY is set")
                logger.info(f"Downloading model {model_name}")
                self.processor = Wav2Vec2FeatureExtractor.from_pretrained(model_name)
                self.model = Wav2Vec2Model.from_pretrained(model_name)
        
        self.model = self.model.to(self.device)
        self.model.eval()
        logger.info(f"Model loaded on {self.device}")
    
    def _load_audio(self, path: str) -> Tuple[torch.Tensor, int]:
        """
        Load audio from file, handling video containers via FFmpeg.
        
        Returns:
            Tuple of (audio_tensor, sample_rate)
        """
        path = str(path)
        
        # Check if it's a video container that needs FFmpeg
        video_extensions = {'.mp4', '.mov', '.mkv', '.avi', '.mxf', '.m4v'}
        ext = Path(path).suffix.lower()
        
        if ext in video_extensions:
            # Extract audio with FFmpeg
            logger.debug(f"Extracting audio from video: {path}")
            temp_wav = tempfile.mktemp(suffix=".wav", prefix="sync_")
            
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-i", path,
                "-vn",  # No video
                "-ac", "1",  # Mono
                "-ar", str(self.target_sr),  # Target sample rate
                "-acodec", "pcm_s16le",
                "-y", temp_wav
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg failed: {result.stderr}")
            
            audio, sr = torchaudio.load(temp_wav)
            os.remove(temp_wav)
        else:
            # Direct load for audio files
            audio, sr = torchaudio.load(path)
        
        # Convert to mono if needed
        if audio.shape[0] > 1:
            audio = audio.mean(dim=0, keepdim=True)
        
        # Resample if needed
        if sr != self.target_sr:
            resampler = torchaudio.transforms.Resample(sr, self.target_sr)
            audio = resampler(audio)
            sr = self.target_sr
        
        return audio.squeeze(0), sr
    
    @torch.no_grad()
    def _extract_embeddings(self, audio: torch.Tensor, max_duration: float = 300.0) -> torch.Tensor:
        """
        Extract Wav2Vec2 embeddings from audio.

        Args:
            audio: Audio tensor (1D)
            max_duration: Maximum duration to process (seconds) - matches MFCC/Onset limit

        Returns:
            Embeddings tensor (frames x features)
        """
        # Limit to max_duration for speed (analyze first N seconds)
        max_samples = int(self.target_sr * max_duration)
        if len(audio) > max_samples:
            logger.info(f"Trimming audio from {len(audio)/self.target_sr:.1f}s to {max_duration}s for speed")
            audio = audio[:max_samples]
        
        # Minimum audio length for Wav2Vec2 (needs at least ~400 samples)
        min_samples = 1000
        if len(audio) < min_samples:
            logger.warning(f"Audio too short ({len(audio)} samples), padding")
            audio = torch.nn.functional.pad(audio, (0, min_samples - len(audio)))
        
        # Process in chunks if audio is very long (>30 seconds)
        chunk_samples = self.target_sr * 30  # 30 seconds per chunk
        
        if len(audio) > chunk_samples:
            # Process in chunks and concatenate
            embeddings_list = []
            for start in range(0, len(audio), chunk_samples):
                end = min(start + chunk_samples, len(audio))
                chunk = audio[start:end]
                # Skip very short final chunks
                if len(chunk) < min_samples:
                    continue
                emb = self._extract_embeddings_chunk(chunk)
                embeddings_list.append(emb)
            if embeddings_list:
                return torch.cat(embeddings_list, dim=0)
            else:
                return self._extract_embeddings_chunk(audio)
        else:
            return self._extract_embeddings_chunk(audio)
    
    def _extract_embeddings_chunk(self, audio: torch.Tensor) -> torch.Tensor:
        """Extract embeddings from a single audio chunk."""
        # Prepare input
        inputs = self.processor(
            audio.cpu().numpy(),
            sampling_rate=self.target_sr,
            return_tensors="pt",
            padding=True
        )
        
        # Move to device
        input_values = inputs.input_values.to(self.device)
        
        # Get embeddings
        outputs = self.model(input_values)
        
        # Return last hidden state (frames x 768)
        return outputs.last_hidden_state.squeeze(0)
    
    def _cross_correlate_embeddings(
        self,
        master_emb: torch.Tensor,
        dub_emb: torch.Tensor
    ) -> Tuple[int, float]:
        """
        Cross-correlate embeddings to find offset using GPU-accelerated FFT.
        
        Uses PyTorch FFT for full GPU acceleration when available.
        
        Returns:
            Tuple of (offset_frames, confidence)
        """
        # Mean pool across feature dimension to get 1D signals (stay on GPU)
        master_signal = master_emb.mean(dim=1)
        dub_signal = dub_emb.mean(dim=1)
        
        # Normalize on GPU
        master_signal = (master_signal - master_signal.mean()) / (master_signal.std() + 1e-8)
        dub_signal = (dub_signal - dub_signal.mean()) / (dub_signal.std() + 1e-8)
        
        # GPU-accelerated cross-correlation using FFT
        # Pad to power of 2 for efficiency
        n = master_signal.shape[0] + dub_signal.shape[0] - 1
        fft_size = 1 << (n - 1).bit_length()  # Next power of 2
        
        # Zero-pad signals
        master_padded = torch.nn.functional.pad(master_signal, (0, fft_size - master_signal.shape[0]))
        dub_padded = torch.nn.functional.pad(dub_signal, (0, fft_size - dub_signal.shape[0]))
        
        # FFT-based cross-correlation: corr = IFFT(FFT(master) * conj(FFT(dub)))
        master_fft = torch.fft.fft(master_padded)
        dub_fft = torch.fft.fft(dub_padded)
        correlation_fft = master_fft * torch.conj(dub_fft)
        correlation = torch.fft.ifft(correlation_fft).real
        
        # Rearrange to match scipy.correlate output (mode='full')
        # The FFT correlation gives circular correlation; we need to shift
        correlation = torch.fft.fftshift(correlation)
        
        # Trim to valid length
        start = (fft_size - n) // 2
        correlation = correlation[start:start + n]
        
        # Find peak (on GPU, then move scalar to CPU)
        abs_corr = torch.abs(correlation)
        peak_idx = torch.argmax(abs_corr).item()
        peak_value = abs_corr[peak_idx].item()
        
        # For mode='full' correlation, zero-lag is at len(dub)-1
        offset_frames = peak_idx - (dub_signal.shape[0] - 1)
        
        # Confidence based on peak prominence (calculate on GPU)
        mean_corr = abs_corr.mean().item()
        std_corr = abs_corr.std().item()
        
        prominence = (peak_value - mean_corr) / (std_corr + 1e-8)
        confidence = min(1.0, max(0.0, prominence / 5.0))  # Scale to 0-1
        
        logger.debug(f"GPU Correlation: peak_idx={peak_idx}, offset_frames={offset_frames}, "
                    f"peak={peak_value:.4f}, mean={mean_corr:.4f}, confidence={confidence:.3f}")
        
        return offset_frames, confidence
    
    def detect_bars_tone(self, audio: torch.Tensor, max_search_seconds: float = 120.0) -> float:
        """
        Detect bars and tone (1kHz reference tone) at the head of the audio.
        
        IMPROVED VERSION with strict checks to avoid false positives:
        - Spectral purity: 1kHz must dominate by 5x over other frequencies
        - Exact frequency: Must be within 15Hz of exactly 1000Hz
        - Energy concentration: 50%+ of energy must be at 1kHz (not 30%)
        - Amplitude consistency: Level must be stable (real tone doesn't fluctuate)
        - Minimum duration: At least 10 seconds of continuous tone
        
        Args:
            audio: Audio tensor (1D)
            max_search_seconds: Maximum duration to search for tone
            
        Returns:
            Timestamp where program content starts (0.0 if no tone detected)
        """
        try:
            # Convert to numpy for FFT analysis
            if isinstance(audio, torch.Tensor):
                audio_np = audio.cpu().numpy()
            else:
                audio_np = audio
            
            sr = self.target_sr
            max_samples = int(max_search_seconds * sr)
            audio_np = audio_np[:max_samples]
            
            # STRICT parameters for tone detection
            tone_freq = 1000  # 1kHz reference tone (broadcast standard)
            freq_tolerance = 15  # Hz tolerance - STRICT (real tone is exactly 1kHz)
            window_size = int(0.1 * sr)  # 100ms windows
            hop_size = window_size // 2
            min_tone_duration = 10.0  # Minimum 10 seconds of tone (was 5)
            min_purity_ratio = 5.0  # 1kHz must be 5x louder than next peak
            min_energy_ratio = 0.50  # 50% of energy at 1kHz (was 30%)
            
            tone_detected = []
            window_amplitudes = []  # Track amplitude for consistency check
            
            for start in range(0, len(audio_np) - window_size, hop_size):
                window = audio_np[start:start + window_size]
                time_seconds = start / sr
                
                # FFT to find dominant frequency
                fft = np.fft.rfft(window * np.hanning(len(window)))
                freqs = np.fft.rfftfreq(len(window), 1/sr)
                magnitude = np.abs(fft)
                
                # Find peak frequency and value
                peak_idx = np.argmax(magnitude)
                peak_freq = freqs[peak_idx]
                peak_magnitude = magnitude[peak_idx]
                
                # Calculate energy in 1kHz band (narrow: ±15Hz)
                freq_min_idx = np.searchsorted(freqs, tone_freq - freq_tolerance)
                freq_max_idx = np.searchsorted(freqs, tone_freq + freq_tolerance)
                tone_band_energy = np.sum(magnitude[freq_min_idx:freq_max_idx] ** 2)
                total_energy = np.sum(magnitude ** 2) + 1e-10
                energy_ratio = tone_band_energy / total_energy
                
                # CHECK 1: Spectral purity - is 1kHz MUCH higher than second peak?
                # Real 1kHz tone is a pure sine wave, music has multiple frequencies
                magnitude_sorted = np.sort(magnitude)[::-1]
                second_peak = magnitude_sorted[1] if len(magnitude_sorted) > 1 else 1e-10
                purity_ratio = peak_magnitude / (second_peak + 1e-10)
                is_pure = purity_ratio >= min_purity_ratio
                
                # CHECK 2: Exact frequency - must be very close to 1000Hz
                is_exact_freq = abs(peak_freq - tone_freq) < freq_tolerance
                
                # CHECK 3: Energy concentration - most energy at 1kHz
                is_concentrated = energy_ratio >= min_energy_ratio
                
                # CHECK 4: Not silence
                is_audible = total_energy > 1e-6
                
                # ALL checks must pass for this to be real bars/tone
                is_tone = is_pure and is_exact_freq and is_concentrated and is_audible
                
                tone_detected.append((time_seconds, is_tone, peak_freq, purity_ratio, energy_ratio))
                
                if is_tone:
                    window_amplitudes.append(np.sqrt(total_energy))
            
            if not tone_detected:
                logger.info("GPU Detector: No tone candidates found")
                return 0.0
            
            # Find continuous tone region at start
            tone_start = None
            tone_end = None
            consecutive_tone = 0
            consecutive_threshold = int(min_tone_duration / 0.05)  # windows per required duration
            
            for time_sec, is_tone, freq, purity, energy in tone_detected:
                if is_tone:
                    if tone_start is None:
                        tone_start = time_sec
                    consecutive_tone += 1
                else:
                    # Tone just ended - check if it was long enough
                    if consecutive_tone >= consecutive_threshold and tone_start is not None:
                        tone_end = time_sec
                        # Found valid tone region - must start within first second
                        if tone_start < 1.0:
                            break
                    # Not enough consecutive tone - reset
                    if consecutive_tone < consecutive_threshold:
                        tone_start = None
                    consecutive_tone = 0
            
            # CHECK 5: Amplitude consistency - real tone has stable level
            if window_amplitudes and len(window_amplitudes) >= consecutive_threshold:
                amplitude_std = np.std(window_amplitudes)
                amplitude_mean = np.mean(window_amplitudes)
                amplitude_cv = amplitude_std / (amplitude_mean + 1e-10)  # Coefficient of variation
                is_stable = amplitude_cv < 0.15  # Less than 15% variation
                
                if not is_stable:
                    logger.info(f"GPU Detector: Tone candidate rejected - amplitude varies too much "
                               f"(CV={amplitude_cv:.2%}, need <15%)")
                    return 0.0
            
            if tone_start is not None and tone_start < 1.0 and tone_end is not None:
                # Log details for verification
                avg_purity = np.mean([t[3] for t in tone_detected if t[1]])
                avg_energy = np.mean([t[4] for t in tone_detected if t[1]])
                avg_freq = np.mean([t[2] for t in tone_detected if t[1]])
                
                program_start = tone_end + 0.5
                logger.info(f"✅ GPU Detector: REAL bars/tone detected!")
                logger.info(f"   Duration: {tone_start:.1f}s to {tone_end:.1f}s ({tone_end-tone_start:.1f}s)")
                logger.info(f"   Avg frequency: {avg_freq:.1f}Hz (target: 1000Hz)")
                logger.info(f"   Avg purity ratio: {avg_purity:.1f}x (min: {min_purity_ratio}x)")
                logger.info(f"   Avg energy ratio: {avg_energy:.1%} (min: {min_energy_ratio:.0%})")
                logger.info(f"   Program starts at: {program_start:.1f}s")
                return program_start
            
            # Log why detection failed for debugging
            if tone_start is not None:
                logger.info(f"GPU Detector: Tone candidate at {tone_start:.1f}s rejected - "
                           f"not long enough ({consecutive_tone} windows, need {consecutive_threshold})")
            else:
                logger.info("GPU Detector: No bars/tone detected at head of file")
            return 0.0
            
        except Exception as e:
            logger.warning(f"GPU Detector: Error detecting bars/tone: {e}")
            return 0.0
    
    def detect_sync(
        self,
        master_path: str,
        dub_path: str,
        progress_callback: Optional[callable] = None,
        skip_bars_tone: bool = True  # Re-enabled with improved detection
    ) -> SimpleSyncResult:
        """
        Detect sync offset between master and dub audio.
        
        Args:
            master_path: Path to master audio/video file
            dub_path: Path to dub audio/video file
            progress_callback: Optional callback(progress, message)
            skip_bars_tone: If True, auto-detect and skip bars/tone at head of master
            
        Returns:
            SimpleSyncResult with offset and confidence
        """
        import time
        start_time = time.time()
        
        def update_progress(pct: float, msg: str):
            if progress_callback:
                progress_callback(pct, msg)
            logger.info(f"[{pct:.0f}%] {msg}")
        
        update_progress(0, "Loading master audio...")
        master_audio, sr = self._load_audio(master_path)
        
        # Detect bars/tone in master
        master_program_start = 0.0
        if skip_bars_tone:
            update_progress(5, "Checking master for bars/tone...")
            master_program_start = self.detect_bars_tone(master_audio)
            if master_program_start > 0:
                logger.info(f"✅ Master has bars/tone, program starts at {master_program_start:.2f}s")
            else:
                logger.info(f"Master: no bars/tone detected")
        
        update_progress(15, "Loading dub audio...")
        dub_audio, _ = self._load_audio(dub_path)
        
        # Detect bars/tone in dub (IMPORTANT: both files may have bars/tone!)
        dub_program_start = 0.0
        if skip_bars_tone:
            update_progress(20, "Checking dub for bars/tone...")
            dub_program_start = self.detect_bars_tone(dub_audio)
            if dub_program_start > 0:
                logger.info(f"✅ Dub has bars/tone, program starts at {dub_program_start:.2f}s")
            else:
                logger.info(f"Dub: no bars/tone detected")
        
        # Trim BOTH audio files if bars/tone detected
        if master_program_start > 0:
            start_sample = int(master_program_start * sr)
            master_audio_trimmed = master_audio[start_sample:]
            logger.info(f"Master trimmed: starting from {master_program_start:.2f}s "
                       f"({len(master_audio_trimmed)/sr:.2f}s remaining)")
        else:
            master_audio_trimmed = master_audio
        
        if dub_program_start > 0:
            start_sample = int(dub_program_start * sr)
            dub_audio_trimmed = dub_audio[start_sample:]
            logger.info(f"Dub trimmed: starting from {dub_program_start:.2f}s "
                       f"({len(dub_audio_trimmed)/sr:.2f}s remaining)")
        else:
            dub_audio_trimmed = dub_audio
        
        update_progress(40, "Extracting master embeddings...")
        master_emb = self._extract_embeddings(master_audio_trimmed)
        
        update_progress(60, "Extracting dub embeddings...")
        dub_emb = self._extract_embeddings(dub_audio_trimmed)
        
        update_progress(80, "Computing cross-correlation...")
        offset_frames, confidence = self._cross_correlate_embeddings(master_emb, dub_emb)
        
        # Convert frame offset to time
        raw_offset_seconds = offset_frames * self.frame_duration
        logger.info(f"Raw correlation offset (program-to-program): {raw_offset_seconds:.3f}s")
        
        # Adjust offset to be relative to ORIGINAL file starts (before trimming)
        # Final offset = raw_offset + master_bars - dub_bars
        # This gives us: how much to shift the ORIGINAL dub to align with ORIGINAL master
        offset_seconds = raw_offset_seconds + master_program_start - dub_program_start
        
        if master_program_start > 0 or dub_program_start > 0:
            logger.info(f"Bars/tone adjustment: {raw_offset_seconds:.3f}s + {master_program_start:.2f}s (master) "
                       f"- {dub_program_start:.2f}s (dub) = {offset_seconds:.3f}s")
        
        offset_samples = int(offset_seconds * sr)
        
        processing_time = time.time() - start_time
        update_progress(100, f"Done! Offset: {offset_seconds:.3f}s, Confidence: {confidence:.2f}")
        
        return SimpleSyncResult(
            offset_seconds=offset_seconds,
            offset_samples=offset_samples,
            confidence=confidence,
            sample_rate=sr,
            method="wav2vec2_gpu",
            processing_time=processing_time,
            bars_tone_detected=master_program_start > 0,
            bars_tone_duration=master_program_start
        )


def quick_sync_check(master_path: str, dub_path: str, device: str = "cuda") -> Dict[str, Any]:
    """
    Quick function for one-off sync detection.
    
    Args:
        master_path: Path to master file
        dub_path: Path to dub file
        device: Device to use
        
    Returns:
        Dict with offset_seconds, confidence, processing_time
    """
    detector = SimpleGPUSyncDetector(device=device)
    result = detector.detect_sync(master_path, dub_path)
    
    return {
        "offset_seconds": result.offset_seconds,
        "offset_ms": result.offset_seconds * 1000,
        "offset_frames_24fps": round(result.offset_seconds * 24),
        "offset_frames_30fps": round(result.offset_seconds * 29.97),
        "confidence": result.confidence,
        "processing_time": result.processing_time,
        "method": result.method,
        "device": device
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python simple_gpu_sync.py <master> <dub>")
        sys.exit(1)
    
    master = sys.argv[1]
    dub = sys.argv[2]
    
    print(f"\n🎵 Simple GPU Sync Detector (Wav2Vec2)")
    print(f"=" * 50)
    print(f"Master: {master}")
    print(f"Dub: {dub}")
    print()
    
    result = quick_sync_check(master, dub)
    
    print(f"\n📊 Results:")
    print(f"   Offset: {result['offset_seconds']:.3f}s ({result['offset_ms']:.1f}ms)")
    print(f"   Frames: {result['offset_frames_24fps']}f @24fps | {result['offset_frames_30fps']}f @30fps")
    print(f"   Confidence: {result['confidence']:.2%}")
    print(f"   Time: {result['processing_time']:.2f}s")
    print(f"   Device: {result['device']}")

