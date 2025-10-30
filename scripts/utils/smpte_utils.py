#!/usr/bin/env python3
"""
SMPTE Timecode Utilities for Professional Audio/Video Sync Analysis

Provides comprehensive SMPTE timecode support including:
- Frame rate detection and conversion
- Seconds to SMPTE timecode conversion
- SMPTE timecode parsing and manipulation
- Drop-frame and non-drop-frame support
"""

import re
import subprocess
import json
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TimecodeInfo:
    """SMPTE timecode information container."""
    hours: int
    minutes: int
    seconds: int
    frames: int
    frame_rate: float
    drop_frame: bool = False
    
    def __str__(self) -> str:
        """Convert to SMPTE timecode string (HH:MM:SS:FF or HH:MM:SS;FF for drop-frame)."""
        separator = ";" if self.drop_frame else ":"
        return f"{self.hours:02d}:{self.minutes:02d}:{self.seconds:02d}{separator}{self.frames:02d}"
    
    def to_seconds(self) -> float:
        """Convert SMPTE timecode to total seconds."""
        total_seconds = (self.hours * 3600 + 
                        self.minutes * 60 + 
                        self.seconds + 
                        self.frames / self.frame_rate)
        
        # Handle drop-frame compensation for 29.97fps
        if self.drop_frame and abs(self.frame_rate - 29.97) < 0.01:
            # Drop frame calculation: 2 frames dropped every minute except every 10th minute
            total_minutes = self.hours * 60 + self.minutes
            dropped_frames = 2 * (total_minutes - (total_minutes // 10))
            adjustment = dropped_frames / self.frame_rate
            total_seconds -= adjustment
            
        return total_seconds


class SMPTEUtils:
    """Utility class for SMPTE timecode operations."""
    
    # Common frame rates in professional video
    FRAME_RATES = {
        23.976: "23.976 fps (Film)",
        24.0: "24 fps (Cinema)",
        25.0: "25 fps (PAL)",
        29.97: "29.97 fps (NTSC Drop-Frame)",
        30.0: "30 fps (NTSC Non-Drop)",
        50.0: "50 fps (PAL Progressive)",
        59.94: "59.94 fps (NTSC Progressive)",
        60.0: "60 fps (High Frame Rate)"
    }
    
    @staticmethod
    def extract_media_metadata(file_path: str) -> Dict[str, Any]:
        """
        Extract comprehensive media metadata including SMPTE timecode information.
        
        Args:
            file_path: Path to the media file
            
        Returns:
            Dictionary containing metadata including timecode, frame rate, duration
        """
        try:
            # Use ffprobe to get detailed media information
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json", 
                "-show_format",
                "-show_streams",
                "-show_chapters",
                file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return {"error": f"ffprobe failed: {result.stderr}"}
                
            data = json.loads(result.stdout)
            metadata = {
                "file_path": file_path,
                "file_name": Path(file_path).name
            }
            
            # Extract format information
            if "format" in data:
                format_info = data["format"]
                metadata.update({
                    "duration": float(format_info.get("duration", 0)),
                    "size": int(format_info.get("size", 0)),
                    "bit_rate": int(format_info.get("bit_rate", 0)),
                    "format_name": format_info.get("format_name", "unknown")
                })
                
                # Look for timecode in format tags
                tags = format_info.get("tags", {})
                metadata.update(SMPTEUtils._extract_timecode_from_tags(tags))
            
            # Extract stream information
            if "streams" in data:
                video_streams = [s for s in data["streams"] if s.get("codec_type") == "video"]
                audio_streams = [s for s in data["streams"] if s.get("codec_type") == "audio"]
                
                # Video stream info
                if video_streams:
                    video = video_streams[0]  # Use first video stream
                    metadata.update(SMPTEUtils._extract_video_info(video))
                
                # Audio stream info
                if audio_streams:
                    audio = audio_streams[0]  # Use first audio stream
                    metadata.update(SMPTEUtils._extract_audio_info(audio))
            
            return metadata
            
        except Exception as e:
            return {"error": f"Failed to extract metadata: {str(e)}"}
    
    @staticmethod
    def _extract_timecode_from_tags(tags: Dict[str, str]) -> Dict[str, Any]:
        """Extract timecode information from format/stream tags."""
        timecode_info = {}
        
        # Common timecode tag names
        timecode_keys = [
            "timecode", "TIMECODE", "Timecode",
            "time_code", "TIME_CODE", "TimeCode",
            "tc", "TC"
        ]
        
        for key in timecode_keys:
            if key in tags:
                tc_string = tags[key]
                parsed_tc = SMPTEUtils.parse_timecode_string(tc_string)
                if parsed_tc:
                    timecode_info.update({
                        "source_timecode": tc_string,
                        "source_timecode_parsed": parsed_tc,
                        "source_start_seconds": parsed_tc.to_seconds()
                    })
                break
        
        return timecode_info
    
    @staticmethod
    def _extract_video_info(video_stream: Dict[str, Any]) -> Dict[str, Any]:
        """Extract video stream information including frame rate."""
        video_info = {
            "video_codec": video_stream.get("codec_name", "unknown"),
            "width": int(video_stream.get("width", 0)),
            "height": int(video_stream.get("height", 0)),
            "pix_fmt": video_stream.get("pix_fmt", "unknown")
        }
        
        # Extract frame rate
        fps_str = video_stream.get("r_frame_rate", "0/1")
        if "/" in fps_str:
            try:
                num, den = fps_str.split("/")
                frame_rate = float(num) / float(den) if float(den) != 0 else 0
                video_info["frame_rate"] = round(frame_rate, 3)
                video_info["frame_rate_description"] = SMPTEUtils.FRAME_RATES.get(
                    round(frame_rate, 3), f"{frame_rate:.3f} fps"
                )
            except (ValueError, ZeroDivisionError):
                video_info["frame_rate"] = 0
        
        # Check for timecode in video stream tags
        tags = video_stream.get("tags", {})
        video_info.update(SMPTEUtils._extract_timecode_from_tags(tags))
        
        return video_info
    
    @staticmethod
    def _extract_audio_info(audio_stream: Dict[str, Any]) -> Dict[str, Any]:
        """Extract audio stream information."""
        return {
            "audio_codec": audio_stream.get("codec_name", "unknown"),
            "sample_rate": int(audio_stream.get("sample_rate", 0)),
            "channels": int(audio_stream.get("channels", 0)),
            "channel_layout": audio_stream.get("channel_layout", "unknown")
        }
    
    @staticmethod
    def parse_timecode_string(timecode_str: str) -> Optional[TimecodeInfo]:
        """
        Parse SMPTE timecode string into TimecodeInfo object.
        
        Supports formats:
        - HH:MM:SS:FF (non-drop frame)
        - HH:MM:SS;FF (drop frame)
        - HH:MM:SS.mmm (milliseconds)
        
        Args:
            timecode_str: Timecode string to parse
            
        Returns:
            TimecodeInfo object or None if parsing fails
        """
        if not timecode_str:
            return None
            
        # Try SMPTE format (HH:MM:SS:FF or HH:MM:SS;FF)
        smpte_pattern = r"^(\d{2}):(\d{2}):(\d{2})[:;](\d{2})$"
        match = re.match(smpte_pattern, timecode_str)
        
        if match:
            hours, minutes, seconds, frames = map(int, match.groups())
            drop_frame = ";" in timecode_str
            
            # Default frame rate - should be provided by context
            frame_rate = 29.97 if drop_frame else 30.0
            
            return TimecodeInfo(
                hours=hours,
                minutes=minutes, 
                seconds=seconds,
                frames=frames,
                frame_rate=frame_rate,
                drop_frame=drop_frame
            )
        
        # Try milliseconds format (HH:MM:SS.mmm)
        ms_pattern = r"^(\d{2}):(\d{2}):(\d{2})\.(\d{3})$"
        match = re.match(ms_pattern, timecode_str)
        
        if match:
            hours, minutes, seconds, ms = map(int, match.groups())
            # Convert milliseconds to frames (assuming 30fps)
            frame_rate = 30.0
            frames = int((ms / 1000.0) * frame_rate)
            
            return TimecodeInfo(
                hours=hours,
                minutes=minutes,
                seconds=seconds, 
                frames=frames,
                frame_rate=frame_rate,
                drop_frame=False
            )
        
        return None
    
    @staticmethod
    def seconds_to_timecode(seconds: float, frame_rate: float = 30.0, 
                          drop_frame: bool = False, start_tc: Optional[TimecodeInfo] = None) -> TimecodeInfo:
        """
        Convert seconds to SMPTE timecode.
        
        Args:
            seconds: Time in seconds
            frame_rate: Frame rate for conversion
            drop_frame: Whether to use drop-frame format
            start_tc: Starting timecode (if file has embedded timecode)
            
        Returns:
            TimecodeInfo object
        """
        if start_tc:
            # Add offset to starting timecode
            total_seconds = start_tc.to_seconds() + seconds
        else:
            total_seconds = seconds
        
        # Handle drop-frame compensation for 29.97fps
        if drop_frame and abs(frame_rate - 29.97) < 0.01:
            # Compensate for dropped frames
            minutes = int(total_seconds // 60)
            dropped_frames = 2 * (minutes - (minutes // 10))
            total_seconds += dropped_frames / frame_rate
        
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        secs = int(total_seconds % 60)
        frames = int((total_seconds % 1) * frame_rate)
        
        return TimecodeInfo(
            hours=hours,
            minutes=minutes,
            seconds=secs,
            frames=frames,
            frame_rate=frame_rate,
            drop_frame=drop_frame
        )
    
    @staticmethod
    def format_time_range(start_seconds: float, end_seconds: float, 
                         frame_rate: float = 30.0, start_tc: Optional[TimecodeInfo] = None) -> str:
        """
        Format a time range using SMPTE timecodes.
        
        Args:
            start_seconds: Start time in seconds
            end_seconds: End time in seconds  
            frame_rate: Frame rate for conversion
            start_tc: Starting timecode reference
            
        Returns:
            Formatted time range string
        """
        start_tc_obj = SMPTEUtils.seconds_to_timecode(start_seconds, frame_rate, start_tc=start_tc)
        end_tc_obj = SMPTEUtils.seconds_to_timecode(end_seconds, frame_rate, start_tc=start_tc)
        
        return f"{start_tc_obj} - {end_tc_obj}"
    
    @staticmethod
    def detect_frame_rate(file_path: str) -> float:
        """
        Detect frame rate from media file.
        
        Args:
            file_path: Path to media file
            
        Returns:
            Frame rate as float, defaults to 30.0 if detection fails
        """
        try:
            metadata = SMPTEUtils.extract_media_metadata(file_path)
            return metadata.get("frame_rate", 30.0)
        except Exception:
            return 30.0
    
    @staticmethod
    def get_source_timecode(file_path: str) -> Optional[TimecodeInfo]:
        """
        Extract source timecode from media file if available.
        
        Args:
            file_path: Path to media file
            
        Returns:
            TimecodeInfo object if found, None otherwise
        """
        try:
            metadata = SMPTEUtils.extract_media_metadata(file_path)
            return metadata.get("source_timecode_parsed")
        except Exception:
            return None


# Convenience functions for backward compatibility
def format_time(seconds: float, frame_rate: float = 30.0) -> str:
    """Convert seconds to SMPTE timecode string."""
    tc = SMPTEUtils.seconds_to_timecode(seconds, frame_rate)
    return str(tc)


def format_time_range(start_seconds: float, end_seconds: float, frame_rate: float = 30.0) -> str:
    """Format time range as SMPTE timecode range."""
    return SMPTEUtils.format_time_range(start_seconds, end_seconds, frame_rate)


if __name__ == "__main__":
    # Test functionality
    print("SMPTE Timecode Utilities Test")
    print("=" * 50)
    
    # Test timecode parsing
    test_timecodes = ["01:23:45:12", "02:30:15;29", "00:15:30.500"]
    for tc_str in test_timecodes:
        parsed = SMPTEUtils.parse_timecode_string(tc_str)
        if parsed:
            print(f"Parsed '{tc_str}' -> {parsed} ({parsed.to_seconds():.3f}s)")
    
    # Test seconds to timecode conversion
    test_seconds = [0, 90.5, 3661.75, 7322.333]
    for sec in test_seconds:
        tc = SMPTEUtils.seconds_to_timecode(sec, 29.97, drop_frame=True)
        print(f"{sec}s -> {tc}")
    
    print("\nTest completed!")