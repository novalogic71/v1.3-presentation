#!/usr/bin/env python3
"""
Simple Sync Reporter Implementation
==================================

A basic implementation of the sync reporter for testing purposes.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import logging
import numpy as np

logger = logging.getLogger(__name__)


def format_timecode(seconds: float, fps: float = 23.976) -> str:
    """
    Convert seconds to SMPTE timecode format HH:MM:SS:FF

    Args:
        seconds: Time in seconds (can be negative)
        fps: Frame rate (default: 23.976)

    Returns:
        Timecode string in format HH:MM:SS:FF
    """
    sign = '-' if seconds < 0 else ''
    abs_seconds = abs(seconds)

    hours = int(abs_seconds // 3600)
    minutes = int((abs_seconds % 3600) // 60)
    secs = int(abs_seconds % 60)
    frames = int((abs_seconds % 1) * fps)

    return f"{sign}{hours:02d}:{minutes:02d}:{secs:02d}:{frames:02d}"


def format_offset_display(offset_seconds: float, fps: float = 23.976) -> str:
    """
    Format offset for display with timecode and frame count

    Args:
        offset_seconds: Offset in seconds
        fps: Frame rate (default: 23.976)

    Returns:
        Formatted string like "00:00:15:00 (-360f @ 23.976fps)"
    """
    timecode = format_timecode(offset_seconds, fps)
    total_frames = round(abs(offset_seconds) * fps)
    frame_sign = '-' if offset_seconds < 0 else '+'
    return f"{timecode} ({frame_sign}{total_frames}f @ {fps}fps)"


class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder for numpy types."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

@dataclass
class SyncAnalysisReport:
    """Data class for sync analysis reports."""
    analysis_id: str
    master_file: str
    dub_file: str
    sync_results: Dict[str, Any]
    analysis_metadata: Dict[str, Any]
    recommendations: List[str]

class ProfessionalSyncReporter:
    """Simple sync reporter for generating JSON reports."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        """Initialize the reporter.
        
        Args:
            output_dir: Directory to save reports to. Defaults to current directory.
        """
        self.output_dir = Path(output_dir) if output_dir else Path(".")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Reports will be saved to: {self.output_dir}")
    
    def generate_report(self, sync_result: Any, master_file: Path, dub_file: Path, 
                       analysis_metadata: Optional[Dict[str, Any]] = None) -> SyncAnalysisReport:
        """Generate a sync analysis report.
        
        Args:
            sync_result: The sync detection result
            master_file: Path to master file
            dub_file: Path to dub file
            analysis_metadata: Additional metadata
            
        Returns:
            SyncAnalysisReport object
        """
        import datetime
        
        # Create analysis ID from timestamp
        analysis_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Convert sync result to dict with sensible fallbacks
        sync_data: Dict[str, Any]
        methods_from_meta = []
        detailed_from_meta = {}
        if analysis_metadata and isinstance(analysis_metadata, dict):
            sr = analysis_metadata.get("sync_results")
            if isinstance(sr, dict):
                methods_from_meta = list(sr.keys())
                detailed_from_meta = sr

        if hasattr(sync_result, '__dict__'):
            # Prefer common attribute names when present
            offset = getattr(sync_result, 'offset_seconds', None)
            if offset is None:
                offset = getattr(sync_result, 'consensus_offset_seconds', 0.0)
            confidence = getattr(sync_result, 'confidence', None)
            if confidence is None:
                confidence = getattr(sync_result, 'confidence_score', 0.0)

            sync_data = {
                "consensus_offset_seconds": float(offset or 0.0),
                "confidence_score": float(confidence or 0.0),
                "methods_used": methods_from_meta,
                "detailed_results": detailed_from_meta,
            }
        else:
            sync_data = {"raw_result": str(sync_result)}
        
        metadata = analysis_metadata or {}
        metadata.update({
            "timestamp": datetime.datetime.now().isoformat(),
            "analyzer_version": "1.0.0"
        })
        
        # Generate simple recommendations based on offset/confidence
        recs: List[str] = []
        try:
            off = float(sync_data.get("consensus_offset_seconds", 0.0))
            conf = float(sync_data.get("confidence_score", 0.0))
            if abs(off) < 0.01:
                recs.append("Audio appears synchronized")
            elif off > 0:
                recs.append(f"Dub audio is {off:.3f}s ahead of master")
            else:
                recs.append(f"Dub audio is {abs(off):.3f}s behind master")
            if conf >= 0.9:
                recs.append(f"Very high confidence ({conf:.0%})")
            elif conf >= 0.75:
                recs.append(f"High confidence ({conf:.0%})")
            elif conf >= 0.5:
                recs.append(f"Moderate confidence ({conf:.0%})")
            else:
                recs.append(f"Low confidence ({conf:.0%}) — consider re-analysis")
        except Exception:
            pass

        report = SyncAnalysisReport(
            analysis_id=analysis_id,
            master_file=str(master_file),
            dub_file=str(dub_file),
            sync_results=sync_data,
            analysis_metadata=metadata,
            recommendations=recs,
        )
        
        return report
    
    def save_json_report(self, report: SyncAnalysisReport) -> Path:
        """Save report as JSON file.
        
        Args:
            report: The report to save
            
        Returns:
            Path to saved file
        """
        filename = f"sync_report_{report.analysis_id}.json"
        filepath = self.output_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(asdict(report), f, indent=2, cls=NumpyEncoder)
        
        logger.info(f"Report saved to: {filepath}")
        return filepath
    
    def save_summary_report(self, report: SyncAnalysisReport) -> Path:
        """Save a human-readable summary report.
        
        Args:
            report: The report to save
            
        Returns:
            Path to saved file
        """
        filename = f"sync_summary_{report.analysis_id}.txt"
        filepath = self.output_dir / filename
        
        with open(filepath, 'w') as f:
            f.write(f"Audio Sync Analysis Report\n")
            f.write(f"========================\n\n")
            f.write(f"Analysis ID: {report.analysis_id}\n")
            f.write(f"Master File: {report.master_file}\n")
            f.write(f"Dub File: {report.dub_file}\n\n")
            
            sync_results = report.sync_results
            if 'consensus_offset_seconds' in sync_results:
                offset = sync_results['consensus_offset_seconds']
                f.write(f"Detected Offset: {format_offset_display(offset)}\n")

                if offset > 0:
                    f.write(f"  → Dub is ahead by {format_timecode(offset)}\n")
                elif offset < 0:
                    f.write(f"  → Dub is behind by {format_timecode(abs(offset))}\n")
                else:
                    f.write(f"  → Files are in sync\n")
            
            if 'confidence_score' in sync_results:
                confidence = sync_results['confidence_score']
                f.write(f"Confidence: {confidence:.2%}\n")
            
            f.write(f"\nGenerated: {report.analysis_metadata.get('timestamp', 'Unknown')}\n")
        
        logger.info(f"Summary saved to: {filepath}")
        return filepath
