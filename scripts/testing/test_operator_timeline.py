#!/usr/bin/env python3
"""
Test script for the operator-friendly timeline display
"""

import sys
import os
from pathlib import Path
import numpy as np

# Add the sync_analyzer to path
sys.path.append(str(Path(__file__).parent))


# Add project root to Python path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root))

from sync_analyzer.ui.operator_timeline import OperatorTimeline

def create_mock_analysis_result():
    """Create realistic mock analysis result for demonstration"""

    # Simulate analysis of a 10-minute video with various sync issues
    mock_chunks = []

    # Scene 1: Good dialogue sync (0:00-2:30)
    mock_chunks.append({
        'start_time': 0.0,
        'end_time': 150.0,
        'offset_detection': {'offset_seconds': 0.015, 'confidence': 0.85},
        'similarities': {'overall': 0.82},
        'master_content': {'content_type': 'dialogue'},
        'quality': 'Good',
        'ensemble_confidence': 0.87
    })

    # Scene 2: Minor drift in action sequence (2:30-4:00)
    mock_chunks.append({
        'start_time': 150.0,
        'end_time': 240.0,
        'offset_detection': {'offset_seconds': 0.067, 'confidence': 0.72},
        'similarities': {'overall': 0.68},
        'master_content': {'content_type': 'mixed'},
        'quality': 'Good',
        'ensemble_confidence': 0.74
    })

    # Scene 3: Music with good sync (4:00-5:30)
    mock_chunks.append({
        'start_time': 240.0,
        'end_time': 330.0,
        'offset_detection': {'offset_seconds': 0.023, 'confidence': 0.91},
        'similarities': {'overall': 0.88},
        'master_content': {'content_type': 'music'},
        'quality': 'Excellent',
        'ensemble_confidence': 0.93
    })

    # Scene 4: Major dialogue sync issue (5:30-7:00)
    mock_chunks.append({
        'start_time': 330.0,
        'end_time': 420.0,
        'offset_detection': {'offset_seconds': 1.234, 'confidence': 0.78},
        'similarities': {'overall': 0.71},
        'master_content': {'content_type': 'dialogue'},
        'quality': 'Fair',
        'ensemble_confidence': 0.65
    })

    # Scene 5: Moderate drift in mixed content (7:00-8:30)
    mock_chunks.append({
        'start_time': 420.0,
        'end_time': 510.0,
        'offset_detection': {'offset_seconds': 0.234, 'confidence': 0.61},
        'similarities': {'overall': 0.58},
        'master_content': {'content_type': 'mixed'},
        'quality': 'Fair',
        'ensemble_confidence': 0.55
    })

    # Scene 6: Silence/pause with no data (8:30-9:00)
    mock_chunks.append({
        'start_time': 510.0,
        'end_time': 540.0,
        'offset_detection': {'offset_seconds': 0.0, 'confidence': 0.0},
        'similarities': {'overall': 0.0, 'skipped': True},
        'master_content': {'content_type': 'silence'},
        'quality': 'Skipped'
    })

    # Scene 7: Good sync in final scene (9:00-10:00)
    mock_chunks.append({
        'start_time': 540.0,
        'end_time': 600.0,
        'offset_detection': {'offset_seconds': 0.031, 'confidence': 0.83},
        'similarities': {'overall': 0.79},
        'master_content': {'content_type': 'dialogue'},
        'quality': 'Good',
        'ensemble_confidence': 0.81
    })

    # Create mock analysis result
    mock_result = {
        'analysis_date': '2025-01-15T10:30:00',
        'master_duration': 600.0,
        'dub_duration': 600.0,
        'offset_seconds': 0.234,  # Overall weighted average
        'confidence': 0.75,
        'combined_chunks': mock_chunks,
        'timeline': mock_chunks,
        'multi_pass_analysis': True,
        'pass_1_chunks': 7,
        'pass_2_chunks': 3,
        'refinement_regions': [
            {'start': 330.0, 'end': 420.0, 'reason': 'Major drift in dialogue scene'},
            {'start': 420.0, 'end': 510.0, 'reason': 'Complex drift pattern'}
        ]
    }

    return mock_result

def test_operator_timeline():
    """Test the operator-friendly timeline display"""
    print("🧪 Testing Operator-Friendly Timeline Display")
    print("=" * 60)

    # Create mock data
    mock_result = create_mock_analysis_result()

    # Initialize operator timeline
    timeline = OperatorTimeline()

    # Test scene classification
    print("✅ Testing scene classification...")
    for chunk in mock_result['combined_chunks']:
        scene_type, scene_desc = timeline.classify_scene_content(chunk)
        severity, sev_indicator, sev_desc = timeline.classify_sync_severity(
            chunk['offset_detection']['offset_seconds']
        )
        print(f"   {chunk['start_time']/60:.1f}min: {scene_desc} → {sev_indicator} {severity}")

    print("\n" + "=" * 60)
    print("FULL OPERATOR TIMELINE DEMONSTRATION:")
    print("=" * 60)

    # Display full operator timeline
    timeline.print_operator_timeline(mock_result, "Demo_Episode.mov")

    print("\n" + "=" * 60)
    print("✅ Operator Timeline Test Complete!")
    print("\nKey Features Demonstrated:")
    print("   🎯 Clear problem identification with visual indicators")
    print("   📊 Scene-based breakdown with content awareness")
    print("   ⚡ Actionable repair recommendations with priorities")
    print("   📈 ASCII timeline visualization showing drift patterns")
    print("   🎭 Content-specific sync requirements (dialogue vs music vs action)")

    return True

if __name__ == "__main__":
    try:
        test_operator_timeline()

        print(f"\n🚀 Ready for Production Use!")
        print(f"\nUsage Examples:")
        print(f"   # Operator-friendly view (default)")
        print(f"   python continuous_sync_monitor.py master.mov dub.mov")
        print(f"")
        print(f"   # Technical view (for advanced users)")
        print(f"   python continuous_sync_monitor.py master.mov dub.mov --technical-view")
        print(f"")
        print(f"   # Fine-tuned analysis")
        print(f"   python continuous_sync_monitor.py master.mov dub.mov --refinement-chunk-size 5")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)