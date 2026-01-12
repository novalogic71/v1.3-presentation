"""
Audio Channel Layout Detection API
==================================

Endpoint for detecting audio channel layouts (5.1, stereo, 7.1, etc.)
by analyzing the actual audio content.

This solves the problem of files without channel tagging in containers.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any

from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class ChannelDetail(BaseModel):
    """Details for a single audio channel."""
    index: int
    rms_db: float
    peak_db: float
    low_freq_ratio: float = Field(description="Ratio of energy <120Hz (LFE indicator)")
    mid_freq_ratio: float = Field(description="Ratio of energy 300Hz-3kHz (dialogue indicator)")
    spectral_centroid_hz: float = Field(description="Brightness indicator")
    is_silent: bool
    assigned_role: str = Field(description="Detected role: L, R, C, LFE, Ls, Rs, etc.")


class DetectedPair(BaseModel):
    """A detected stereo pair."""
    channels: List[int]
    correlation: float = Field(description="Correlation coefficient 0-1")
    type: str = Field(description="Pair type: front_lr, surround_lr, unknown")


class ChannelLayoutResponse(BaseModel):
    """Response from channel layout detection."""
    success: bool
    channel_count: int
    layout_name: str = Field(description="Detected layout: 5.1, stereo, 7.1, etc.")
    channel_mapping: Dict[int, str] = Field(description="Channel index to role mapping")
    confidence: float = Field(description="Overall detection confidence 0-1")
    channel_confidences: Dict[int, float] = Field(description="Per-channel confidence scores")
    channel_details: List[ChannelDetail] = Field(description="Detailed analysis per channel")
    detected_pairs: List[DetectedPair] = Field(description="Detected stereo pairs")
    warnings: List[str] = Field(default_factory=list)
    
    # Summary for easy integration
    summary: str = Field(description="Human-readable summary")
    tag_suggestion: str = Field(description="Suggested tag for BOX system")


@router.post("/detect", response_model=ChannelLayoutResponse)
async def detect_channel_layout(
    file_path: str = Query(..., description="Path to audio/video file"),
    skip_seconds: float = Query(60.0, description="Seconds to skip at start (avoid bars/tone)"),
    analysis_duration: float = Query(60.0, description="Seconds of audio to analyze")
):
    """
    Detect the audio channel layout of a file.
    
    Analyzes the actual audio content to determine channel roles:
    - LFE detection via low-frequency ratio (<120Hz)
    - Center/dialogue detection via mid-band energy (300Hz-3kHz)
    - Stereo pair detection via pairwise correlation
    
    Returns channel mapping with confidence scores suitable for
    automatic tagging in BOX or other asset management systems.
    """
    import os
    
    # Validate file exists
    full_path = os.path.join(settings.MOUNT_PATH, file_path.lstrip('/'))
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    
    try:
        from sync_analyzer.core.audio_channel_detector import AudioChannelDetector
        
        detector = AudioChannelDetector(
            sample_rate=48000,
            analysis_duration=analysis_duration
        )
        
        result = detector.detect_layout(full_path, skip_seconds=skip_seconds)
        
        # Build response
        channel_details = [
            ChannelDetail(
                index=ch.channel_index,
                rms_db=round(ch.rms_level, 1),
                peak_db=round(ch.peak_level, 1),
                low_freq_ratio=round(ch.low_freq_ratio, 3),
                mid_freq_ratio=round(ch.mid_freq_ratio, 3),
                spectral_centroid_hz=round(ch.spectral_centroid, 0),
                is_silent=ch.is_silent,
                assigned_role=result.channel_mapping.get(ch.channel_index, "Unknown")
            )
            for ch in result.channel_analyses
        ]
        
        detected_pairs = [
            DetectedPair(
                channels=[pair.channel_a, pair.channel_b],
                correlation=round(pair.correlation, 3),
                type=pair.pair_type
            )
            for pair in result.detected_pairs
        ]
        
        # Generate summary and tag suggestion
        summary = _generate_summary(result)
        tag_suggestion = _generate_tag(result)
        
        return ChannelLayoutResponse(
            success=True,
            channel_count=result.channel_count,
            layout_name=result.layout_name,
            channel_mapping={str(k): v for k, v in result.channel_mapping.items()},
            confidence=round(result.confidence, 3),
            channel_confidences={str(k): round(v, 3) for k, v in result.channel_confidences.items()},
            channel_details=channel_details,
            detected_pairs=detected_pairs,
            warnings=result.warnings,
            summary=summary,
            tag_suggestion=tag_suggestion
        )
        
    except Exception as e:
        logger.exception(f"Channel detection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")


@router.get("/quick", response_model=Dict[str, Any])
async def quick_channel_detect(
    file_path: str = Query(..., description="Path to audio/video file")
):
    """
    Quick channel count and basic layout detection.
    
    Faster than full detection - just gets channel count and 
    makes a basic layout guess without detailed analysis.
    """
    import os
    import subprocess
    
    full_path = os.path.join(settings.MOUNT_PATH, file_path.lstrip('/'))
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    
    try:
        # Get channel count via ffprobe
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'a:0',
            '-show_entries', 'stream=channels,channel_layout',
            '-of', 'json',
            full_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail="FFprobe failed")
        
        import json
        probe_data = json.loads(result.stdout)
        
        if not probe_data.get('streams'):
            return {
                "success": False,
                "channel_count": 0,
                "layout_guess": "unknown",
                "container_layout": None,
                "needs_analysis": True
            }
        
        stream = probe_data['streams'][0]
        channel_count = stream.get('channels', 0)
        container_layout = stream.get('channel_layout', None)
        
        # Guess layout from count
        layout_guess = {
            1: "mono",
            2: "stereo",
            6: "5.1",
            8: "7.1"
        }.get(channel_count, f"{channel_count}ch")
        
        needs_analysis = container_layout is None or container_layout == ""
        
        return {
            "success": True,
            "channel_count": channel_count,
            "layout_guess": layout_guess,
            "container_layout": container_layout,
            "needs_analysis": needs_analysis,
            "message": "Full analysis recommended" if needs_analysis else "Container has layout tag"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Quick detection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")


def _generate_summary(result) -> str:
    """Generate a human-readable summary of the detection."""
    parts = [f"{result.channel_count}-channel audio detected as {result.layout_name}"]
    
    mapping_str = ", ".join([
        f"Ch{k}={v}" for k, v in sorted(result.channel_mapping.items())
    ])
    parts.append(f"Mapping: {mapping_str}")
    
    parts.append(f"Confidence: {result.confidence:.0%}")
    
    if result.warnings:
        parts.append(f"Warnings: {'; '.join(result.warnings)}")
    
    return " | ".join(parts)


def _generate_tag(result) -> str:
    """Generate a suggested tag for asset management systems."""
    # Standard naming convention for BOX/asset management
    if result.layout_name == "5.1":
        return "AUDIO_51_SURROUND"
    elif result.layout_name == "7.1":
        return "AUDIO_71_SURROUND"
    elif result.layout_name == "stereo":
        return "AUDIO_STEREO"
    elif result.layout_name == "mono":
        return "AUDIO_MONO"
    elif "5.1" in result.layout_name:
        return "AUDIO_51_PARTIAL"
    else:
        return f"AUDIO_{result.channel_count}CH_UNKNOWN"

