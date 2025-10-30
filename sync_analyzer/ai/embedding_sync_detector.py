#!/usr/bin/env python3
"""
AI-Based Audio Sync Detection using Deep Learning Embeddings
============================================================

This module implements advanced AI-based sync detection using pretrained audio
embeddings and neural network approaches for robust sync analysis between
master and dubbed audio tracks.

Author: AI Audio Engineer
Version: 1.0.0
"""

import numpy as np
import os
import torch
import torch.nn as nn
import torch.nn.functional as F
import librosa
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import logging
from sklearn.metrics.pairwise import cosine_similarity
from scipy.spatial.distance import euclidean
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

logger = logging.getLogger(__name__)

@dataclass
class EmbeddingConfig:
    """Configuration for embedding-based sync detection."""
    model_name: str = "wav2vec2"
    embedding_dim: int = 768
    window_size: float = 2.0  # seconds
    hop_size: float = 0.5     # seconds
    sample_rate: int = 16000
    normalize_embeddings: bool = True
    use_gpu: bool = True

@dataclass
class AISyncResult:
    """Container for AI-based sync analysis results."""
    offset_samples: int
    offset_seconds: float
    confidence: float
    embedding_similarity: float
    temporal_consistency: float
    method_details: Dict[str, Any]

class AudioEmbeddingExtractor:
    """
    Extracts deep learning embeddings from audio using pretrained models.
    """
    
    def __init__(self, config: EmbeddingConfig):
        """
        Initialize the embedding extractor.
        
        Args:
            config: Configuration for embedding extraction
        """
        self.config = config
        
        # Multi-GPU support: distribute load across available GPUs
        if config.use_gpu and torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            # Use round-robin GPU selection based on process ID or thread ID
            import os
            gpu_id = (os.getpid() % gpu_count) if gpu_count > 1 else 0
            self.device = torch.device(f'cuda:{gpu_id}')
            logger.info(f"Using GPU {gpu_id} of {gpu_count} available GPUs")
        else:
            self.device = torch.device('cpu')
        
        # Initialize model based on configuration
        self.model_type = "unknown"
        self._init_model()

        # Log both requested and active model for clarity
        logger.info(
            f"AudioEmbeddingExtractor initialized: requested={config.model_name}, "
            f"active={self.model_type}, device={self.device}"
        )
    
    def _init_model(self):
        """Initialize the embedding model."""
        try:
            if self.config.model_name == "wav2vec2":
                self._init_wav2vec2()
            elif self.config.model_name == "yamnet":
                self._init_yamnet()
            else:
                raise ValueError(f"Unsupported model: {self.config.model_name}")
        except Exception as e:
            logger.warning(f"Could not load {self.config.model_name}, falling back to spectral embeddings: {e}")
            self._init_spectral_embeddings()
    
    def _init_wav2vec2(self):
        """Initialize Wav2Vec2 model for embeddings."""
        try:
            import transformers
            from transformers import Wav2Vec2Model, Wav2Vec2Processor
            
            # Allow overriding the model path/id to a local directory
            model_name = os.getenv("AI_WAV2VEC2_MODEL_PATH", "facebook/wav2vec2-base-960h")

            # Respect local cache configuration if provided
            cache_dir = os.getenv("AI_MODEL_CACHE_DIR") or None
            # Enforce fully offline usage if HF_LOCAL_ONLY is set, or when a local path is provided
            local_only_env = str(os.getenv("HF_LOCAL_ONLY", "1")).lower() in {"1", "true", "yes"}
            force_local = local_only_env or os.path.isdir(model_name)

            self.processor = Wav2Vec2Processor.from_pretrained(
                model_name,
                cache_dir=cache_dir,
                local_files_only=force_local,
            )
            self.model = Wav2Vec2Model.from_pretrained(
                model_name,
                cache_dir=cache_dir,
                local_files_only=force_local,
            )
            self.model.to(self.device)
            self.model.eval()
            self.model_type = "wav2vec2"
            
            logger.info("Wav2Vec2 model loaded successfully")
            
        except ImportError:
            logger.warning(
                "Transformers library not available. Install with 'pip install transformers' "
                "or 'pip install -r fastapi_app/requirements.txt'. Falling back to spectral embeddings."
            )
            self._init_spectral_embeddings()
        except Exception as e:
            logger.warning(
                f"Failed to initialize Wav2Vec2 ({e}). Using spectral embeddings fallback. "
                f"Hint: set AI_MODEL_CACHE_DIR to a writable path; set HF_LOCAL_ONLY=1 for offline."
            )
            self._init_spectral_embeddings()
    
    def _init_yamnet(self):
        """Initialize YAMNet model for embeddings (prefer local)."""
        try:
            import tensorflow as tf
            import tensorflow_hub as hub
            import pathlib

            # Prefer local model path for offline usage
            local_hint = os.getenv("YAMNET_MODEL_PATH")
            cache_root = os.getenv("AI_MODEL_CACHE_DIR")

            def _find_saved_model_dir(root: str):
                try:
                    p = pathlib.Path(root)
                    if not p.exists():
                        return None
                    if (p / 'saved_model.pb').exists():
                        return str(p)
                    for child in p.rglob('saved_model.pb'):
                        return str(child.parent)
                except Exception:
                    return None
                return None

            local_model_dir = None
            if local_hint:
                local_model_dir = _find_saved_model_dir(local_hint)
            if not local_model_dir and cache_root:
                for sub in ('yamnet', 'yamnet/1', 'tfhub/yamnet', 'tfhub_modules/yamnet/1'):
                    local_model_dir = _find_saved_model_dir(os.path.join(cache_root, sub))
                    if local_model_dir:
                        break

            if local_model_dir:
                logger.info(f"Loading YAMNet from local path: {local_model_dir}")
                self.model = hub.load(local_model_dir)
            else:
                allow_online = str(os.getenv("AI_ALLOW_ONLINE_MODELS", "0")).lower() in {"1", "true", "yes"}
                if allow_online:
                    logger.warning("YAMNet local model not found; attempting online download from TF Hub")
                    self.model = hub.load('https://tfhub.dev/google/yamnet/1')
                else:
                    raise RuntimeError(
                        "YAMNet local model not found. Set YAMNET_MODEL_PATH or place a saved_model under AI_MODEL_CACHE_DIR."
                    )
            self.model_type = "yamnet"
            logger.info("YAMNet model loaded successfully")
        except ImportError:
            logger.warning("TensorFlow Hub not available, falling back")
            self._init_spectral_embeddings()
        except Exception as e:
            logger.warning(f"Failed to initialize YAMNet locally: {e}. Falling back to spectral embeddings.")
            self._init_spectral_embeddings()
    
    def _init_spectral_embeddings(self):
        """Initialize spectral-based embeddings as fallback."""
        self.model_type = "spectral"
        logger.info("Using spectral embeddings as fallback")
    
    def extract_embeddings(self, audio: np.ndarray, sr: int, progress_callback=None) -> np.ndarray:
        """
        Extract embeddings from audio.
        
        Args:
            audio: Audio samples
            sr: Sample rate
            progress_callback: Optional callback function for progress updates
            
        Returns:
            Array of embeddings with shape (n_windows, embedding_dim)
        """
        if self.model_type == "wav2vec2":
            return self._extract_wav2vec2_embeddings(audio, sr, progress_callback)
        elif self.model_type == "yamnet":
            return self._extract_yamnet_embeddings(audio, sr, progress_callback)
        else:
            return self._extract_spectral_embeddings(audio, sr, progress_callback)
    
    def _extract_wav2vec2_embeddings(self, audio: np.ndarray, sr: int, progress_callback=None) -> np.ndarray:
        """Extract embeddings using Wav2Vec2."""
        # Resample if needed
        if sr != 16000:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
            sr = 16000
        
        # Split into windows
        window_samples = int(self.config.window_size * sr)
        hop_samples = int(self.config.hop_size * sr)
        
        # Calculate total windows for progress tracking
        total_windows = len(range(0, len(audio) - window_samples + 1, hop_samples))
        
        embeddings = []
        
        for i, start in enumerate(range(0, len(audio) - window_samples + 1, hop_samples)):
            window = audio[start:start + window_samples]
            
            # Process with Wav2Vec2
            with torch.no_grad():
                inputs = self.processor(
                    window, 
                    sampling_rate=sr, 
                    return_tensors="pt"
                ).input_values.to(self.device)
                
                outputs = self.model(inputs)
                # Use last hidden state, average over time
                embedding = outputs.last_hidden_state.mean(dim=1).cpu().numpy()
                embeddings.append(embedding.flatten())
            
            # Report progress
            if progress_callback:
                progress_percent = (i + 1) / total_windows * 100
                progress_callback(progress_percent, f"Processing window {i+1}/{total_windows}")
            
            # For console logging
            if (i + 1) % 10 == 0 or (i + 1) == total_windows:
                logger.info(f"Processed {i+1}/{total_windows} audio windows ({(i+1)/total_windows*100:.1f}%)")
        
        embeddings = np.array(embeddings)
        
        if self.config.normalize_embeddings:
            embeddings = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-8)
        
        return embeddings
    
    def _extract_yamnet_embeddings(self, audio: np.ndarray, sr: int, progress_callback=None) -> np.ndarray:
        """Extract embeddings using YAMNet."""
        import tensorflow as tf
        
        # Resample if needed
        if sr != 16000:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
            sr = 16000
        
        # Split into windows
        window_samples = int(self.config.window_size * sr)
        hop_samples = int(self.config.hop_size * sr)
        
        # Calculate total windows for progress tracking
        window_positions = list(range(0, len(audio) - window_samples + 1, hop_samples))
        total_windows = len(window_positions)
        
        embeddings = []
        
        for i, start in enumerate(window_positions):
            window = audio[start:start + window_samples]
            
            # Process with YAMNet
            window_tf = tf.constant(window.astype(np.float32))
            scores, embedding, spectrogram = self.model(window_tf)
            
            # Average embeddings over time
            embedding_avg = tf.reduce_mean(embedding, axis=0).numpy()
            embeddings.append(embedding_avg)
            
            # Report progress
            if progress_callback:
                progress_percent = (i + 1) / total_windows * 100
                progress_callback(progress_percent, f"Processing YAMNet window {i+1}/{total_windows}")
            
            # For console logging
            if (i + 1) % 10 == 0 or (i + 1) == total_windows:
                logger.info(f"Processed {i+1}/{total_windows} YAMNet windows ({(i+1)/total_windows*100:.1f}%)")
        
        embeddings = np.array(embeddings)
        
        if self.config.normalize_embeddings:
            embeddings = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-8)
        
        return embeddings
    
    def _extract_spectral_embeddings(self, audio: np.ndarray, sr: int, progress_callback=None) -> np.ndarray:
        """Extract spectral-based embeddings as fallback."""
        # Split into windows
        window_samples = int(self.config.window_size * sr)
        hop_samples = int(self.config.hop_size * sr)
        
        # Calculate total windows for progress tracking
        window_positions = list(range(0, len(audio) - window_samples + 1, hop_samples))
        total_windows = len(window_positions)
        
        embeddings = []
        
        for i, start in enumerate(window_positions):
            window = audio[start:start + window_samples]
            
            # Extract comprehensive spectral features
            features = []
            
            # MFCC features
            mfccs = librosa.feature.mfcc(y=window, sr=sr, n_mfcc=13)
            features.append(np.mean(mfccs, axis=1))
            
            # Spectral features
            spectral_centroid = librosa.feature.spectral_centroid(y=window, sr=sr)
            spectral_bandwidth = librosa.feature.spectral_bandwidth(y=window, sr=sr)
            spectral_rolloff = librosa.feature.spectral_rolloff(y=window, sr=sr)
            
            features.extend([
                np.mean(spectral_centroid),
                np.mean(spectral_bandwidth),
                np.mean(spectral_rolloff)
            ])
            
            # Chroma features
            chroma = librosa.feature.chroma_stft(y=window, sr=sr)
            features.append(np.mean(chroma, axis=1))
            
            # Mel spectrogram statistics
            mel_spec = librosa.feature.melspectrogram(y=window, sr=sr, n_mels=64)
            mel_spec_db = librosa.power_to_db(mel_spec)
            features.extend([
                np.mean(mel_spec_db, axis=1),
                np.std(mel_spec_db, axis=1)
            ])
            
            # Combine all features
            embedding = np.concatenate([
                f.flatten() if hasattr(f, 'flatten') else [f] 
                for f in features
            ])
            
            embeddings.append(embedding)
            
            # Report progress
            if progress_callback:
                progress_percent = (i + 1) / total_windows * 100
                progress_callback(progress_percent, f"Processing spectral window {i+1}/{total_windows}")
            
            # For console logging
            if (i + 1) % 10 == 0 or (i + 1) == total_windows:
                logger.info(f"Processed {i+1}/{total_windows} spectral windows ({(i+1)/total_windows*100:.1f}%)")
        
        embeddings = np.array(embeddings)
        
        # Pad or truncate to consistent size
        target_dim = 256  # Fixed embedding dimension
        if embeddings.shape[1] > target_dim:
            embeddings = embeddings[:, :target_dim]
        elif embeddings.shape[1] < target_dim:
            padding = target_dim - embeddings.shape[1]
            embeddings = np.pad(embeddings, ((0, 0), (0, padding)), mode='constant')
        
        if self.config.normalize_embeddings:
            embeddings = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-8)
        
        return embeddings

class AISyncDetector:
    """
    AI-powered sync detector using deep learning embeddings.
    """
    
    def __init__(self, config: Optional[EmbeddingConfig] = None):
        """
        Initialize AI sync detector.
        
        Args:
            config: Configuration for embedding extraction
        """
        self.config = config or EmbeddingConfig()
        self.embedding_extractor = AudioEmbeddingExtractor(self.config)
        
        logger.info("AISyncDetector initialized")
    
    def compute_similarity_matrix(self, 
                                 master_embeddings: np.ndarray,
                                 dub_embeddings: np.ndarray) -> np.ndarray:
        """
        Compute similarity matrix between master and dub embeddings.
        
        Args:
            master_embeddings: Master audio embeddings
            dub_embeddings: Dub audio embeddings
            
        Returns:
            Similarity matrix
        """
        # Compute cosine similarity
        similarity_matrix = cosine_similarity(master_embeddings, dub_embeddings)
        return similarity_matrix
    
    def find_optimal_alignment(self, similarity_matrix: np.ndarray) -> Tuple[int, float]:
        """
        Find optimal alignment using dynamic time warping on similarity matrix.
        
        Args:
            similarity_matrix: Similarity matrix between embeddings
            
        Returns:
            Tuple of (offset_windows, alignment_confidence)
        """
        # Simple diagonal search for best alignment
        m, n = similarity_matrix.shape
        
        # Clear GPU cache to prevent memory buildup during batch processing
        if hasattr(self.embedding_extractor, 'device') and self.embedding_extractor.device.type == 'cuda':
            try:
                torch.cuda.empty_cache()
                # Clear memory on specific GPU device
                with torch.cuda.device(self.embedding_extractor.device):
                    torch.cuda.empty_cache()
            except Exception:
                pass
        
        # Try different diagonal alignments
        best_score = -np.inf
        best_offset = 0
        
        max_offset = min(m, n) // 2
        
        for offset in range(-max_offset, max_offset + 1):
            if offset >= 0:
                # Dub is delayed
                if offset < m and offset + n <= m:
                    diagonal = np.diag(similarity_matrix[offset:offset + n, :])
                else:
                    continue
            else:
                # Master is delayed
                abs_offset = abs(offset)
                if abs_offset < n and abs_offset + m <= n:
                    diagonal = np.diag(similarity_matrix[:, abs_offset:abs_offset + m])
                else:
                    continue
            
            if len(diagonal) > 0:
                score = np.mean(diagonal)
                if score > best_score:
                    best_score = score
                    best_offset = offset
        
        # Calculate confidence based on score and consistency
        confidence = min(best_score * 2, 1.0)  # Normalize to 0-1
        
        return best_offset, confidence
    
    def temporal_consistency_check(self, 
                                  master_embeddings: np.ndarray,
                                  dub_embeddings: np.ndarray,
                                  offset: int) -> float:
        """
        Check temporal consistency of alignment.
        
        Args:
            master_embeddings: Master embeddings
            dub_embeddings: Dub embeddings  
            offset: Detected offset in windows
            
        Returns:
            Temporal consistency score (0-1)
        """
        if offset == 0:
            min_len = min(len(master_embeddings), len(dub_embeddings))
            aligned_master = master_embeddings[:min_len]
            aligned_dub = dub_embeddings[:min_len]
        elif offset > 0:
            # Dub is delayed
            if offset >= len(master_embeddings):
                return 0.0
            master_slice = master_embeddings[offset:]
            min_len = min(len(master_slice), len(dub_embeddings))
            aligned_master = master_slice[:min_len]
            aligned_dub = dub_embeddings[:min_len]
        else:
            # Master is delayed
            abs_offset = abs(offset)
            if abs_offset >= len(dub_embeddings):
                return 0.0
            dub_slice = dub_embeddings[abs_offset:]
            min_len = min(len(master_embeddings), len(dub_slice))
            aligned_master = master_embeddings[:min_len]
            aligned_dub = dub_slice[:min_len]
        
        if len(aligned_master) == 0 or len(aligned_dub) == 0:
            return 0.0
        
        # Compute frame-by-frame similarity
        similarities = []
        for i in range(len(aligned_master)):
            sim = cosine_similarity([aligned_master[i]], [aligned_dub[i]])[0, 0]
            similarities.append(sim)
        
        # Temporal consistency is the stability of similarities
        similarities = np.array(similarities)
        consistency = 1.0 - np.std(similarities)  # Lower std = higher consistency
        
        return max(0.0, min(1.0, consistency))
    
    def detect_sync(self, 
                   master_audio: np.ndarray, 
                   dub_audio: np.ndarray,
                   sr: int,
                   progress_callback=None) -> AISyncResult:
        """
        Detect sync using AI embeddings.
        
        Args:
            master_audio: Master audio samples
            dub_audio: Dub audio samples
            sr: Sample rate
            progress_callback: Optional callback function for progress updates
            
        Returns:
            AISyncResult with sync analysis
        """
        def update_progress(stage_progress, stage_name, stage_weight, base_progress):
            if progress_callback:
                total_progress = base_progress + (stage_progress * stage_weight / 100)
                progress_callback(total_progress, f"AI Analysis: {stage_name}")
        
        logger.info("Extracting embeddings from master audio...")
        if progress_callback:
            progress_callback(5.0, "AI Analysis: Starting master audio processing...")
        
        master_callback = lambda p, msg: update_progress(p, f"Master embeddings - {msg}", 35, 5)
        master_embeddings = self.embedding_extractor.extract_embeddings(master_audio, sr, master_callback)
        
        logger.info("Extracting embeddings from dub audio...")
        if progress_callback:
            progress_callback(40.0, "AI Analysis: Processing dub audio...")
        
        dub_callback = lambda p, msg: update_progress(p, f"Dub embeddings - {msg}", 35, 40)
        dub_embeddings = self.embedding_extractor.extract_embeddings(dub_audio, sr, dub_callback)
        
        logger.info("Computing similarity matrix...")
        if progress_callback:
            progress_callback(75.0, "AI Analysis: Computing similarity matrix...")
        similarity_matrix = self.compute_similarity_matrix(master_embeddings, dub_embeddings)
        
        logger.info("Finding optimal alignment...")
        if progress_callback:
            progress_callback(90.0, "AI Analysis: Finding optimal alignment...")
        offset_windows, confidence = self.find_optimal_alignment(similarity_matrix)
        
        # Convert window offset to samples
        window_duration_samples = int(self.config.hop_size * sr)
        offset_samples = offset_windows * window_duration_samples
        offset_seconds = offset_samples / sr
        
        logger.info("Checking temporal consistency...")
        if progress_callback:
            progress_callback(95.0, "AI Analysis: Checking temporal consistency...")
        temporal_consistency = self.temporal_consistency_check(
            master_embeddings, dub_embeddings, offset_windows
        )
        
        # Calculate embedding similarity at optimal alignment
        if offset_windows == 0:
            min_len = min(len(master_embeddings), len(dub_embeddings))
            aligned_similarities = [
                cosine_similarity([master_embeddings[i]], [dub_embeddings[i]])[0, 0]
                for i in range(min_len)
            ]
        elif offset_windows > 0:
            max_len = min(len(master_embeddings) - offset_windows, len(dub_embeddings))
            aligned_similarities = [
                cosine_similarity([master_embeddings[i + offset_windows]], [dub_embeddings[i]])[0, 0]
                for i in range(max_len)
            ]
        else:
            abs_offset = abs(offset_windows)
            max_len = min(len(master_embeddings), len(dub_embeddings) - abs_offset)
            aligned_similarities = [
                cosine_similarity([master_embeddings[i]], [dub_embeddings[i + abs_offset]])[0, 0]
                for i in range(max_len)
            ]
        
        embedding_similarity = np.mean(aligned_similarities) if aligned_similarities else 0.0
        
        # Adjust confidence based on temporal consistency
        final_confidence = confidence * temporal_consistency
        
        if progress_callback:
            progress_callback(100.0, "AI Analysis: Complete!")
        
        return AISyncResult(
            offset_samples=int(offset_samples),
            offset_seconds=offset_seconds,
            confidence=final_confidence,
            embedding_similarity=embedding_similarity,
            temporal_consistency=temporal_consistency,
            method_details={
                "model_type": self.embedding_extractor.model_type,
                "window_size": self.config.window_size,
                "hop_size": self.config.hop_size,
                "master_windows": len(master_embeddings),
                "dub_windows": len(dub_embeddings),
                "similarity_matrix_shape": similarity_matrix.shape,
                "offset_windows": offset_windows
            }
        )
    
    def analyze_sync_quality(self, 
                           master_audio: np.ndarray,
                           dub_audio: np.ndarray,
                           sr: int,
                           sync_result: AISyncResult) -> Dict[str, float]:
        """
        Analyze the quality of sync detection result.
        
        Args:
            master_audio: Master audio samples
            dub_audio: Dub audio samples  
            sr: Sample rate
            sync_result: Previous sync detection result
            
        Returns:
            Dictionary of quality metrics
        """
        # Apply detected offset and re-analyze
        offset_samples = sync_result.offset_samples
        
        if offset_samples > 0:
            # Dub is delayed - trim master
            if offset_samples < len(master_audio):
                aligned_master = master_audio[offset_samples:]
                aligned_dub = dub_audio
            else:
                aligned_master = np.array([])
                aligned_dub = dub_audio
        elif offset_samples < 0:
            # Master is delayed - trim dub
            abs_offset = abs(offset_samples)
            if abs_offset < len(dub_audio):
                aligned_master = master_audio
                aligned_dub = dub_audio[abs_offset:]
            else:
                aligned_master = master_audio
                aligned_dub = np.array([])
        else:
            # No offset
            aligned_master = master_audio
            aligned_dub = dub_audio
        
        # Ensure same length
        min_len = min(len(aligned_master), len(aligned_dub))
        if min_len == 0:
            return {"sync_quality": 0.0, "spectral_similarity": 0.0, "temporal_stability": 0.0}
        
        aligned_master = aligned_master[:min_len]
        aligned_dub = aligned_dub[:min_len]
        
        # Extract features for quality assessment
        master_mfcc = librosa.feature.mfcc(y=aligned_master, sr=sr, n_mfcc=13)
        dub_mfcc = librosa.feature.mfcc(y=aligned_dub, sr=sr, n_mfcc=13)
        
        # Spectral similarity
        spectral_similarity = np.mean([
            cosine_similarity([master_mfcc[:, i]], [dub_mfcc[:, i]])[0, 0]
            for i in range(min(master_mfcc.shape[1], dub_mfcc.shape[1]))
        ])
        
        # Temporal stability (consistency over time)
        window_size = sr // 4  # 0.25 second windows
        similarities = []
        
        for start in range(0, min_len - window_size, window_size // 2):
            master_window = aligned_master[start:start + window_size]
            dub_window = aligned_dub[start:start + window_size]
            
            master_spec = np.abs(librosa.stft(master_window))
            dub_spec = np.abs(librosa.stft(dub_window))
            
            if master_spec.size > 0 and dub_spec.size > 0:
                # Resize to same shape
                min_frames = min(master_spec.shape[1], dub_spec.shape[1])
                master_spec = master_spec[:, :min_frames]
                dub_spec = dub_spec[:, :min_frames]
                
                # Flatten and compute similarity
                master_flat = master_spec.flatten()
                dub_flat = dub_spec.flatten()
                
                if len(master_flat) > 0 and len(dub_flat) > 0:
                    sim = cosine_similarity([master_flat], [dub_flat])[0, 0]
                    similarities.append(sim)
        
        temporal_stability = 1.0 - np.std(similarities) if similarities else 0.0
        
        # Overall sync quality
        sync_quality = (
            sync_result.confidence * 0.4 +
            spectral_similarity * 0.3 +
            temporal_stability * 0.3
        )
        
        return {
            "sync_quality": sync_quality,
            "spectral_similarity": spectral_similarity,
            "temporal_stability": temporal_stability,
            "embedding_similarity": sync_result.embedding_similarity,
            "temporal_consistency": sync_result.temporal_consistency
        }
