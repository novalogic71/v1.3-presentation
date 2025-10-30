#!/usr/bin/env python3
"""
Intelligent Sync Repair System

Uses comprehensive drift analysis to perform time-variable sync correction
with support for multi-channel audio and complex drift patterns.
"""

import os
import sys
import json
import argparse
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

class IntelligentSyncRepairer:
    """
    Intelligent sync repair system that handles complex drift patterns
    """
    
    def __init__(self):
        self.temp_dir = None
        self.audio_channels = {}
        
    def analyze_repair_requirements(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze what type of repair is needed based on drift analysis
        """
        timeline = analysis_data.get('timeline', [])
        drift_analysis = analysis_data.get('drift_analysis', {})
        
        if not timeline:
            return {"repair_type": "none", "reason": "No timeline data available"}
        
        # Extract sync offsets from timeline
        reliable_chunks = [chunk for chunk in timeline if chunk.get('reliable', False)]
        
        if len(reliable_chunks) < 2:
            # Try to get the overall offset from analysis, fall back to 0.0 if unavailable
            consensus_offset = analysis_data.get('offset_seconds', 0.0)

            # If still no reliable offset found, don't apply correction
            if consensus_offset == 0.0 and analysis_data.get('confidence', 0) < 0.1:
                return {
                    "repair_type": "none",
                    "reason": "Insufficient reliable data points and no consensus offset detected",
                    "correction_value": 0.0,
                    "correction_segments": None,
                    "reliable_chunks_count": len(reliable_chunks),
                    "total_chunks": len(timeline),
                    "confidence_score": 0.0,
                    "offset_variation": 0
                }

            return {
                "repair_type": "simple_offset",
                "reason": f"Using overall analysis offset ({consensus_offset:.3f}s)",
                "correction_value": consensus_offset,
                "correction_segments": None,
                "reliable_chunks_count": len(reliable_chunks),
                "total_chunks": len(timeline),
                "confidence_score": analysis_data.get('confidence', 0.1),
                "offset_variation": 0
            }
        
        offsets = [chunk.get('offset_seconds', 0) for chunk in reliable_chunks]
        times = [chunk.get('start_time', 0) for chunk in reliable_chunks]
        
        # Analyze drift patterns
        offset_variation = max(offsets) - min(offsets)
        correction_value = None
        correction_segments = None
        
        if offset_variation < 0.1:  # Less than 100ms variation
            repair_type = "simple_offset"
            correction_value = np.median(offsets)
        elif offset_variation < 0.5:  # Less than 500ms variation
            repair_type = "gradual_correction"
            correction_segments = self._create_gradual_correction_segments(times, offsets)
        else:  # Complex drift pattern
            repair_type = "time_variable_correction"
            correction_segments = self._create_time_variable_correction_segments(times, offsets)
        
        return {
            "repair_type": repair_type,
            "offset_variation": offset_variation,
            "correction_value": correction_value,
            "correction_segments": correction_segments,
            "reliable_chunks_count": len(reliable_chunks),
            "total_chunks": len(timeline),
            "confidence_score": len(reliable_chunks) / len(timeline)
        }
    
    def _create_gradual_correction_segments(self, times: List[float], offsets: List[float]) -> List[Dict]:
        """Create segments for gradual drift correction"""
        segments = []
        
        if len(times) < 2:
            return segments
        
        # Linear interpolation across the file
        start_offset = offsets[0]
        end_offset = offsets[-1]
        duration = times[-1] - times[0]
        
        # Create 5-minute segments with smooth transitions
        segment_duration = 300  # 5 minutes
        current_time = 0
        
        while current_time < duration:
            # Calculate offset at this time point using linear interpolation
            progress = current_time / duration
            current_offset = start_offset + (end_offset - start_offset) * progress
            
            segments.append({
                "start_time": current_time,
                "end_time": min(current_time + segment_duration, duration),
                "offset_seconds": current_offset,
                "correction_type": "gradual"
            })
            
            current_time += segment_duration
        
        return segments
    
    def _create_time_variable_correction_segments(self, times: List[float], offsets: List[float]) -> List[Dict]:
        """Create segments for complex time-variable correction"""
        segments = []
        
        # Group nearby measurements and create correction segments
        segment_size = max(2, len(times) // 10)  # Create ~10 segments
        
        for i in range(0, len(times), segment_size):
            segment_times = times[i:i + segment_size]
            segment_offsets = offsets[i:i + segment_size]
            
            if not segment_times:
                continue
                
            segments.append({
                "start_time": segment_times[0],
                "end_time": segment_times[-1] if len(segment_times) > 1 else segment_times[0] + 60,
                "offset_seconds": np.median(segment_offsets),
                "offset_variation": max(segment_offsets) - min(segment_offsets),
                "correction_type": "variable",
                "confidence": len(segment_times) / segment_size
            })
        
        return segments
    
    def detect_audio_channels(self, video_file: str) -> Dict[str, Any]:
        """
        Detect audio channel configuration of the video file
        """
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json', 
            '-show_streams', '-select_streams', 'a', video_file
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            streams_info = json.loads(result.stdout)
            
            audio_info = {
                "streams": [],
                "total_channels": 0,
                "channel_layouts": []
            }
            
            for stream in streams_info.get('streams', []):
                if stream.get('codec_type') == 'audio':
                    channels = stream.get('channels', 0)
                    channel_layout = stream.get('channel_layout', 'unknown')
                    
                    audio_info["streams"].append({
                        "index": stream.get('index'),
                        "channels": channels,
                        "channel_layout": channel_layout,
                        "codec": stream.get('codec_name'),
                        "sample_rate": stream.get('sample_rate'),
                        "bit_rate": stream.get('bit_rate')
                    })
                    
                    audio_info["total_channels"] += channels
                    audio_info["channel_layouts"].append(channel_layout)
            
            return audio_info
            
        except subprocess.CalledProcessError as e:
            print(f"Error detecting audio channels: {e}")
            return {"error": str(e)}
    
    def repair_sync_simple_offset(self, input_file: str, output_file: str, offset_seconds: float) -> bool:
        """
        Apply simple offset correction (for uniform sync issues)
        """
        print(f"Applying simple offset correction: {offset_seconds:.3f}s")
        
        cmd = [
            'ffmpeg', '-i', input_file,
            '-itsoffset', str(-offset_seconds),  # Negative because we're correcting
            '-i', input_file,
            '-map', '0:v',  # Video from first input
            '-map', '1:a',  # Audio from second input (with offset)
            '-c:v', 'copy',  # Copy video without re-encoding
            '-c:a', 'copy',  # Copy audio without re-encoding
            '-y', output_file
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Simple offset repair failed: {e}")
            return False
    
    def repair_sync_time_variable(self, input_file: str, output_file: str, 
                                 correction_segments: List[Dict], 
                                 audio_info: Dict[str, Any]) -> bool:
        """
        Apply time-variable sync correction for complex drift patterns
        """
        print(f"Applying time-variable correction with {len(correction_segments)} segments")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)
            
            # Extract original video and audio
            # Use MOV container to safely copy ProRes/H.264/etc without re-encode
            # MP4 cannot mux some codecs (e.g., ProRes), which caused failures.
            video_file = temp_dir / "video.mov"
            audio_file = temp_dir / "audio.wav"
            
            # Extract video stream (first video only), keep original codec/container
            cmd_video = [
                'ffmpeg', '-hide_banner', '-loglevel', 'error',
                '-i', input_file,
                '-map', '0:v:0',  # first video stream only
                '-an',            # drop audio
                '-dn',            # drop data
                '-c:v', 'copy',   # do not re-encode video
                '-y', str(video_file)
            ]
            
            # Extract audio stream with all channels
            cmd_audio = [
                'ffmpeg', '-hide_banner', '-loglevel', 'error',
                '-i', input_file,
                '-vn',              # No video
                '-acodec', 'pcm_s16le',
                '-ar', '48000',     # Standard sample rate
                '-y', str(audio_file)
            ]
            
            try:
                subprocess.run(cmd_video, capture_output=True, text=True, check=True)
                subprocess.run(cmd_audio, capture_output=True, text=True, check=True)
                
                # Apply time-variable correction to audio
                corrected_audio = temp_dir / "corrected_audio.wav"
                success = self._apply_time_variable_audio_correction(
                    str(audio_file), str(corrected_audio), correction_segments
                )
                
                if not success:
                    return False
                
                # Recombine video and corrected audio
                cmd_combine = [
                    'ffmpeg', 
                    '-i', str(video_file),
                    '-i', str(corrected_audio),
                    '-c:v', 'copy',
                    '-c:a', 'aac',  # Re-encode audio to maintain quality
                    '-b:a', '320k',
                    '-y', output_file
                ]
                
                subprocess.run(cmd_combine, capture_output=True, text=True, check=True)
                return True
                
            except subprocess.CalledProcessError as e:
                print(f"Time-variable repair failed: {e}")
                if hasattr(e, 'stderr') and e.stderr:
                    # Provide ffmpeg error details for debugging
                    print(e.stderr)
                return False
    
    def _apply_time_variable_audio_correction(self, input_audio: str, output_audio: str, 
                                            correction_segments: List[Dict]) -> bool:
        """
        Apply time-variable correction to audio using segment-based approach
        """
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir = Path(temp_dir)
                segment_files = []
                
                # Process each correction segment
                for i, segment in enumerate(correction_segments):
                    start_time = segment['start_time']
                    end_time = segment['end_time']
                    offset = segment['offset_seconds']
                    
                    segment_file = temp_dir / f"segment_{i:03d}.wav"
                    
                    # Compute safe seek times (avoid negative start)
                    seek_start = max(0.0, float(start_time) - float(offset))
                    seg_duration = max(0.0, float(end_time) - float(start_time))
                    if seg_duration == 0.0:
                        continue
                    
                    # Extract segment with time-shift correction (fast seek)
                    cmd_segment = [
                        'ffmpeg', '-hide_banner', '-loglevel', 'error',
                        '-ss', f"{seek_start}",
                        '-t', f"{seg_duration}",
                        '-i', input_audio,
                        '-acodec', 'pcm_s16le',
                        '-y', str(segment_file)
                    ]
                    
                    subprocess.run(cmd_segment, capture_output=True, text=True, check=True)
                    segment_files.append(str(segment_file))
                
                # Create concat file list
                concat_file = temp_dir / "concat_list.txt"
                with open(concat_file, 'w') as f:
                    for segment_file in segment_files:
                        f.write(f"file '{segment_file}'\n")
                
                # Concatenate all segments
                cmd_concat = [
                    'ffmpeg', 
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', str(concat_file),
                    '-c', 'copy',
                    '-y', output_audio
                ]
                
                subprocess.run(cmd_concat, capture_output=True, text=True, check=True)
                return True
                
        except subprocess.CalledProcessError as e:
            print(f"Audio correction failed: {e}")
            return False
    
    def repair_file(self, input_file: str, analysis_file: str, output_file: str) -> Dict[str, Any]:
        """
        Main repair function that analyzes and applies appropriate correction
        """
        # Load analysis data
        with open(analysis_file, 'r') as f:
            analysis_data = json.load(f)
        
        # Detect audio configuration
        audio_info = self.detect_audio_channels(input_file)
        if "error" in audio_info:
            return {"success": False, "error": f"Failed to analyze audio: {audio_info['error']}"}
        
        print(f"Detected audio: {audio_info['total_channels']} channels across {len(audio_info['streams'])} streams")
        
        # Analyze repair requirements
        repair_plan = self.analyze_repair_requirements(analysis_data)
        print(f"Repair type: {repair_plan['repair_type']}")
        print(f"Confidence: {repair_plan.get('confidence_score', 0):.2f}")
        
        # Apply appropriate repair method
        success = False
        
        if repair_plan['repair_type'] == "simple_offset":
            success = self.repair_sync_simple_offset(
                input_file, output_file, repair_plan['correction_value']
            )
        
        elif repair_plan['repair_type'] in ["gradual_correction", "time_variable_correction"]:
            success = self.repair_sync_time_variable(
                input_file, output_file, repair_plan['correction_segments'], audio_info
            )
        
        else:
            return {"success": False, "error": "No repair needed or insufficient data"}
        
        return {
            "success": success,
            "repair_type": repair_plan['repair_type'],
            "audio_channels": audio_info['total_channels'],
            "confidence_score": repair_plan.get('confidence_score', 0),
            "offset_variation": repair_plan.get('offset_variation', 0),
            "segments_count": len(repair_plan.get('correction_segments', [])) if repair_plan.get('correction_segments') else 1
        }
    
    def validate_repair(self, original_file: str, repaired_file: str, master_file: str) -> Dict[str, Any]:
        """
        Validate the repair by running a quick sync analysis on the result
        """
        try:
            # Run quick sync check on repaired file vs master
            cmd = [
                'python', 'quick_sync_check.py',
                master_file, repaired_file,
                '60', '300', '600'  # Check at 1min, 5min, 10min
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Parse output to extract sync measurements
            lines = result.stdout.split('\n')
            measurements = []
            
            for line in lines:
                if 'Offset =' in line and 'Confidence =' in line:
                    # Extract offset value
                    offset_part = line.split('Offset = ')[1].split('s')[0]
                    confidence_part = line.split('Confidence = ')[1].split(' ')[0]
                    
                    measurements.append({
                        "offset": float(offset_part),
                        "confidence": float(confidence_part)
                    })
            
            if measurements:
                avg_offset = np.mean([m["offset"] for m in measurements])
                max_offset = max([abs(m["offset"]) for m in measurements])
                avg_confidence = np.mean([m["confidence"] for m in measurements])
                
                # Determine repair quality
                if max_offset < 0.1:  # Less than 100ms
                    quality = "excellent"
                elif max_offset < 0.3:  # Less than 300ms
                    quality = "good"
                elif max_offset < 0.5:  # Less than 500ms
                    quality = "acceptable"
                else:
                    quality = "poor"
                
                return {
                    "success": True,
                    "quality": quality,
                    "average_offset": avg_offset,
                    "max_offset": max_offset,
                    "average_confidence": avg_confidence,
                    "measurements": measurements
                }
            
            return {"success": False, "error": "No measurements obtained"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

def main():
    parser = argparse.ArgumentParser(
        description="Intelligent Sync Repair System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.mov analysis.json --output repaired.mov
  %(prog)s input.mov analysis.json --output repaired.mov --validate-with master.mov
  %(prog)s input.mov analysis.json --output repaired.mov --preserve-quality
        """
    )
    
    parser.add_argument('input_file', help='Input video file to repair')
    parser.add_argument('analysis_file', help='JSON analysis file from continuous sync monitor')
    parser.add_argument('--output', '-o', required=True, help='Output repaired video file')
    parser.add_argument('--validate-with', help='Master file for repair validation')
    parser.add_argument('--preserve-quality', action='store_true', 
                       help='Use higher quality encoding (slower)')
    parser.add_argument('--temp-dir', help='Temporary directory for processing')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input_file):
        print(f"Error: Input file not found: {args.input_file}")
        sys.exit(1)
    
    if not os.path.exists(args.analysis_file):
        print(f"Error: Analysis file not found: {args.analysis_file}")
        sys.exit(1)
    
    # Initialize repairer
    repairer = IntelligentSyncRepairer()
    
    print("🔧 Intelligent Sync Repair System")
    print("=" * 50)
    print(f"Input: {os.path.basename(args.input_file)}")
    print(f"Analysis: {os.path.basename(args.analysis_file)}")
    print(f"Output: {os.path.basename(args.output)}")
    
    # Perform repair
    repair_result = repairer.repair_file(args.input_file, args.analysis_file, args.output)
    
    if not repair_result["success"]:
        print(f"❌ Repair failed: {repair_result['error']}")
        sys.exit(1)
    
    print("\n✅ Repair completed successfully!")
    print(f"Repair type: {repair_result['repair_type']}")
    print(f"Audio channels: {repair_result['audio_channels']}")
    print(f"Confidence: {repair_result['confidence_score']:.2f}")
    
    if repair_result.get('segments_count', 1) > 1:
        print(f"Correction segments: {repair_result['segments_count']}")
    
    # Validate repair if master file provided
    if args.validate_with:
        print("\n🔍 Validating repair quality...")
        validation = repairer.validate_repair(args.input_file, args.output, args.validate_with)
        
        if validation["success"]:
            print(f"Validation result: {validation['quality'].upper()}")
            print(f"Average offset: {validation['average_offset']:.3f}s")
            print(f"Maximum offset: {validation['max_offset']:.3f}s")
            print(f"Average confidence: {validation['average_confidence']:.3f}")
            
            if validation['quality'] in ['excellent', 'good']:
                print("🎉 Repair validation successful!")
            else:
                print("⚠️ Repair may need refinement")
        else:
            print(f"⚠️ Validation failed: {validation['error']}")
    
    print(f"\nRepaired file saved: {args.output}")

if __name__ == "__main__":
    main()
