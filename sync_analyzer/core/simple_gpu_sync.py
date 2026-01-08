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
        from transformers import Wav2Vec2Model, Wav2Vec2Processor
        
        # Check for local model first
        if local_path and os.path.exists(local_path):
            logger.info(f"Loading local model from {local_path}")
            self.processor = Wav2Vec2Processor.from_pretrained(local_path)
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
                        self.processor = Wav2Vec2Processor.from_pretrained(model_name, cache_dir=cache_dir, local_files_only=True)
                        self.model = Wav2Vec2Model.from_pretrained(model_name, cache_dir=cache_dir, local_files_only=True)
                        break
            else:
                if local_only:
                    raise RuntimeError(f"Model not found locally and HF_LOCAL_ONLY is set")
                logger.info(f"Downloading model {model_name}")
                self.processor = Wav2Vec2Processor.from_pretrained(model_name)
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
    def _extract_embeddings(self, audio: torch.Tensor, max_duration: float = 120.0) -> torch.Tensor:
        """
        Extract Wav2Vec2 embeddings from audio.
        
        Args:
            audio: Audio tensor (1D)
            max_duration: Maximum duration to process (for speed)
            
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
    
    def detect_sync(
        self,
        master_path: str,
        dub_path: str,
        progress_callback: Optional[callable] = None
    ) -> SimpleSyncResult:
        """
        Detect sync offset between master and dub audio.
        
        Args:
            master_path: Path to master audio/video file
            dub_path: Path to dub audio/video file
            progress_callback: Optional callback(progress, message)
            
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
        
        update_progress(20, "Loading dub audio...")
        dub_audio, _ = self._load_audio(dub_path)
        
        update_progress(40, "Extracting master embeddings...")
        master_emb = self._extract_embeddings(master_audio)
        
        update_progress(60, "Extracting dub embeddings...")
        dub_emb = self._extract_embeddings(dub_audio)
        
        update_progress(80, "Computing cross-correlation...")
        offset_frames, confidence = self._cross_correlate_embeddings(master_emb, dub_emb)
        
        # Convert frame offset to time
        offset_seconds = offset_frames * self.frame_duration
        offset_samples = int(offset_seconds * sr)
        
        processing_time = time.time() - start_time
        update_progress(100, f"Done! Offset: {offset_seconds:.3f}s, Confidence: {confidence:.2f}")
        
        return SimpleSyncResult(
            offset_seconds=offset_seconds,
            offset_samples=offset_samples,
            confidence=confidence,
            sample_rate=sr,
            method="wav2vec2_gpu",
            processing_time=processing_time
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

