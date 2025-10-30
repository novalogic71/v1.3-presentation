#!/usr/bin/env python3
"""
Enhanced Continuous Sync Monitoring Tool

This tool provides comprehensive sync analysis throughout entire video files,
detecting sync drift and providing detailed timeline reports.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import matplotlib.pyplot as plt
import numpy as np

# Add project root to Python path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root))

from sync_analyzer.core.optimized_large_file_detector import OptimizedLargeFileDetector
from sync_analyzer.ui.operator_timeline import OperatorTimeline


def format_time(seconds: float) -> str:
    """Format seconds to HH:MM:SS.mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def print_timeline_summary(timeline: List[Dict], file_duration: float):
    """Print a concise timeline summary"""
    print("\n" + "="*80)
    print("SYNC TIMELINE ANALYSIS")
    print("="*80)
    
    reliable_chunks = [t for t in timeline if t['reliable']]
    unreliable_chunks = [t for t in timeline if not t['reliable']]
    
    print(f"File Duration: {format_time(file_duration)}")
    print(f"Total Chunks Analyzed: {len(timeline)}")
    print(f"Reliable Chunks: {len(reliable_chunks)}")
    print(f"Unreliable Chunks: {len(unreliable_chunks)}")
    
    if reliable_chunks:
        offsets = [t['offset_seconds'] for t in reliable_chunks]
        print(f"Offset Range: {min(offsets):.3f}s to {max(offsets):.3f}s")
        print(f"Median Offset: {np.median(offsets):.3f}s")
        
        print(f"\nDetailed Timeline:")
        print("-" * 80)
        print(f"{'Time Range':>20} {'Offset':>10} {'Conf':>6} {'Quality':>10} {'Status':>8}")
        print("-" * 80)
        
        for chunk in timeline[::max(1, len(timeline)//20)]:  # Show max 20 entries
            time_str = f"{format_time(chunk['start_time'])}"
            offset_str = f"{chunk['offset_seconds']:+6.3f}s"
            conf_str = f"{chunk['confidence']:.2f}"
            quality_str = chunk['quality']
            status_str = "✓" if chunk['reliable'] else "✗"
            
            print(f"{time_str:>20} {offset_str:>10} {conf_str:>6} {quality_str:>10} {status_str:>8}")


def print_drift_analysis(drift_analysis: Dict[str, Any]):
    """Print detailed drift analysis"""
    print("\n" + "="*80)
    print("SYNC DRIFT ANALYSIS")
    print("="*80)
    
    print(f"Has Significant Drift: {'Yes' if drift_analysis['has_drift'] else 'No'}")
    print(f"Drift Magnitude: {drift_analysis['drift_magnitude']:.3f}s ({drift_analysis['drift_magnitude_ms']:.1f}ms)")
    print(f"Median Offset: {drift_analysis['median_offset']:.3f}s")
    
    offset_range = drift_analysis['offset_range']
    print(f"Offset Range: {offset_range['min']:.3f}s to {offset_range['max']:.3f}s")
    
    print(f"\nSummary: {drift_analysis['drift_summary']}")
    
    # Show problematic regions
    drift_regions = drift_analysis.get('drift_regions', [])
    if drift_regions:
        print(f"\n⚠️  Problematic Regions ({len(drift_regions)} found):")
        print("-" * 60)
        for region in drift_regions[:10]:  # Show max 10 regions
            print(f"  {region['time_range']:>20}: {region['offset_seconds']:+6.3f}s "
                  f"(deviation: {region['deviation_from_median']:+6.3f}s)")


def create_sync_visualization(result: Dict[str, Any], output_path: str = None):
    """Create a visualization of sync over time"""
    try:
        timeline = result.get('timeline', [])
        if not timeline:
            print("No timeline data available for visualization")
            return
        
        # Extract data for plotting
        times = [t['start_time'] / 60 for t in timeline]  # Convert to minutes
        offsets = [t['offset_seconds'] for t in timeline]
        confidences = [t['confidence'] for t in timeline]
        reliable = [t['reliable'] for t in timeline]
        
        # Create subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
        
        # Plot 1: Sync offsets over time
        reliable_times = [t for i, t in enumerate(times) if reliable[i]]
        reliable_offsets = [o for i, o in enumerate(offsets) if reliable[i]]
        unreliable_times = [t for i, t in enumerate(times) if not reliable[i]]
        unreliable_offsets = [o for i, o in enumerate(offsets) if not reliable[i]]
        
        ax1.scatter(reliable_times, reliable_offsets, c='green', alpha=0.7, s=30, label='Reliable')
        ax1.scatter(unreliable_times, unreliable_offsets, c='red', alpha=0.5, s=20, label='Unreliable')
        
        if reliable_offsets:
            median_offset = np.median(reliable_offsets)
            ax1.axhline(y=median_offset, color='blue', linestyle='--', alpha=0.7, label=f'Median: {median_offset:.3f}s')
        
        ax1.set_ylabel('Sync Offset (seconds)')
        ax1.set_title('Sync Offset Throughout File')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Plot 2: Confidence over time  
        reliable_conf = [c for i, c in enumerate(confidences) if reliable[i]]
        unreliable_conf = [c for i, c in enumerate(confidences) if not reliable[i]]
        
        ax2.scatter(reliable_times, reliable_conf, c='green', alpha=0.7, s=30, label='Reliable')
        ax2.scatter(unreliable_times, unreliable_conf, c='red', alpha=0.5, s=20, label='Unreliable')
        
        ax2.set_xlabel('Time (minutes)')
        ax2.set_ylabel('Confidence')
        ax2.set_title('Analysis Confidence Throughout File')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            print(f"Visualization saved to: {output_path}")
        else:
            plt.show()
            
    except ImportError:
        print("Matplotlib not available - skipping visualization")
    except Exception as e:
        print(f"Error creating visualization: {e}")


def export_results(result: Dict[str, Any], output_path: str):
    """Export results to JSON file"""
    try:
        # Convert numpy types to native Python types for JSON serialization
        def convert_numpy(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, (np.int64, np.int32)):
                return int(obj)
            elif isinstance(obj, (np.float64, np.float32)):
                return float(obj)
            return obj
        
        def clean_dict(d):
            if isinstance(d, dict):
                return {k: clean_dict(v) for k, v in d.items()}
            elif isinstance(d, list):
                return [clean_dict(v) for v in d]
            else:
                return convert_numpy(d)
        
        clean_result = clean_dict(result)
        
        with open(output_path, 'w') as f:
            json.dump(clean_result, f, indent=2)
        print(f"Results exported to: {output_path}")
        
    except Exception as e:
        print(f"Error exporting results: {e}")


def get_default_repair_output(dub_file: str) -> str:
    """Generate default output filename for repaired file"""
    dub_path = Path(dub_file)
    return str(dub_path.with_name(f"{dub_path.stem}_repaired{dub_path.suffix}"))


def perform_auto_repair(analysis_result: Dict[str, Any], dub_file: str, repair_output: Optional[str], quiet: bool) -> bool:
    """
    Perform automatic repair using the intelligent sync repair system
    
    Returns:
        bool: True if repair was successful, False otherwise
    """
    try:
        # Import repair components
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
        from scripts.repair.intelligent_sync_repair import IntelligentSyncRepairer
        
        # Determine output path
        if not repair_output:
            repair_output = get_default_repair_output(dub_file)
        
        if not quiet:
            print(f"   Repairing: {os.path.basename(dub_file)} -> {os.path.basename(repair_output)}")
        
        # Save analysis to temporary file for repairer
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(analysis_result, f, indent=2, default=str)
            temp_analysis_file = f.name
        
        try:
            # Initialize repairer and perform repair
            repairer = IntelligentSyncRepairer()
            repair_result = repairer.repair_file(dub_file, temp_analysis_file, repair_output)
            
            if repair_result["success"]:
                if not quiet:
                    print(f"   ✅ Repair completed: {repair_result['repair_type']}")
                    print(f"   📁 Repaired file: {repair_output}")
                return True
            else:
                if not quiet:
                    print(f"   ❌ Repair failed: {repair_result.get('error', 'Unknown error')}")
                return False
                
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_analysis_file)
            except:
                pass
                
    except ImportError:
        if not quiet:
            print("   ❌ Repair system not available (intelligent_sync_repair module not found)")
        return False
    except Exception as e:
        if not quiet:
            print(f"   ❌ Repair failed: {e}")
        return False


def create_comprehensive_package(master_file: str, dub_file: str, analysis_result: Dict[str, Any], 
                               repair_output: str, package_dir: str, quiet: bool) -> bool:
    """
    Create comprehensive repair package with all outputs
    
    Returns:
        bool: True if package was created successfully, False otherwise
    """
    try:
        # Import packager
        from sync_repair_packager import SyncRepairPackager
        
        episode_name = f"{Path(dub_file).stem}_repair"
        
        if not quiet:
            print(f"   📦 Creating repair package...")
        
        # Create packager and generate package
        packager = SyncRepairPackager(package_dir)
        package_result = packager.create_repair_package(
            original_file=dub_file,
            analysis_data=analysis_result,
            repaired_file=repair_output if os.path.exists(repair_output) else None,
            episode_name=episode_name,
            include_visualization=True,
            create_zip=True
        )
        
        if package_result["success"]:
            if not quiet:
                print(f"   ✅ Package created: {package_result['package_name']}")
                print(f"   📁 Package directory: {package_result['package_directory']}")
                if "zip_file" in package_result:
                    print(f"   📦 Archive: {os.path.basename(package_result['zip_file'])}")
            return True
        else:
            if not quiet:
                print(f"   ❌ Package creation failed: {package_result.get('error', 'Unknown error')}")
            return False
            
    except ImportError:
        if not quiet:
            print("   ❌ Package system not available (sync_repair_packager module not found)")
        return False
    except Exception as e:
        if not quiet:
            print(f"   ❌ Package creation failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Enhanced Continuous Sync Monitoring Tool with Auto-Repair",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s master.mov dub.mov
  %(prog)s master.mov dub.mov --output results.json --plot sync_plot.png
  %(prog)s master.mov dub.mov --chunk-size 20 --detailed
  %(prog)s master.mov dub.mov --auto-repair --repair-threshold 100
  %(prog)s master.mov dub.mov --auto-repair --repair-output repaired.mov --create-package

Timeline Display Options:
  %(prog)s master.mov dub.mov                    # Operator-friendly view (default)
  %(prog)s master.mov dub.mov --technical-view   # Technical details view
  %(prog)s master.mov dub.mov --disable-multipass --technical-view  # Legacy mode

Multi-Pass Analysis:
  %(prog)s master.mov dub.mov --refinement-chunk-size 5 --gap-threshold 0.2  # Fine-tuned
        """
    )
    
    parser.add_argument('master_file', help='Path to master/reference video file')
    parser.add_argument('dub_file', help='Path to dub/test video file')
    parser.add_argument('--chunk-size', type=float, default=30.0,
                       help='Chunk size in seconds (default: 30.0)')
    parser.add_argument('--output', '-o', help='Output JSON file path')
    parser.add_argument('--plot', help='Output plot image file path')
    parser.add_argument('--detailed', action='store_true',
                       help='Show detailed chunk information')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Minimal output (summary only)')

    # Enhanced multi-pass analysis options
    parser.add_argument('--enable-multipass', action='store_true', default=True,
                       help='Enable intelligent two-pass analysis (default: enabled)')
    parser.add_argument('--disable-multipass', action='store_true',
                       help='Disable multi-pass analysis, use single-pass only')
    parser.add_argument('--refinement-chunk-size', type=float, default=10.0,
                       help='Chunk size for Pass 2 refinement (default: 10.0s)')
    parser.add_argument('--gap-threshold', type=float, default=0.3,
                       help='Confidence threshold for triggering gap analysis (default: 0.3)')
    parser.add_argument('--content-adaptive', action='store_true', default=True,
                       help='Enable content-aware parameter tuning (default: enabled)')

    # Timeline display options
    parser.add_argument('--operator-view', action='store_true', default=True,
                       help='Use operator-friendly timeline display (default: enabled)')
    parser.add_argument('--technical-view', action='store_true',
                       help='Use technical timeline display (legacy mode)')

    # Auto-repair options
    parser.add_argument('--auto-repair', action='store_true',
                       help='Automatically repair sync issues if detected')
    parser.add_argument('--repair-threshold', type=float, default=100.0,
                       help='Offset threshold in ms for auto-repair (default: 100ms)')
    parser.add_argument('--repair-output', help='Output path for repaired file (default: auto-generated)')
    parser.add_argument('--create-package', action='store_true',
                       help='Create comprehensive repair package with all outputs')
    parser.add_argument('--package-dir', default='./repair_packages',
                       help='Directory for repair packages (default: ./repair_packages)')
    
    args = parser.parse_args()
    
    # Validate input files
    if not os.path.exists(args.master_file):
        print(f"Error: Master file not found: {args.master_file}")
        sys.exit(1)
    
    if not os.path.exists(args.dub_file):
        print(f"Error: Dub file not found: {args.dub_file}")
        sys.exit(1)
    
    # Determine multi-pass settings
    enable_multipass = args.enable_multipass and not args.disable_multipass

    # Determine timeline display mode
    use_operator_view = args.operator_view and not args.technical_view

    if not args.quiet:
        print("🧠 Enhanced Intelligent Sync Monitor")
        print("=" * 50)
        print(f"Master: {os.path.basename(args.master_file)}")
        print(f"Dub: {os.path.basename(args.dub_file)}")
        print(f"Chunk Size: {args.chunk_size}s")
        print(f"Multi-Pass Analysis: {'Enabled' if enable_multipass else 'Disabled'}")
        if enable_multipass:
            print(f"Refinement Chunk Size: {args.refinement_chunk_size}s")
            print(f"Gap Analysis Threshold: {args.gap_threshold}")
        print(f"Content-Adaptive Processing: {'Enabled' if args.content_adaptive else 'Disabled'}")
        print(f"Timeline Display: {'Operator-Friendly' if use_operator_view else 'Technical'}")
        print(f"Analysis Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Run analysis
    try:
        detector = OptimizedLargeFileDetector(
            chunk_size=args.chunk_size,
            enable_multi_pass=enable_multipass
        )

        # Set refinement parameters
        detector.refinement_chunk_size = args.refinement_chunk_size
        detector.gap_analysis_threshold = args.gap_threshold

        result = detector.analyze_sync_chunked(args.master_file, args.dub_file)
        
        if 'error' in result:
            print(f"Analysis failed: {result['error']}")
            sys.exit(1)
        
        # Print results
        if not args.quiet:
            print(f"\nAnalysis Completed: {datetime.now().strftime('%H:%M:%S')}")

            # Multi-pass analysis summary
            is_multipass = result.get('multi_pass_analysis', False)
            if is_multipass:
                print(f"\n🎯 MULTI-PASS ANALYSIS RESULTS:")
                print(f"Pass 1 (Coarse): {result.get('pass_1_chunks', 0)} chunks")
                print(f"Pass 2 (Refinement): {result.get('pass_2_chunks', 0)} chunks")
                refinement_regions = result.get('refinement_regions', [])
                if refinement_regions:
                    print(f"Refined Regions: {len(refinement_regions)}")
                    for i, region in enumerate(refinement_regions[:3]):  # Show first 3
                        print(f"  Region {i+1}: {region['start']:.1f}s-{region['end']:.1f}s ({region['reason']})")
                    if len(refinement_regions) > 3:
                        print(f"  ... and {len(refinement_regions) - 3} more regions")

            # Basic summary
            print(f"\n📊 SUMMARY:")
            print(f"Overall Offset: {result.get('offset_seconds', 0):.3f}s")
            print(f"Confidence: {result.get('confidence', 0):.3f}")
            print(f"Total Chunks Analyzed: {result.get('total_chunks_analyzed', result.get('chunks_analyzed', 0))}")
            print(f"Reliable Chunks: {result.get('chunks_reliable', 0)}")

            # Content analysis summary if available
            if 'combined_chunks' in result:
                chunks = result['combined_chunks']
                content_types = {}
                for chunk in chunks:
                    if 'master_content' in chunk:
                        content_type = chunk['master_content'].get('content_type', 'unknown')
                        content_types[content_type] = content_types.get(content_type, 0) + 1

                if content_types:
                    print(f"\n🎵 CONTENT ANALYSIS:")
                    for content_type, count in content_types.items():
                        percentage = (count / len(chunks)) * 100
                        print(f"  {content_type.capitalize()}: {count} chunks ({percentage:.1f}%)")

            # Timeline Display
            if use_operator_view:
                # Operator-friendly timeline
                operator_timeline = OperatorTimeline()
                operator_timeline.print_operator_timeline(
                    result,
                    file_name=f"{os.path.basename(args.master_file)} vs {os.path.basename(args.dub_file)}"
                )
            else:
                # Legacy technical timeline (for advanced users)
                if 'drift_analysis' in result:
                    print_drift_analysis(result['drift_analysis'])

                if 'timeline' in result and (args.detailed or result.get('drift_analysis', {}).get('has_drift', False)):
                    print_timeline_summary(result['timeline'], result.get('master_duration', 0))
        
        # Export results
        if args.output:
            export_results(result, args.output)
        
        # Create visualization
        if args.plot:
            create_sync_visualization(result, args.plot)
            
        # Auto-repair logic
        repair_performed = False
        package_created = False
        
        if args.auto_repair:
            offset_ms = abs(result.get('offset_seconds', 0) * 1000)
            
            if offset_ms >= args.repair_threshold:
                if not args.quiet:
                    print(f"\n🔧 AUTO-REPAIR TRIGGERED")
                    print(f"Detected offset: {offset_ms:.1f}ms >= threshold: {args.repair_threshold}ms")
                
                # Perform repair
                repair_performed = perform_auto_repair(
                    result, args.dub_file, args.repair_output, args.quiet
                )
                
                if repair_performed and args.create_package:
                    # Create comprehensive package
                    package_created = create_comprehensive_package(
                        args.master_file, args.dub_file, result, 
                        args.repair_output if args.repair_output else get_default_repair_output(args.dub_file),
                        args.package_dir, args.quiet
                    )
            else:
                if not args.quiet:
                    print(f"\n✅ No repair needed (offset: {offset_ms:.1f}ms < threshold: {args.repair_threshold}ms)")
        
        # Final assessment
        drift_analysis = result.get('drift_analysis', {})
        if drift_analysis.get('has_drift', False):
            if not args.quiet:
                print(f"\n⚠️  SYNC DRIFT DETECTED")
                print(f"The files have inconsistent sync throughout the duration.")
                print(f"Maximum variation: {drift_analysis['drift_magnitude']:.3f}s")
                
                if repair_performed:
                    print(f"✅ Repair applied automatically")
                    if package_created:
                        print(f"📦 Comprehensive package created")
            
            sys.exit(2 if not repair_performed else 0)  # Success if repaired
        else:
            if not args.quiet:
                print(f"\n✅ Consistent sync throughout file")
                if repair_performed:
                    print(f"✅ Minor offset corrected automatically")
            sys.exit(0)  # Success
            
    except KeyboardInterrupt:
        print("\nAnalysis interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"Error during analysis: {e}")
        if not args.quiet:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()