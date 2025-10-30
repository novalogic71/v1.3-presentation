#!/usr/bin/env python3
"""
Sync Report Analyzer - Creates formatted analysis reports from sync analysis data
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Tuple

def format_time_range(start_seconds: float, end_seconds: float) -> str:
    """Format time range in minutes"""
    start_min = start_seconds / 60
    end_min = end_seconds / 60
    return f"{start_min:.1f}-{end_min:.1f} min"

def format_time_minutes(seconds: float) -> str:
    """Format time in minutes"""
    return f"{seconds/60:.1f} min"

def classify_similarity(similarity: float) -> str:
    """Classify similarity score"""
    if similarity >= 0.750:
        return "excellent"
    elif similarity >= 0.600:
        return "good"  
    elif similarity >= 0.450:
        return "fair"
    elif similarity >= 0.300:
        return "poor"
    else:
        return "very poor"

def analyze_drift_phases(timeline: List[Dict]) -> List[Dict]:
    """Analyze timeline to identify drift phases"""
    if not timeline:
        return []
    
    phases = []
    current_phase = None
    
    for i, chunk in enumerate(timeline):
        similarity = chunk.get('confidence', 0.0)  # Using confidence as similarity proxy
        chunk_num = i + 1
        start_time = chunk.get('start_time', 0)
        
        # Determine phase type based on similarity
        if similarity >= 0.750:
            phase_type = "perfect_sync"
        elif similarity >= 0.600:
            phase_type = "good_sync"
        elif similarity >= 0.450:
            phase_type = "degraded_sync"
        elif similarity >= 0.300:
            phase_type = "poor_sync"
        else:
            phase_type = "critical_drift"
        
        # Start new phase or continue current one
        if current_phase is None or current_phase['type'] != phase_type:
            if current_phase:
                current_phase['end_chunk'] = chunk_num - 1
                current_phase['end_time'] = timeline[chunk_num-2]['start_time'] + timeline[chunk_num-2].get('duration', 45)
                phases.append(current_phase)
            
            current_phase = {
                'type': phase_type,
                'start_chunk': chunk_num,
                'start_time': start_time,
                'similarities': [similarity],
                'chunks': [chunk_num]
            }
        else:
            current_phase['similarities'].append(similarity)
            current_phase['chunks'].append(chunk_num)
    
    # Close final phase
    if current_phase:
        current_phase['end_chunk'] = len(timeline)
        current_phase['end_time'] = timeline[-1]['start_time'] + timeline[-1].get('duration', 45)
        phases.append(current_phase)
    
    return phases

def generate_formatted_report(json_file: str, episode_name: str = None) -> str:
    """Generate a formatted sync analysis report"""
    
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
    except Exception as e:
        return f"Error reading analysis file: {e}"
    
    timeline = data.get('timeline', [])
    if not timeline:
        return "No timeline data found in analysis"
    
    report_lines = []
    
    # Header
    episode = episode_name or Path(json_file).stem
    total_chunks = len(timeline)
    report_lines.append(f"📊 **{episode} Sync Analysis Report**")
    report_lines.append("=" * 60)
    report_lines.append("")
    
    # Basic stats
    file_duration = data.get('master_duration', 0)
    reliable_chunks = [t for t in timeline if t.get('reliable', False)]

    report_lines.append(f"**File Duration:** {format_time_minutes(file_duration)}")
    report_lines.append(f"**Total Chunks Analyzed:** {total_chunks}")
    report_lines.append(f"**Reliable Chunks:** {len(reliable_chunks)}/{total_chunks} ({len(reliable_chunks)/total_chunks*100:.1f}%)")
    report_lines.append("")

    # Offset Summary
    overall_offset = data.get('offset_seconds', 0)
    drift_analysis = data.get('drift_analysis', {})
    has_drift = drift_analysis.get('has_drift', False)
    drift_magnitude = drift_analysis.get('drift_magnitude', 0)
    offset_range = drift_analysis.get('offset_range', {})

    report_lines.append("## 📊 **Sync Offset Summary:**")
    report_lines.append("")
    report_lines.append(f"**Overall Offset:** {overall_offset:+.3f}s ({abs(overall_offset)*24:+.0f}f @ 24fps)")
    if has_drift and drift_magnitude > 0:
        report_lines.append(f"**Drift Detected:** Yes - {drift_magnitude:.2f}s variation across file")
        min_offset = offset_range.get('min', 0)
        max_offset = offset_range.get('max', 0)
        report_lines.append(f"**Offset Range:** {min_offset:+.2f}s to {max_offset:+.2f}s")
    else:
        report_lines.append(f"**Drift Detected:** No - constant offset throughout file")
    report_lines.append("")
    
    # Analyze phases
    phases = analyze_drift_phases(timeline)
    
    # Phase analysis
    report_lines.append("## 🔍 **Sync Drift Analysis by Phases:**")
    report_lines.append("")
    
    phase_counter = 1
    critical_regions = []
    
    for phase in phases:
        avg_similarity = sum(phase['similarities']) / len(phase['similarities'])
        time_range = format_time_range(phase['start_time'], phase['end_time'])
        chunk_range = f"Chunks {phase['start_chunk']}-{phase['end_chunk']}"
        
        if phase['type'] == 'perfect_sync':
            icon = "✅"
            description = f"**Perfect Sync Phase** ({time_range}): {chunk_range} at consistent {avg_similarity:.3f} similarity"
        elif phase['type'] == 'good_sync':
            icon = "🟢" 
            description = f"**Good Sync Phase** ({time_range}): {chunk_range} at {avg_similarity:.3f} similarity"
        elif phase['type'] == 'degraded_sync':
            icon = "🟡"
            description = f"**Degraded Sync Phase** ({time_range}): {chunk_range} - similarity drops to {avg_similarity:.3f}"
            critical_regions.append({
                'time_range': time_range,
                'chunks': chunk_range,
                'similarity': avg_similarity,
                'severity': 'moderate'
            })
        elif phase['type'] == 'poor_sync':
            icon = "🟠"
            description = f"**Poor Sync Phase** ({time_range}): {chunk_range} - poor similarity at {avg_similarity:.3f}"
            critical_regions.append({
                'time_range': time_range,
                'chunks': chunk_range, 
                'similarity': avg_similarity,
                'severity': 'severe'
            })
        else:  # critical_drift
            icon = "🔴"
            description = f"**Critical Drift Crisis** ({time_range}): {chunk_range} - catastrophic sync failure at {avg_similarity:.3f}"
            critical_regions.append({
                'time_range': time_range,
                'chunks': chunk_range,
                'similarity': avg_similarity, 
                'severity': 'critical'
            })
        
        report_lines.append(f"{phase_counter}. {icon} {description}")

        # Show individual chunk details for problematic phases OR when drift is detected
        show_chunks = (phase['type'] in ['degraded_sync', 'poor_sync', 'critical_drift']) or has_drift
        if show_chunks:
            for i, chunk_num in enumerate(phase['chunks'][:10]):  # Show max 10 chunks
                chunk_idx = chunk_num - 1
                if chunk_idx < len(timeline):
                    chunk_data = timeline[chunk_idx]
                    similarity = phase['similarities'][i]
                    offset = chunk_data.get('offset_seconds', 0)
                    offset_frames = int(abs(offset) * 24)
                    offset_sign = "+" if offset >= 0 else "-"
                    report_lines.append(f"   - Chunk {chunk_num}: {similarity:.3f} ({classify_similarity(similarity)}) | Offset: {offset_sign}{offset_frames}f ({offset:+.2f}s)")
            if len(phase['chunks']) > 10:
                report_lines.append(f"   - ... and {len(phase['chunks']) - 10} more chunks")
        
        report_lines.append("")
        phase_counter += 1
    
    # Key insights
    report_lines.append("## 🎯 **Key Insights:**")
    report_lines.append("")
    
    # Find worst similarity
    all_similarities = [t.get('confidence', 0.0) for t in timeline]
    worst_similarity = min(all_similarities)
    worst_chunk_idx = all_similarities.index(worst_similarity)
    worst_time = format_time_minutes(timeline[worst_chunk_idx]['start_time'])
    
    report_lines.append(f"- **Worst sync occurs at {worst_time}** (chunk {worst_chunk_idx + 1}: {worst_similarity:.3f} similarity)")
    
    # Count problematic regions
    severe_regions = [r for r in critical_regions if r['severity'] in ['severe', 'critical']]
    if severe_regions:
        report_lines.append(f"- **{len(severe_regions)} severe drift regions detected** requiring attention")
        
    # Drift assessment
    similarity_range = max(all_similarities) - min(all_similarities)
    if similarity_range > 0.400:
        report_lines.append(f"- **Extreme sync variation** (range: {similarity_range:.3f}) - single offset correction will fail")
    elif similarity_range > 0.200:
        report_lines.append(f"- **Significant sync drift** (range: {similarity_range:.3f}) - complex sync issues present")
    else:
        report_lines.append(f"- **Moderate sync variation** (range: {similarity_range:.3f}) - manageable drift")
    
    report_lines.append("")
    
    # Recommendations
    report_lines.append("## 💡 **Recommendations:**")
    report_lines.append("")
    
    if len(severe_regions) > 2:
        report_lines.append("- ⚠️  **File requires re-dubbing** - too many severe drift regions for correction")
    elif len(critical_regions) > 0:
        report_lines.append("- 🔧 **Time-variable sync correction needed** - single offset insufficient")
        report_lines.append("- 🎬 **Manual review recommended** for problematic regions")
    else:
        report_lines.append("- ✅ **File acceptable** - minor drift within tolerance")
    
    report_lines.append("")
    report_lines.append("---")
    report_lines.append(f"*Report generated from: {Path(json_file).name}*")
    
    return "\n".join(report_lines)

def main():
    parser = argparse.ArgumentParser(description="Generate formatted sync analysis report")
    parser.add_argument('json_file', help='Path to sync analysis JSON file')
    parser.add_argument('--name', help='Episode/file name for report header')
    parser.add_argument('--output', '-o', help='Output file for report (default: console)')
    
    args = parser.parse_args()
    
    if not Path(args.json_file).exists():
        print(f"Error: File not found: {args.json_file}")
        return 1
    
    report = generate_formatted_report(args.json_file, args.name)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        print(f"Report saved to: {args.output}")
    else:
        print(report)
    
    return 0

if __name__ == "__main__":
    exit(main())