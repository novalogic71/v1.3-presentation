#!/usr/bin/env python3
"""
Operator-Friendly Timeline Display Module

Transforms technical sync analysis data into clear, visual, actionable information
that operators can immediately understand and act upon.
"""

import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import math

class OperatorTimeline:
    """
    Enhanced timeline display system designed for operators and editors
    """

    def __init__(self):
        self.severity_indicators = {
            'IN_SYNC': '🟢',
            'MINOR_DRIFT': '🟡',
            'SYNC_ISSUE': '🟠',
            'MAJOR_DRIFT': '🔴',
            'NO_DATA': '❓'
        }

        self.reliability_indicators = {
            'RELIABLE': '✅',
            'UNCERTAIN': '⚠️',
            'PROBLEM': '🔴',
            'NO_DATA': '❓'
        }

        # Sync tolerance thresholds (in seconds)
        self.sync_thresholds = {
            'perfect': 0.040,      # ≤40ms - broadcast standard
            'minor': 0.100,        # 40-100ms - noticeable but acceptable
            'issue': 1.000,        # 100ms-1s - needs correction
            'major': float('inf')  # >1s - critical problem
        }

    def format_time_range(self, start_seconds: float, end_seconds: float) -> str:
        """Format time range for operator display (MM:SS or HH:MM:SS)"""
        def format_single_time(seconds: float) -> str:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)

            if hours > 0:
                return f"{hours:d}:{minutes:02d}:{secs:02d}"
            else:
                return f"{minutes:d}:{secs:02d}"

        return f"{format_single_time(start_seconds)}-{format_single_time(end_seconds)}"

    def classify_sync_severity(self, offset_seconds: float) -> Tuple[str, str, str]:
        """
        Classify sync offset into operator-friendly categories

        Returns:
            Tuple of (severity_level, indicator, description)
        """
        abs_offset = abs(offset_seconds)
        offset_ms = abs_offset * 1000

        if abs_offset <= self.sync_thresholds['perfect']:
            return 'IN_SYNC', self.severity_indicators['IN_SYNC'], f"Perfect sync"
        elif abs_offset <= self.sync_thresholds['minor']:
            return 'MINOR_DRIFT', self.severity_indicators['MINOR_DRIFT'], f"+{offset_ms:.0f}ms drift"
        elif abs_offset <= self.sync_thresholds['issue']:
            return 'SYNC_ISSUE', self.severity_indicators['SYNC_ISSUE'], f"+{offset_ms:.0f}ms drift"
        else:
            return 'MAJOR_DRIFT', self.severity_indicators['MAJOR_DRIFT'], f"+{abs_offset:.1f}s offset"

    def classify_reliability(self, chunk_data: Dict[str, Any]) -> Tuple[str, str, str]:
        """
        Convert technical quality metrics to operator-friendly reliability

        Returns:
            Tuple of (reliability_level, indicator, explanation)
        """
        confidence = chunk_data.get('confidence', chunk_data.get('ensemble_confidence', 0))
        quality = chunk_data.get('quality', 'Poor')
        similarities = chunk_data.get('similarities', {})

        # Skip/silence handling
        if similarities.get('skipped') or quality == 'Skipped':
            return 'NO_DATA', self.reliability_indicators['NO_DATA'], "Unable to analyze"

        # Enhanced reliability assessment
        if confidence >= 0.7 and quality in ['Excellent', 'Good']:
            return 'RELIABLE', self.reliability_indicators['RELIABLE'], "High-confidence measurement"
        elif confidence >= 0.4 and quality in ['Excellent', 'Good', 'Fair']:
            return 'UNCERTAIN', self.reliability_indicators['UNCERTAIN'], "Low-confidence, needs review"
        else:
            return 'PROBLEM', self.reliability_indicators['PROBLEM'], "Sync issue detected"

    def classify_scene_content(self, chunk_data: Dict[str, Any]) -> Tuple[str, str]:
        """
        Classify scene content for operator understanding

        Returns:
            Tuple of (scene_type, description)
        """
        master_content = chunk_data.get('master_content', {})
        content_type = master_content.get('content_type', 'unknown')

        scene_mapping = {
            'dialogue': ('Dialogue Scene', '🎭'),
            'music': ('Music Scene', '🎵'),
            'mixed': ('Mixed Content', '🎬'),
            'silence': ('Silence/Pause', '🔇'),
            'unknown': ('Unknown Content', '❓')
        }

        scene_type, icon = scene_mapping.get(content_type, ('Unknown Content', '❓'))
        return scene_type, f"{icon} {scene_type}"

    def get_repair_recommendation(self, chunk_data: Dict[str, Any], severity: str, reliability: str) -> Dict[str, str]:
        """
        Generate actionable repair recommendations for operators

        Returns:
            Dictionary with action, priority, and description
        """
        offset_seconds = chunk_data.get('offset_detection', {}).get('offset_seconds', 0)
        scene_type, _ = self.classify_scene_content(chunk_data)

        # Determine repair action based on severity and reliability
        if severity == 'MAJOR_DRIFT' and reliability in ['RELIABLE', 'UNCERTAIN']:
            if abs(offset_seconds) > 2.0:
                action = "MANUAL REVIEW"
                priority = "HIGH"
                description = f"Large drift requires manual adjustment"
            else:
                action = "AUTO-REPAIR"
                priority = "HIGH"
                description = f"Simple offset correction available"

        elif severity == 'SYNC_ISSUE':
            if 'Dialogue' in scene_type:
                action = "AUTO-REPAIR"
                priority = "MEDIUM-HIGH"
                description = f"Critical for lip sync accuracy"
            else:
                action = "MANUAL REVIEW"
                priority = "MEDIUM"
                description = f"Correction recommended"

        elif severity == 'MINOR_DRIFT':
            if 'Dialogue' in scene_type:
                action = "MONITOR"
                priority = "LOW-MEDIUM"
                description = f"Minor drift in dialogue scene"
            else:
                action = "MONITOR ONLY"
                priority = "LOW"
                description = f"Within acceptable limits"

        else:  # IN_SYNC
            action = "NO ACTION"
            priority = "NONE"
            description = f"Good sync quality"

        return {
            'action': action,
            'priority': priority,
            'description': description,
            'scene_context': scene_type
        }

    def create_scene_timeline(self, analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Create operator-friendly scene-based timeline

        Returns:
            List of scene segments with operator-friendly information
        """
        timeline = analysis_result.get('timeline', [])
        combined_chunks = analysis_result.get('combined_chunks', timeline)

        if not combined_chunks:
            return []

        scenes = []
        for chunk in combined_chunks:
            # Extract timing info
            start_time = chunk.get('start_time', 0)
            end_time = chunk.get('end_time', start_time + 30)

            # Get offset info
            offset_detection = chunk.get('offset_detection', {})
            offset_seconds = offset_detection.get('offset_seconds', 0)

            # Classify for operators
            severity, sev_indicator, sev_description = self.classify_sync_severity(offset_seconds)
            reliability, rel_indicator, rel_explanation = self.classify_reliability(chunk)
            scene_type, scene_description = self.classify_scene_content(chunk)
            repair_rec = self.get_repair_recommendation(chunk, severity, reliability)

            scene_data = {
                'time_range': self.format_time_range(start_time, end_time),
                'start_seconds': start_time,
                'end_seconds': end_time,
                'scene_type': scene_type,
                'scene_description': scene_description,
                'severity': severity,
                'severity_indicator': sev_indicator,
                'severity_description': sev_description,
                'reliability': reliability,
                'reliability_indicator': rel_indicator,
                'reliability_explanation': rel_explanation,
                'offset_seconds': offset_seconds,
                'repair_recommendation': repair_rec,
                'raw_chunk_data': chunk  # Keep for advanced users
            }

            scenes.append(scene_data)

        return scenes

    def print_operator_timeline(self, analysis_result: Dict[str, Any], file_name: str = ""):
        """
        Print comprehensive operator-friendly timeline analysis
        """
        scenes = self.create_scene_timeline(analysis_result)

        if not scenes:
            print("❌ No timeline data available for analysis")
            return

        duration = analysis_result.get('master_duration', analysis_result.get('dub_duration', 0))
        total_time = self.format_time_range(0, duration) if duration > 0 else "Unknown"

        print("\n" + "═" * 80)
        print(f"📺 SYNC TIMELINE ANALYSIS{f' - {file_name}' if file_name else ''} ({total_time} total)")
        print("═" * 80)

        # Scene breakdown
        print(f"\n🎬 SCENE BREAKDOWN:")
        for scene in scenes:
            print(f"   {scene['time_range']:>12}  {scene['scene_description']:18} "
                  f"{scene['severity_indicator']} {scene['severity']:12} {scene['severity_description']}")

        # Problem summary
        self._print_problem_summary(scenes)

        # Repair recommendations
        self._print_repair_recommendations(scenes)

        # ASCII timeline visualization
        self._print_ascii_timeline(scenes, duration)

    def _print_problem_summary(self, scenes: List[Dict[str, Any]]):
        """Print prioritized problem summary"""
        # Count issues by severity
        severity_counts = {'MAJOR_DRIFT': 0, 'SYNC_ISSUE': 0, 'MINOR_DRIFT': 0, 'IN_SYNC': 0}
        critical_scenes = []
        moderate_scenes = []
        minor_scenes = []

        for scene in scenes:
            severity = scene['severity']
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

            if severity == 'MAJOR_DRIFT':
                critical_scenes.append(scene)
            elif severity == 'SYNC_ISSUE':
                moderate_scenes.append(scene)
            elif severity == 'MINOR_DRIFT':
                minor_scenes.append(scene)

        print(f"\n📊 PROBLEM SUMMARY:")

        if critical_scenes:
            print(f"   🔴 {len(critical_scenes)} Critical Issue{'s' if len(critical_scenes) > 1 else ''}:")
            for scene in critical_scenes[:3]:  # Show max 3
                print(f"      → {scene['time_range']}: {scene['severity_description']} in {scene['scene_type'].lower()}")

        if moderate_scenes:
            print(f"   🟠 {len(moderate_scenes)} Moderate Issue{'s' if len(moderate_scenes) > 1 else ''}:")
            for scene in moderate_scenes[:3]:  # Show max 3
                print(f"      → {scene['time_range']}: {scene['severity_description']} in {scene['scene_type'].lower()}")

        if minor_scenes:
            print(f"   🟡 {len(minor_scenes)} Minor Issue{'s' if len(minor_scenes) > 1 else ''}:")
            for scene in minor_scenes[:2]:  # Show max 2
                print(f"      → {scene['time_range']}: {scene['severity_description']} in {scene['scene_type'].lower()}")

        good_count = severity_counts.get('IN_SYNC', 0)
        if good_count > 0:
            print(f"   🟢 {good_count} Good Section{'s' if good_count > 1 else ''}     : No issues detected")

    def _print_repair_recommendations(self, scenes: List[Dict[str, Any]]):
        """Print actionable repair recommendations"""
        # Group by action type
        immediate_actions = []
        review_needed = []
        monitor_only = []

        for scene in scenes:
            repair_rec = scene['repair_recommendation']
            priority = repair_rec['priority']

            if priority in ['HIGH', 'MEDIUM-HIGH']:
                immediate_actions.append(scene)
            elif priority in ['MEDIUM', 'LOW-MEDIUM']:
                review_needed.append(scene)
            elif priority in ['LOW']:
                monitor_only.append(scene)

        print(f"\n⚡ REPAIR RECOMMENDATIONS:")

        if immediate_actions:
            print(f"   🚨 IMMEDIATE ACTION REQUIRED:")
            for scene in immediate_actions:
                repair_rec = scene['repair_recommendation']
                print(f"      → Scene {scene['time_range']}: {scene['severity_description']}")
                print(f"        Action: {repair_rec['action']}")
                print(f"        Priority: {repair_rec['priority']} ({repair_rec['description']})")
                print()

        if review_needed:
            print(f"   ⚠️ REVIEW RECOMMENDED:")
            for scene in review_needed:
                repair_rec = scene['repair_recommendation']
                print(f"      → Scene {scene['time_range']}: {repair_rec['description']}")
                print(f"        Action: {repair_rec['action']} (Priority: {repair_rec['priority']})")
                print()

        if monitor_only:
            print(f"   📝 MONITOR ONLY:")
            for scene in monitor_only[:3]:  # Limit to 3
                repair_rec = scene['repair_recommendation']
                print(f"      → Scene {scene['time_range']}: {repair_rec['description']}")
            if len(monitor_only) > 3:
                print(f"      ... and {len(monitor_only) - 3} more sections")

    def _print_ascii_timeline(self, scenes: List[Dict[str, Any]], total_duration: float):
        """Print ASCII visualization of sync drift over time"""
        if not scenes or total_duration <= 0:
            return

        print(f"\nSYNC DRIFT OVER TIME:")

        # Calculate drift range
        offsets = [scene['offset_seconds'] for scene in scenes if scene['offset_seconds'] != 0]
        if not offsets:
            print("   No significant drift detected")
            return

        max_offset = max(abs(o) for o in offsets)
        scale_factor = max(2.0, max_offset * 1.2)  # At least ±2s scale

        # Create ASCII chart
        chart_height = 9
        chart_width = 60

        # Create vertical scale
        scale_steps = [-scale_factor, -scale_factor/2, 0, scale_factor/2, scale_factor]

        print("      " + " " * 10 + "|" + " " * (chart_width-10))
        for i, scale_val in enumerate(reversed(scale_steps)):
            row_char = "|" if scale_val != 0 else "+"

            # Plot points for this row
            line = " " * chart_width
            for scene in scenes:
                offset = scene['offset_seconds']
                time_pos = int((scene['start_seconds'] / total_duration) * (chart_width - 1))

                # Check if this offset falls in this row's range
                row_min = scale_val - scale_factor/8
                row_max = scale_val + scale_factor/8

                if row_min <= offset <= row_max:
                    severity = scene['severity']
                    if severity == 'MAJOR_DRIFT':
                        char = '█'
                    elif severity == 'SYNC_ISSUE':
                        char = '▓'
                    elif severity == 'MINOR_DRIFT':
                        char = '▒'
                    else:
                        char = '░'

                    line = line[:time_pos] + char + line[time_pos+1:]

            print(f"{scale_val:+5.1f}s {row_char}{line}")

        # Time axis
        time_markers = []
        for i in range(0, chart_width, 10):
            time_pos = (i / chart_width) * total_duration
            time_markers.append(f"{time_pos/60:.0f}:{(time_pos%60):02.0f}")

        print("      " + "|" + "-" * (chart_width-1))
        marker_line = "      |"
        for i, marker in enumerate(time_markers):
            pos = i * 10
            if pos < chart_width:
                marker_line += f"{marker:>8}"[:8].ljust(10-len(marker_line)%10)[:10]
        print(marker_line)

        # Legend
        print(f"\n      Legend: 🟢 IN_SYNC  🟡 MINOR  🟠 ISSUE  🔴 MAJOR")