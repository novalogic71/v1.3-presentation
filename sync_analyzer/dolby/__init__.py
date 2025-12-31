"""
Dolby Atmos Support Module

This module provides functionality for:
- Converting Dolby Atmos files (EC3/EAC3/ADM WAV) to MP4 format
- Extracting Atmos bed channels for audio analysis
- Preserving Atmos metadata throughout the sync analysis workflow
- Re-packaging repaired files with original Atmos format

Components:
    - mp4base_wrapper: Python wrapper for dlb_mp4base library
    - atmos_converter: Atmos to MP4 conversion pipeline
    - video_generator: Black video generation for MP4 containers
    - atmos_metadata: Atmos metadata extraction and parsing
"""

__version__ = "1.0.0"
__author__ = "Professional Audio Sync Analyzer"

from .atmos_converter import convert_atmos_to_mp4, is_atmos_file
from .video_generator import generate_black_video
from .atmos_metadata import extract_atmos_metadata, AtmosMetadata

__all__ = [
    "convert_atmos_to_mp4",
    "is_atmos_file",
    "generate_black_video",
    "extract_atmos_metadata",
    "AtmosMetadata",
]
