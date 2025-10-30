#!/usr/bin/env python3
"""
LLM-Based Intelligent Report Formatting System

Uses a local LLM to generate sophisticated analysis reports with contextual insights.
"""

import json
import argparse
import requests
from typing import Dict, Any, Optional
from pathlib import Path
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from scripts.utils.smpte_utils import SMPTEUtils, TimecodeInfo

class LLMReportFormatter:
    def __init__(self, model_endpoint: str = "http://localhost:11434/api/generate"):
        """
        Initialize LLM formatter.
        
        Args:
            model_endpoint: Ollama API endpoint (default: localhost:11434)
        """
        self.model_endpoint = model_endpoint
        self.model_name = "llama3.1:8b"  # Updated to use available model
        
    def format_with_llm(self, analysis_data: Dict[str, Any], episode_name: str = "Episode") -> str:
        """Generate intelligent report using LLM analysis."""
        
        # Create comprehensive prompt with all analysis data
        prompt = self._create_analysis_prompt(analysis_data, episode_name)
        
        try:
            response = self._query_llm(prompt)
            return response
        except Exception as e:
            print(f"LLM formatting failed: {e}")
            # Fallback to rule-based formatting: write temp JSON and pass its path
            from .sync_report_analyzer import generate_formatted_report
            import tempfile
            import os
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tf:
                    json.dump(analysis_data, tf)
                    tmp_path = tf.name
                return generate_formatted_report(tmp_path, episode_name)
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass
    
    def _create_analysis_prompt(self, data: Dict[str, Any], episode_name: str) -> str:
        """Create comprehensive analysis prompt for LLM with SMPTE timecode support."""
        
        timeline = data.get('timeline', [])
        file_duration = data.get('master_duration', 0)
        drift_analysis = data.get('drift_analysis', {})
        
        # Extract key metrics
        total_chunks = len(timeline)
        reliable_chunks = sum(1 for t in timeline if t.get('reliable', False))
        similarities = [t.get('confidence', 0.0) for t in timeline]
        
        # Detect frame rate and source timecode from file paths if available
        frame_rate = 30.0  # Default
        source_timecode = None
        
        master_file = data.get('master_file', '')
        if master_file:
            try:
                frame_rate = SMPTEUtils.detect_frame_rate(master_file)
                source_timecode = SMPTEUtils.get_source_timecode(master_file)
            except Exception:
                pass
        
        # Convert duration to SMPTE timecode
        duration_tc = SMPTEUtils.seconds_to_timecode(file_duration, frame_rate, start_tc=source_timecode)
        
        prompt = f"""
You are a professional broadcast/post-production audio/video sync analysis expert. Generate a comprehensive, detailed report analyzing sync drift patterns in the episode "{episode_name}" using industry-standard SMPTE timecodes.

## RAW ANALYSIS DATA:

**File Information:**
- Episode: {episode_name}
- Duration: {duration_tc} ({file_duration:.1f} seconds)
- Frame Rate: {frame_rate:.3f} fps ({SMPTEUtils.FRAME_RATES.get(frame_rate, 'Custom')})
- Source Timecode: {source_timecode if source_timecode else 'None detected'}
- Total chunks analyzed: {total_chunks}
- Reliable chunks: {reliable_chunks}/{total_chunks} ({reliable_chunks/total_chunks*100:.1f}%)

**Timeline Data (SMPTE Timecode Analysis):**
"""

        # Add timeline data with SMPTE timecodes
        for i, chunk in enumerate(timeline[:20]):  # First 20 chunks
            start_time = chunk.get('start_time', 0)
            similarity = chunk.get('confidence', 0.0)
            reliable = "✓" if chunk.get('reliable', False) else "✗"
            
            # Convert to SMPTE timecode
            start_tc = SMPTEUtils.seconds_to_timecode(start_time, frame_rate, start_tc=source_timecode)
            end_time = start_time + chunk.get('duration', 30)
            end_tc = SMPTEUtils.seconds_to_timecode(end_time, frame_rate, start_tc=source_timecode)
            
            offset_seconds = chunk.get('offset_seconds', 0)
            offset_frames = int(abs(offset_seconds) * frame_rate)
            offset_sign = "+" if offset_seconds >= 0 else "-"
            
            prompt += f"- Chunk {i+1}: {start_tc} - {end_tc} | Similarity: {similarity:.3f} | Offset: {offset_sign}{offset_frames}f ({offset_seconds:+.3f}s) {reliable}\n"
        
        if len(timeline) > 20:
            prompt += f"- ... and {len(timeline)-20} more chunks\n"

        if similarities:
            prompt += f"""
**Key Statistics:**
- Best similarity: {max(similarities):.3f}
- Worst similarity: {min(similarities):.3f}  
- Average similarity: {sum(similarities)/len(similarities):.3f}
- Similarity range: {max(similarities) - min(similarities):.3f}
"""

        # Add drift analysis if available
        if drift_analysis:
            prompt += f"""
**Drift Analysis:**
- Has significant drift: {drift_analysis.get('has_drift', False)}
- Drift magnitude: {drift_analysis.get('drift_magnitude', 0):.3f}s
- Summary: {drift_analysis.get('drift_summary', 'No summary available')}
"""

        prompt += f"""

## INSTRUCTIONS:

Generate a professional sync analysis report with the following structure:

1. **Executive Summary** (2-3 sentences)
   - Overall sync quality assessment
   - Key findings and severity level

2. **Detailed Phase Analysis** 
   - Identify distinct sync phases (excellent/good/degraded/poor/critical)
   - For each phase: SMPTE timecode ranges, chunk numbers, similarity scores, description
   - Highlight the most problematic regions with specific SMPTE timecodes and frame offsets

3. **Critical Insights**
   - Identify patterns (gradual drift vs sudden changes)
   - Root cause analysis where possible
   - Impact assessment on viewer experience

4. **Technical Findings**
   - Worst sync regions with exact SMPTE timecodes and frame-accurate offsets
   - Statistical analysis of drift patterns over time
   - Frame rate consistency and drop-frame compensation analysis
   - Reliability assessment of measurements

5. **Professional Recommendations**
   - Specific actions needed (re-dubbing, time-variable correction, etc.)
   - Priority levels for different issues
   - Technical solutions where applicable

## STYLE REQUIREMENTS:

- Use professional broadcast/post-production terminology
- ALL time references must use SMPTE timecodes (HH:MM:SS:FF format)
- Include frame-accurate measurements and offset calculations
- Reference frame rates and drop-frame compensation where applicable
- Use industry-standard sync terminology (lip-sync, A/V offset, drift, etc.)
- Use emojis sparingly for visual clarity (✅ ❌ ⚠️ 🔴)
- Be objective and data-driven
- Provide actionable insights for post-production workflows
- Format in clean markdown with clear sections

Focus on being insightful rather than just reporting raw numbers. Analyze WHY certain patterns occur and WHAT they mean for the final product quality.

Generate the report now:
"""
        
        return prompt
    
    def _query_llm(self, prompt: str) -> str:
        """Query the LLM with the analysis prompt."""
        
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,  # Lower for more consistent analysis
                "top_p": 0.9,
                "max_tokens": 4000
            }
        }
        
        response = requests.post(self.model_endpoint, json=payload, timeout=120)
        response.raise_for_status()
        
        result = response.json()
        return result.get('response', 'No response from LLM')

    def train_on_examples(self, training_data_dir: str):
        """
        Train/fine-tune the LLM on example reports.
        
        This would load example analysis JSON files and their corresponding
        high-quality formatted reports to improve the model's understanding.
        """
        training_dir = Path(training_data_dir)
        if not training_dir.exists():
            print(f"Training directory not found: {training_dir}")
            return
        
        examples = []
        for json_file in training_dir.glob("*.json"):
            report_file = json_file.with_suffix(".md")
            if report_file.exists():
                with open(json_file) as f:
                    analysis_data = json.load(f)
                with open(report_file) as f:
                    expected_report = f.read()
                
                examples.append({
                    "analysis": analysis_data,
                    "report": expected_report
                })
        
        print(f"Found {len(examples)} training examples")
        
        # In a full implementation, this would:
        # 1. Create training prompts from examples
        # 2. Fine-tune the model or update prompt templates
        # 3. Validate improvements on test set
        
        # For now, we'll use the examples to improve our prompt template
        self._update_prompt_template(examples)
    
    def _update_prompt_template(self, examples):
        """Update prompt template based on training examples."""
        # Analyze the examples to identify common patterns and improve prompts
        print("Analyzing training examples to improve prompt template...")
        
        # This could extract:
        # - Common terminology used in good reports
        # - Effective report structures
        # - Key insights that should be highlighted
        # - Writing style preferences
        
        pass

def main():
    parser = argparse.ArgumentParser(description="LLM-Based Intelligent Report Formatter")
    parser.add_argument('json_file', help='Path to sync analysis JSON file')
    parser.add_argument('--name', help='Episode/file name for report header')
    parser.add_argument('--output', '-o', help='Output file for report')
    parser.add_argument('--model-endpoint', default='http://localhost:11434/api/generate',
                       help='LLM API endpoint (default: Ollama localhost)')
    parser.add_argument('--model', default='llama3.2',
                       help='LLM model name (default: llama3.2)')
    parser.add_argument('--fallback', action='store_true',
                       help='Use rule-based fallback if LLM fails')
    parser.add_argument('--train', help='Training data directory for model improvement')
    
    args = parser.parse_args()
    
    if not Path(args.json_file).exists():
        print(f"Error: File not found: {args.json_file}")
        return 1
    
    # Load analysis data
    with open(args.json_file, 'r') as f:
        analysis_data = json.load(f)
    
    # Initialize formatter
    formatter = LLMReportFormatter(args.model_endpoint)
    formatter.model_name = args.model
    
    # Training mode
    if args.train:
        formatter.train_on_examples(args.train)
        return 0
    
    # Generate report
    episode_name = args.name or Path(args.json_file).stem
    
    try:
        report = formatter.format_with_llm(analysis_data, episode_name)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(report)
            print(f"LLM-generated report saved to: {args.output}")
        else:
            print(report)
        
        return 0
        
    except Exception as e:
        print(f"Error generating LLM report: {e}")
        
        if args.fallback:
            print("Falling back to rule-based formatting...")
            # Import and use the rule-based formatter
            try:
                from .sync_report_analyzer import generate_formatted_report
                with open(args.json_file, 'r') as f:
                    temp_analysis_data = json.load(f)
                report = generate_formatted_report(args.json_file, episode_name)
                
                if args.output:
                    with open(args.output, 'w') as f:
                        f.write(report)
                    print(f"Fallback report saved to: {args.output}")
                else:
                    print(report)
                return 0
            except Exception as fallback_error:
                print(f"Fallback also failed: {fallback_error}")
                return 1
        
        return 1

if __name__ == "__main__":
    exit(main())
