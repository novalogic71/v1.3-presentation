#!/usr/bin/env python3
"""
Waveform Generator - Pre-generates waveform peak data for QC visualization.

Creates lightweight JSON files with peak/RMS data that can be loaded instantly
in the UI without needing to decode full audio files.
"""

import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class WaveformGenerator:
    """
    Generates waveform visualization data from audio/video files.
    
    Output is a JSON file containing peak and RMS data that can be
    rendered instantly in the browser without decoding audio.
    """
    
    def __init__(
        self,
        target_width: int = 2000,
        sample_rate: int = 22050,
        output_dir: Optional[Path] = None
    ):
        """
        Initialize waveform generator.
        
        Args:
            target_width: Number of data points in output (pixels)
            sample_rate: Sample rate for audio extraction
            output_dir: Directory to save waveform JSON files
        """
        self.target_width = target_width
        self.sample_rate = sample_rate
        self.output_dir = Path(output_dir) if output_dir else self._default_output_dir()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def _default_output_dir(self) -> Path:
        """Get default output directory."""
        project_root = Path(__file__).resolve().parent.parent.parent
        return project_root / "waveform_cache"
    
    def generate_waveform(
        self,
        file_path: str,
        output_name: Optional[str] = None,
        force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """
        Generate waveform data for a single audio/video file.
        
        Args:
            file_path: Path to audio/video file
            output_name: Optional custom name for output file
            force_regenerate: If True, regenerate even if cache exists
            
        Returns:
            Dictionary with waveform data
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Generate cache filename based on file path hash
        if output_name:
            cache_name = output_name
        else:
            # Use hash of absolute path for cache key
            import hashlib
            path_hash = hashlib.md5(str(file_path.resolve()).encode()).hexdigest()[:12]
            cache_name = f"{file_path.stem}_{path_hash}"
        
        cache_file = self.output_dir / f"{cache_name}.json"
        
        # Check cache
        if cache_file.exists() and not force_regenerate:
            try:
                with open(cache_file, 'r') as f:
                    cached = json.load(f)
                # Verify cache is valid
                if cached.get('source_path') == str(file_path) and 'peaks' in cached:
                    logger.info(f"Using cached waveform for {file_path.name}")
                    return cached
            except Exception as e:
                logger.warning(f"Cache read failed, regenerating: {e}")
        
        logger.info(f"Generating waveform for {file_path.name}...")
        
        # Extract audio and generate peaks
        try:
            audio_data, duration = self._extract_audio(file_path)
            peaks, rms = self._calculate_peaks(audio_data)
            
            waveform_data = {
                'source_path': str(file_path),
                'source_name': file_path.name,
                'duration': duration,
                'sample_rate': self.sample_rate,
                'width': len(peaks),
                'peaks': peaks.tolist(),
                'rms': rms.tolist(),
                'generated_at': self._timestamp()
            }
            
            # Save to cache
            with open(cache_file, 'w') as f:
                json.dump(waveform_data, f)
            
            logger.info(f"Waveform generated: {len(peaks)} points, {duration:.2f}s duration")
            return waveform_data
            
        except Exception as e:
            logger.error(f"Waveform generation failed for {file_path}: {e}")
            raise
    
    def generate_pair(
        self,
        master_path: str,
        dub_path: str,
        analysis_id: Optional[str] = None,
        force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """
        Generate waveform data for a master/dub pair.
        
        Args:
            master_path: Path to master file
            dub_path: Path to dub file
            analysis_id: Optional analysis ID for naming
            force_regenerate: If True, regenerate even if cache exists
            
        Returns:
            Dictionary with master and dub waveform data
        """
        master_name = f"{analysis_id}_master" if analysis_id else None
        dub_name = f"{analysis_id}_dub" if analysis_id else None
        
        master_waveform = self.generate_waveform(master_path, master_name, force_regenerate)
        dub_waveform = self.generate_waveform(dub_path, dub_name, force_regenerate)
        
        result = {
            'analysis_id': analysis_id,
            'master': master_waveform,
            'dub': dub_waveform,
            'generated_at': self._timestamp()
        }
        
        # Save combined file if analysis_id provided
        if analysis_id:
            combined_file = self.output_dir / f"{analysis_id}_waveforms.json"
            with open(combined_file, 'w') as f:
                json.dump(result, f)
            logger.info(f"Combined waveform saved to {combined_file}")
        
        return result
    
    def _extract_audio(self, file_path: Path) -> Tuple[np.ndarray, float]:
        """
        Extract audio from file using ffmpeg.
        
        Returns:
            Tuple of (audio_samples, duration_seconds)
        """
        with tempfile.NamedTemporaryFile(suffix='.raw', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            # Extract audio to raw PCM
            cmd = [
                'ffmpeg', '-y', '-i', str(file_path),
                '-ac', '1',  # Mono
                '-ar', str(self.sample_rate),
                '-f', 's16le',  # 16-bit signed little-endian PCM
                '-vn',  # No video
                tmp_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                stderr = result.stderr.decode('utf-8', errors='replace')
                raise RuntimeError(f"FFmpeg failed: {stderr[:500]}")
            
            # Read raw audio
            audio_data = np.fromfile(tmp_path, dtype=np.int16)
            audio_data = audio_data.astype(np.float32) / 32768.0  # Normalize to -1..1
            
            duration = len(audio_data) / self.sample_rate
            
            return audio_data, duration
            
        finally:
            # Clean up temp file
            try:
                Path(tmp_path).unlink()
            except Exception:
                pass
    
    def _calculate_peaks(self, audio_data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculate peak and RMS values for visualization.
        
        Returns:
            Tuple of (peaks_array, rms_array)
        """
        length = len(audio_data)
        samples_per_pixel = max(1, length // self.target_width)
        actual_width = min(self.target_width, length)
        
        peaks = np.zeros(actual_width, dtype=np.float32)
        rms = np.zeros(actual_width, dtype=np.float32)
        
        for i in range(actual_width):
            start = i * samples_per_pixel
            end = min(start + samples_per_pixel, length)
            
            if end > start:
                chunk = np.abs(audio_data[start:end])
                peaks[i] = np.max(chunk)
                rms[i] = np.sqrt(np.mean(chunk ** 2))
        
        return peaks, rms
    
    def _timestamp(self) -> str:
        """Get current timestamp string."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + 'Z'
    
    def get_cached_waveform(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Get cached waveform data if available.
        
        Args:
            file_path: Original file path
            
        Returns:
            Cached waveform data or None
        """
        import hashlib
        file_path = Path(file_path)
        path_hash = hashlib.md5(str(file_path.resolve()).encode()).hexdigest()[:12]
        cache_name = f"{file_path.stem}_{path_hash}"
        cache_file = self.output_dir / f"{cache_name}.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return None
        return None
    
    def clear_cache(self, older_than_days: Optional[int] = None) -> int:
        """
        Clear waveform cache.
        
        Args:
            older_than_days: If set, only clear files older than this
            
        Returns:
            Number of files deleted
        """
        count = 0
        cutoff = None
        
        if older_than_days:
            from datetime import datetime, timedelta
            cutoff = datetime.now() - timedelta(days=older_than_days)
        
        for cache_file in self.output_dir.glob('*.json'):
            try:
                if cutoff:
                    mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
                    if mtime >= cutoff:
                        continue
                cache_file.unlink()
                count += 1
            except Exception as e:
                logger.warning(f"Failed to delete {cache_file}: {e}")
        
        logger.info(f"Cleared {count} cached waveform files")
        return count


def generate_waveforms_for_analysis(
    master_path: str,
    dub_path: str,
    analysis_id: str,
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to generate waveforms for an analysis.

    Args:
        master_path: Path to master file
        dub_path: Path to dub file
        analysis_id: Analysis identifier
        output_dir: Optional output directory

    Returns:
        Dictionary with waveform data for both files
    """
    generator = WaveformGenerator(output_dir=Path(output_dir) if output_dir else None)
    return generator.generate_pair(master_path, dub_path, analysis_id)


def generate_componentized_waveforms(
    master_path: str,
    component_paths: List[str],
    analysis_id: str,
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate waveforms for componentized analysis (master + multiple components).

    Args:
        master_path: Path to master file
        component_paths: List of paths to component files
        analysis_id: Analysis identifier
        output_dir: Optional output directory

    Returns:
        Dictionary with master and all component waveform data
    """
    generator = WaveformGenerator(output_dir=Path(output_dir) if output_dir else None)

    # Generate master waveform
    master_name = f"{analysis_id}_master"
    master_waveform = generator.generate_waveform(master_path, master_name)

    # Generate component waveforms
    component_waveforms = []
    for idx, comp_path in enumerate(component_paths):
        comp_name = f"{analysis_id}_component_{idx}"
        try:
            comp_waveform = generator.generate_waveform(comp_path, comp_name)
            component_waveforms.append(comp_waveform)
        except Exception as e:
            logger.warning(f"Failed to generate waveform for component {idx}: {e}")

    result = {
        'analysis_id': analysis_id,
        'master': master_waveform,
        'components': component_waveforms,
        'generated_at': generator._timestamp()
    }

    logger.info(f"Generated componentized waveforms: 1 master + {len(component_waveforms)} components")
    return result


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python waveform_generator.py <master_file> <dub_file> [analysis_id]")
        sys.exit(1)
    
    master = sys.argv[1]
    dub = sys.argv[2]
    analysis_id = sys.argv[3] if len(sys.argv) > 3 else None
    
    logging.basicConfig(level=logging.INFO)
    
    result = generate_waveforms_for_analysis(master, dub, analysis_id or "test")
    print(f"Generated waveforms:")
    print(f"  Master: {result['master']['width']} points, {result['master']['duration']:.2f}s")
    print(f"  Dub: {result['dub']['width']} points, {result['dub']['duration']:.2f}s")

