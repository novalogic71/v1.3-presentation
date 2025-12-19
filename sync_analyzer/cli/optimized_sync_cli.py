#!/usr/bin/env python3
"""
Optimized Sync CLI for Large Video Files
High-performance sync detection with chunking and GPU acceleration
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.optimized_large_file_detector import OptimizedLargeFileDetector
from reports.sync_reporter import ProfessionalSyncReporter


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


def get_default_repair_output(dub_file: str) -> str:
    """Generate default output filename for repaired file"""
    dub_path = Path(dub_file)
    return str(dub_path.with_name(f"{dub_path.stem}_repaired{dub_path.suffix}"))


def perform_auto_repair(analysis_result, dub_file: str, repair_output: str, quiet: bool) -> bool:
    """
    Perform automatic repair using the intelligent sync repair system
    
    Returns:
        bool: True if repair was successful, False otherwise
    """
    try:
        # Import repair components (use relative path since we're in a submodule)
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from scripts.repair.intelligent_sync_repair import IntelligentSyncRepairer
        
        # Determine output path
        if not repair_output:
            repair_output = get_default_repair_output(dub_file)
        
        if not quiet:
            print(f"   Repairing: {os.path.basename(dub_file)} -> {os.path.basename(repair_output)}")
        
        # Save analysis to temporary file for repairer
        import tempfile
        import json
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


def create_comprehensive_package(master_file: str, dub_file: str, analysis_result, 
                               repair_output: str, output_dir: str, quiet: bool) -> bool:
    """
    Create comprehensive repair package with all outputs
    
    Returns:
        bool: True if package was created successfully, False otherwise
    """
    try:
        # Import packager (use relative path since we're in a submodule)
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from sync_repair_packager import SyncRepairPackager
        
        episode_name = f"{Path(dub_file).stem}_repair"
        
        if not quiet:
            print(f"   📦 Creating repair package...")
        
        # Create packager and generate package  
        packager = SyncRepairPackager(output_dir)
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
        description='Optimized Professional Audio Sync Analyzer for Large Files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s master.mov dub.mov
  %(prog)s master.mov dub.mov --gpu --chunk-size 20 --max-chunks 8
  %(prog)s master.mov dub.mov --output-dir ./large_file_reports --verbose
  %(prog)s master.mov dub.mov --auto-repair --repair-threshold 100
  %(prog)s master.mov dub.mov --auto-repair --create-package --repair-output repaired.mov
        """
    )
    
    # Positional arguments
    parser.add_argument('master', help='Path to master video file')
    parser.add_argument('dub', help='Path to dub video file')
    
    # Performance options
    parser.add_argument('--gpu', action='store_true', 
                       help='Enable GPU acceleration if available')
    parser.add_argument('--chunk-size', type=float, default=30.0,
                       help='Size of analysis chunks in seconds (default: 30.0)')
    parser.add_argument('--max-chunks', type=int, default=10,
                       help='Maximum number of chunks to analyze (default: 10)')
    
    # Output options
    parser.add_argument('--output-dir', type=str, default='./optimized_sync_reports',
                       help='Output directory for reports (default: ./optimized_sync_reports)')
    parser.add_argument('--json-only', action='store_true',
                       help='Only generate JSON report (no text/plots)')
    parser.add_argument('--no-visualization', action='store_true',
                       help='Skip generating visualization plots')
    
    # Logging options
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--quiet', action='store_true',
                       help='Suppress console output except errors')
    
    # Auto-repair options
    parser.add_argument('--auto-repair', action='store_true',
                       help='Automatically repair sync issues if detected')
    parser.add_argument('--repair-threshold', type=float, default=100.0,
                       help='Offset threshold in ms for auto-repair (default: 100ms)')
    parser.add_argument('--repair-output', help='Output path for repaired file (default: auto-generated)')
    parser.add_argument('--create-package', action='store_true',
                       help='Create comprehensive repair package with all outputs')
    
    args = parser.parse_args()
    
    # Validate input files
    if not os.path.exists(args.master):
        print(f"❌ Error: Master file not found: {args.master}")
        sys.exit(1)
    
    if not os.path.exists(args.dub):
        print(f"❌ Error: Dub file not found: {args.dub}")
        sys.exit(1)
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    if not args.quiet:
        print("=" * 80)
        print("🎵 OPTIMIZED PROFESSIONAL AUDIO SYNC ANALYZER v2.0")
        print("   High-Performance Large File Processing")
        print("=" * 80)
        print()
        print("📁 INPUT FILES:")
        print(f"   Master: {os.path.basename(args.master)}")
        print(f"   Dub:    {os.path.basename(args.dub)}")
        print()
        print("🔧 CONFIGURATION:")
        print(f"   GPU Acceleration: {'Enabled' if args.gpu else 'Disabled'}")
        print(f"   Chunk Size: {args.chunk_size}s")
        print(f"   Max Chunks: {args.max_chunks}")
        print(f"   Output Directory: {args.output_dir}")
        print()
    
    try:
        # Initialize optimized detector
        if not args.quiet:
            print("🚀 INITIALIZING OPTIMIZED ANALYZER...")
        
        detector = OptimizedLargeFileDetector(
            gpu_enabled=args.gpu,
            chunk_size=args.chunk_size,
            max_chunks=args.max_chunks
        )
        
        # Run analysis
        if not args.quiet:
            print("🎵 PERFORMING CHUNKED SYNC ANALYSIS...")
            print()
        
        results = detector.analyze_sync_chunked(args.master, args.dub)
        
        if 'error' in results:
            print(f"❌ Analysis failed: {results['error']}")
            sys.exit(1)
        
        # Display results
        if not args.quiet:
            print("📊 SYNC ANALYSIS RESULTS:")
            print(f"   Sync Status:    {results['sync_status']}")
            print(f"   Timecode:       {format_offset_display(results['offset_seconds'])}")
            print(f"   Confidence:     {results['confidence']:.2f}")
            print(f"   Quality:        {results['quality']}")
            print(f"   Chunks Used:    {results['chunks_reliable']}/{results['chunks_analyzed']}")
            print()
            
            # Quick assessment
            offset_abs = abs(results['offset_seconds'])
            if offset_abs < 0.01:
                print("🎯 ASSESSMENT: ✅ PERFECT - Files are perfectly synchronized")
            elif offset_abs < 0.04:
                print("🎯 ASSESSMENT: ✅ EXCELLENT - Within broadcast standards (<40ms)")
            elif offset_abs < 0.1:
                print("🎯 ASSESSMENT: ✅ GOOD - Acceptable for most applications (<100ms)")
            elif offset_abs < 1.0:
                print("🎯 ASSESSMENT: ⚠️ CAUTION - Noticeable sync issues detected")
            else:
                print("🎯 ASSESSMENT: ❌ CRITICAL - Major sync correction required")
            print()
        
        # Generate reports
        if not args.quiet:
            print("📋 GENERATING REPORTS...")
        
        # Initialize reporter
        reporter = ProfessionalSyncReporter(output_dir=args.output_dir)
        
        # Create file paths for reporting
        master_path = Path(args.master)
        dub_path = Path(args.dub)
        
        # Save detailed JSON report
        timestamp = results['analysis_date'].replace(':', '').replace('-', '').split('T')[1].split('.')[0]
        
        # Truncate filenames to avoid filesystem limits (255 chars)
        import hashlib
        master_short = master_path.stem[:50]  # First 50 chars
        dub_short = dub_path.stem[:50]  # First 50 chars
        file_hash = hashlib.md5(f"{master_path.stem}_{dub_path.stem}".encode()).hexdigest()[:8]
        
        json_filename = f"sync_report_{master_short}_{dub_short}_{file_hash}_{timestamp}.json"
        json_path = Path(args.output_dir) / json_filename
        
        with open(json_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        if not args.quiet:
            print(f"   📋 JSON Report: {json_path}")
        
        # Generate text report if not json-only
        if not args.json_only:
            text_filename = f"sync_report_{master_short}_{dub_short}_{file_hash}_{timestamp}.txt"
            text_path = Path(args.output_dir) / text_filename
            
            with open(text_path, 'w') as f:
                f.write("=" * 80 + "\\n")
                f.write("OPTIMIZED PROFESSIONAL AUDIO SYNC ANALYSIS REPORT\\n")
                f.write("=" * 80 + "\\n\\n")
                
                f.write(f"Analysis Date: {results['analysis_date']}\\n")
                f.write(f"Master File: {os.path.basename(args.master)}\\n")
                f.write(f"Dub File: {os.path.basename(args.dub)}\\n\\n")
                
                f.write("SYNC ANALYSIS RESULTS:\\n")
                f.write("-" * 40 + "\\n")
                f.write(f"Sync Status: {results['sync_status']}\\n")
                f.write(f"Offset: {results['offset_milliseconds']:+.1f} ms ({results['offset_seconds']:+.6f}s)\\n")
                f.write(f"Confidence: {results['confidence']:.2f}\\n")
                f.write(f"Similarity Score: {results['similarity_score']:.2f}\\n")
                f.write(f"Quality Assessment: {results['quality']}\\n\\n")
                
                f.write("FILE INFORMATION:\\n")
                f.write("-" * 40 + "\\n")
                f.write(f"Master Duration: {results['master_duration']:.2f}s\\n")
                f.write(f"Dub Duration: {results['dub_duration']:.2f}s\\n")
                f.write(f"Duration Difference: {results['duration_difference']:+.3f}s\\n\\n")
                
                f.write("ANALYSIS DETAILS:\\n")
                f.write("-" * 40 + "\\n")
                f.write(f"Chunks Analyzed: {results['chunks_analyzed']}\\n")
                f.write(f"Chunks Reliable: {results['chunks_reliable']}\\n")
                f.write(f"GPU Acceleration: {'Yes' if results['gpu_used'] else 'No'}\\n\\n")
                
                f.write("RECOMMENDATION:\\n")
                f.write("-" * 40 + "\\n")
                f.write(f"{results['recommendation']}\\n\\n")
                
                # Chunk details
                f.write("CHUNK ANALYSIS DETAILS:\\n")
                f.write("-" * 40 + "\\n")
                for chunk in results['chunk_details']:
                    f.write(f"Chunk {chunk['chunk_index'] + 1}: ")
                    f.write(f"{chunk['start_time']:.1f}s-{chunk['end_time']:.1f}s ")
                    f.write(f"(Quality: {chunk['quality']}, ")
                    f.write(f"Similarity: {chunk['similarities'].get('overall', 0):.3f}, ")
                    f.write(f"Offset: {chunk['offset_detection'].get('offset_seconds', 0)*1000:+.1f}ms)\\n")
                
                f.write("\\n" + "=" * 80 + "\\n")
            
            if not args.quiet:
                print(f"   📄 Text Report: {text_path}")
        
        # Generate visualization if requested
        if not args.no_visualization and not args.json_only:
            try:
                import matplotlib
                matplotlib.use('Agg')  # Use non-interactive backend
                import matplotlib.pyplot as plt
                import seaborn as sns
                
                # Create visualization
                fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
                fig.suptitle(f'Optimized Sync Analysis: {master_path.stem} vs {dub_path.stem}', 
                            fontsize=14, fontweight='bold')
                
                # 1. Chunk Quality Distribution
                qualities = [chunk['quality'] for chunk in results['chunk_details']]
                quality_counts = {}
                for q in ['Excellent', 'Good', 'Fair', 'Poor']:
                    quality_counts[q] = qualities.count(q)
                
                ax1.bar(quality_counts.keys(), quality_counts.values(), 
                       color=['green', 'orange', 'yellow', 'red'])
                ax1.set_title('Chunk Quality Distribution')
                ax1.set_ylabel('Number of Chunks')
                
                # 2. Similarity Scores by Chunk
                chunk_indices = [i+1 for i in range(len(results['chunk_details']))]
                similarities = [chunk['similarities'].get('overall', 0) 
                              for chunk in results['chunk_details']]
                
                ax2.plot(chunk_indices, similarities, 'bo-', linewidth=2, markersize=6)
                ax2.set_title('Similarity Score by Chunk')
                ax2.set_xlabel('Chunk Number')
                ax2.set_ylabel('Similarity Score')
                ax2.grid(True, alpha=0.3)
                ax2.set_ylim(0, 1)
                
                # 3. Offset Detection by Chunk
                offsets_ms = [chunk['offset_detection'].get('offset_seconds', 0) * 1000
                            for chunk in results['chunk_details']]
                confidences = [chunk['offset_detection'].get('confidence', 0)
                             for chunk in results['chunk_details']]
                
                scatter = ax3.scatter(chunk_indices, offsets_ms, c=confidences, 
                                    cmap='RdYlGn', s=60, alpha=0.7)
                ax3.set_title('Offset Detection by Chunk')
                ax3.set_xlabel('Chunk Number')
                ax3.set_ylabel('Offset (ms)')
                ax3.grid(True, alpha=0.3)
                ax3.axhline(y=0, color='black', linestyle='-', alpha=0.5)
                plt.colorbar(scatter, ax=ax3, label='Confidence')
                
                # 4. Summary Statistics
                ax4.axis('off')
                summary_text = f"""ANALYSIS SUMMARY
                
Sync Status: {results['sync_status']}
Final Offset: {results['offset_milliseconds']:+.1f} ms
Overall Confidence: {results['confidence']:.2f}
Quality Assessment: {results['quality']}

File Durations:
Master: {results['master_duration']:.1f}s
Dub: {results['dub_duration']:.1f}s

Chunks: {results['chunks_reliable']}/{results['chunks_analyzed']} reliable
GPU Used: {'Yes' if results['gpu_used'] else 'No'}"""
                
                ax4.text(0.05, 0.95, summary_text, transform=ax4.transAxes,
                        fontsize=10, verticalalignment='top',
                        bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))
                
                plt.tight_layout()
                
                # Save plot
                plot_filename = f"sync_plot_{master_short}_{dub_short}_{file_hash}_{timestamp}.png"
                plot_path = Path(args.output_dir) / plot_filename
                plt.savefig(plot_path, dpi=300, bbox_inches='tight')
                plt.close()
                
                if not args.quiet:
                    print(f"   📊 Visualization: {plot_path}")
                
            except ImportError:
                if not args.quiet:
                    print("   ⚠️  Matplotlib not available - skipping visualization")
            except Exception as e:
                if not args.quiet:
                    print(f"   ⚠️  Visualization failed: {e}")
        
        # Auto-repair logic
        repair_performed = False
        package_created = False
        
        if args.auto_repair:
            offset_ms = abs(results.get('offset_seconds', 0) * 1000)
            
            if offset_ms >= args.repair_threshold:
                if not args.quiet:
                    print("🔧 AUTO-REPAIR TRIGGERED")
                    print(f"   Detected: {format_offset_display(results.get('offset_seconds', 0))} >= {args.repair_threshold}ms threshold")
                
                # Perform repair
                repair_performed = perform_auto_repair(
                    results, args.dub, args.repair_output, args.quiet
                )
                
                if repair_performed and args.create_package:
                    # Create comprehensive package  
                    package_created = create_comprehensive_package(
                        args.master, args.dub, results,
                        args.repair_output if args.repair_output else get_default_repair_output(args.dub),
                        args.output_dir, args.quiet
                    )
            else:
                if not args.quiet:
                    print("✅ No repair needed")
                    print(f"   Offset: {format_offset_display(results.get('offset_seconds', 0))} < {args.repair_threshold}ms threshold")
        
        if not args.quiet:
            if not args.auto_repair:
                print()
                print("💡 RECOMMENDATION:")
                print(f"   {results['recommendation']}")
                print()
            print("✅ Analysis complete! Check output directory for detailed reports.")
            if repair_performed:
                print("✅ Auto-repair completed!")
            if package_created:
                print("📦 Comprehensive package created!")
        
        # Exit code based on sync quality (success if repaired)
        if results['quality'] in ['Excellent', 'Good'] or repair_performed:
            sys.exit(0)  # Success
        elif results['quality'] == 'Fair':
            sys.exit(1)  # Warning
        else:
            sys.exit(2)  # Error
    
    except KeyboardInterrupt:
        print("\\n❌ Analysis interrupted by user")
        sys.exit(3)
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(4)

if __name__ == '__main__':
    main()