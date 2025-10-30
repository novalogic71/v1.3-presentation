#!/usr/bin/env python3
"""
Sync Repair Package Creator

Creates comprehensive packages containing analysis, repair results, and reports
for professional sync correction workflows.
"""

import os
import json
import shutil
import zipfile
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import subprocess

class SyncRepairPackager:
    """
    Creates professional repair packages with all analysis and repair artifacts
    """
    
    def __init__(self, output_base_dir: str = "./repair_packages"):
        """
        Initialize packager with output directory
        
        Args:
            output_base_dir: Base directory for creating repair packages
        """
        self.output_base_dir = Path(output_base_dir)
        self.output_base_dir.mkdir(parents=True, exist_ok=True)
    
    def create_repair_package(self, 
                            original_file: str,
                            analysis_data: Dict[str, Any],
                            repaired_file: Optional[str] = None,
                            episode_name: str = "Episode",
                            include_visualization: bool = True,
                            create_zip: bool = True) -> Dict[str, Any]:
        """
        Create a comprehensive repair package
        
        Args:
            original_file: Path to original file
            analysis_data: Complete analysis results dictionary
            repaired_file: Path to repaired file (if repair was performed)
            episode_name: Name for the episode/content
            include_visualization: Whether to create sync visualization
            create_zip: Whether to create a zip archive
            
        Returns:
            Dictionary with package information and file paths
        """
        # Create package directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = self._sanitize_filename(episode_name)
        package_name = f"{safe_name}_sync_repair_{timestamp}"
        package_dir = self.output_base_dir / package_name
        package_dir.mkdir(parents=True, exist_ok=True)
        
        package_info = {
            "package_name": package_name,
            "package_directory": str(package_dir),
            "created_timestamp": timestamp,
            "episode_name": episode_name,
            "files": {}
        }
        
        try:
            # 1. Copy original file
            if os.path.exists(original_file):
                original_dest = package_dir / f"original_{Path(original_file).name}"
                shutil.copy2(original_file, original_dest)
                package_info["files"]["original"] = str(original_dest)
            
            # 2. Copy repaired file if available
            if repaired_file and os.path.exists(repaired_file):
                repaired_dest = package_dir / f"repaired_{Path(repaired_file).name}"
                shutil.copy2(repaired_file, repaired_dest)
                package_info["files"]["repaired"] = str(repaired_dest)
            
            # 3. Save analysis data
            analysis_file = package_dir / "analysis_report.json"
            with open(analysis_file, 'w') as f:
                json.dump(analysis_data, f, indent=2, default=str)
            package_info["files"]["analysis_json"] = str(analysis_file)
            
            # 4. Create repair locations tracking
            repair_locations = self._extract_repair_locations(analysis_data)
            if repair_locations:
                locations_file = package_dir / "repair_locations.json"
                with open(locations_file, 'w') as f:
                    json.dump(repair_locations, f, indent=2)
                package_info["files"]["repair_locations"] = str(locations_file)
            
            # 5. Generate LLM-enhanced repair report
            try:
                repair_report = self._generate_repair_report(analysis_data, episode_name)
                report_file = package_dir / "repair_report.md"
                with open(report_file, 'w') as f:
                    f.write(repair_report)
                package_info["files"]["repair_report"] = str(report_file)
            except Exception as e:
                print(f"Warning: Could not generate LLM repair report: {e}")
            
            # 6. Create sync visualization
            if include_visualization:
                try:
                    viz_file = self._create_sync_visualization(analysis_data, package_dir, package_name)
                    if viz_file:
                        package_info["files"]["visualization"] = str(viz_file)
                except Exception as e:
                    print(f"Warning: Could not create visualization: {e}")
            
            # 7. Create package summary
            summary_file = package_dir / "package_summary.txt"
            self._create_package_summary(package_info, analysis_data, summary_file)
            package_info["files"]["summary"] = str(summary_file)
            
            # 8. Create ZIP archive if requested
            if create_zip:
                zip_file = self.output_base_dir / f"{package_name}.zip"
                self._create_zip_archive(package_dir, zip_file)
                package_info["zip_file"] = str(zip_file)
            
            package_info["success"] = True
            package_info["total_files"] = len(package_info["files"])
            
            return package_info
            
        except Exception as e:
            package_info["success"] = False
            package_info["error"] = str(e)
            return package_info
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize filename for safe filesystem usage"""
        import re
        # Replace unsafe characters with underscores
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', name)
        # Remove multiple consecutive underscores
        safe_name = re.sub(r'_+', '_', safe_name)
        # Limit length
        return safe_name[:50].strip('_')
    
    def _extract_repair_locations(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract specific locations where repairs were applied"""
        timeline = analysis_data.get('timeline', [])
        drift_analysis = analysis_data.get('drift_analysis', {})
        
        repair_locations = {
            "extraction_timestamp": datetime.now().isoformat(),
            "total_duration": analysis_data.get('master_duration', 0),
            "problem_regions": [],
            "repair_segments": [],
            "quality_breakdown": {}
        }
        
        # Extract problem regions from timeline
        for chunk in timeline:
            if chunk.get('reliable', False):
                offset = chunk.get('offset_seconds', 0)
                if abs(offset) > 0.1:  # Significant offset
                    repair_locations["problem_regions"].append({
                        "start_time": chunk.get('start_time', 0),
                        "end_time": chunk.get('end_time', 0),
                        "offset_seconds": offset,
                        "offset_ms": offset * 1000,
                        "confidence": chunk.get('confidence', 0),
                        "quality": chunk.get('quality', 'unknown'),
                        "requires_repair": True
                    })
        
        # Extract repair segments if available
        if 'correction_segments' in analysis_data:
            repair_locations["repair_segments"] = analysis_data['correction_segments']
        
        # Quality breakdown
        qualities = [chunk.get('quality', 'unknown') for chunk in timeline]
        for quality in ['Excellent', 'Good', 'Fair', 'Poor']:
            repair_locations["quality_breakdown"][quality] = qualities.count(quality)
        
        return repair_locations
    
    def _generate_repair_report(self, analysis_data: Dict[str, Any], episode_name: str) -> str:
        """Generate LLM-enhanced repair report"""
        try:
            # Try to use LLM formatter if available
            from .llm_report_formatter import LLMReportFormatter
            formatter = LLMReportFormatter()
            return formatter.format_with_llm(analysis_data, episode_name)
        except ImportError:
            # Fallback to basic repair report
            return self._generate_basic_repair_report(analysis_data, episode_name)
    
    def _generate_basic_repair_report(self, analysis_data: Dict[str, Any], episode_name: str) -> str:
        """Generate basic repair report as fallback"""
        timeline = analysis_data.get('timeline', [])
        drift_analysis = analysis_data.get('drift_analysis', {})
        
        report = f"""# 🔧 Sync Repair Report: {episode_name}

## Analysis Summary
- **Episode**: {episode_name}
- **Analysis Date**: {analysis_data.get('analysis_date', 'Unknown')}
- **File Duration**: {analysis_data.get('master_duration', 0):.1f} seconds
- **Sync Status**: {analysis_data.get('sync_status', 'Unknown')}
- **Overall Offset**: {analysis_data.get('offset_seconds', 0)*1000:+.1f}ms

## Repair Requirements
- **Repair Type**: {self._determine_repair_type(analysis_data)}
- **Confidence**: {analysis_data.get('confidence', 0):.2f}
- **Chunks Analyzed**: {analysis_data.get('chunks_analyzed', 0)}
- **Reliable Chunks**: {analysis_data.get('chunks_reliable', 0)}

## Problem Regions Identified
"""
        
        # Add problem regions
        problem_count = 0
        for chunk in timeline:
            if chunk.get('reliable', False) and abs(chunk.get('offset_seconds', 0)) > 0.1:
                problem_count += 1
                start_min = chunk.get('start_time', 0) / 60
                end_min = chunk.get('end_time', 0) / 60
                offset_ms = chunk.get('offset_seconds', 0) * 1000
                
                report += f"- **{start_min:.1f}m-{end_min:.1f}m**: {offset_ms:+.1f}ms offset (Quality: {chunk.get('quality', 'Unknown')})\n"
        
        if problem_count == 0:
            report += "- No significant sync issues detected\n"
        
        report += f"""
## Drift Analysis
- **Has Drift**: {'Yes' if drift_analysis.get('has_drift', False) else 'No'}
- **Drift Magnitude**: {drift_analysis.get('drift_magnitude', 0)*1000:.1f}ms
- **Drift Summary**: {drift_analysis.get('drift_summary', 'No analysis available')}

## Recommendations
{analysis_data.get('recommendation', 'No specific recommendations available')}

---
*Report generated automatically by Sync Repair Package Creator*
"""
        
        return report
    
    def _determine_repair_type(self, analysis_data: Dict[str, Any]) -> str:
        """Determine what type of repair is needed"""
        timeline = analysis_data.get('timeline', [])
        reliable_chunks = [t for t in timeline if t.get('reliable', False)]
        
        if len(reliable_chunks) < 2:
            return "Simple offset correction"
        
        offsets = [t.get('offset_seconds', 0) for t in reliable_chunks]
        offset_variation = max(offsets) - min(offsets)
        
        if offset_variation < 0.1:
            return "Simple offset correction"
        elif offset_variation < 0.5:
            return "Gradual drift correction"
        else:
            return "Time-variable correction"
    
    def _create_sync_visualization(self, analysis_data: Dict[str, Any], package_dir: Path, package_name: str) -> Optional[Path]:
        """Create sync visualization plot"""
        try:
            import matplotlib.pyplot as plt
            import matplotlib
            matplotlib.use('Agg')  # Use non-interactive backend
            
            timeline = analysis_data.get('timeline', [])
            if not timeline:
                return None
            
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
            
            # Extract data
            times = [t.get('start_time', 0) / 60 for t in timeline]  # Convert to minutes
            offsets_ms = [t.get('offset_seconds', 0) * 1000 for t in timeline]
            confidences = [t.get('confidence', 0) for t in timeline]
            reliable = [t.get('reliable', False) for t in timeline]
            
            # Plot 1: Offset over time
            reliable_times = [t for i, t in enumerate(times) if reliable[i]]
            reliable_offsets = [o for i, o in enumerate(offsets_ms) if reliable[i]]
            unreliable_times = [t for i, t in enumerate(times) if not reliable[i]]
            unreliable_offsets = [o for i, o in enumerate(offsets_ms) if not reliable[i]]
            
            if reliable_times:
                ax1.plot(reliable_times, reliable_offsets, 'go-', label='Reliable', linewidth=2, markersize=6)
            if unreliable_times:
                ax1.plot(unreliable_times, unreliable_offsets, 'ro', label='Unreliable', alpha=0.5, markersize=4)
            
            ax1.axhline(y=0, color='black', linestyle='-', alpha=0.3)
            ax1.set_title(f'Sync Offset Timeline - {analysis_data.get("sync_status", "Unknown")}')
            ax1.set_xlabel('Time (minutes)')
            ax1.set_ylabel('Offset (ms)')
            ax1.grid(True, alpha=0.3)
            ax1.legend()
            
            # Plot 2: Confidence over time
            ax2.plot(times, confidences, 'b-', linewidth=2, alpha=0.7)
            ax2.fill_between(times, confidences, alpha=0.3)
            ax2.set_title('Detection Confidence Over Time')
            ax2.set_xlabel('Time (minutes)')
            ax2.set_ylabel('Confidence')
            ax2.grid(True, alpha=0.3)
            ax2.set_ylim(0, 1)
            
            plt.tight_layout()
            
            viz_file = package_dir / f"{package_name}_sync_visualization.png"
            plt.savefig(viz_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            return viz_file
            
        except ImportError:
            print("Matplotlib not available - skipping visualization")
            return None
        except Exception as e:
            print(f"Visualization creation failed: {e}")
            return None
    
    def _create_package_summary(self, package_info: Dict[str, Any], analysis_data: Dict[str, Any], summary_file: Path):
        """Create a human-readable package summary"""
        with open(summary_file, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("SYNC REPAIR PACKAGE SUMMARY\n")
            f.write("=" * 80 + "\n\n")
            
            f.write(f"Package Name: {package_info['package_name']}\n")
            f.write(f"Created: {package_info['created_timestamp']}\n")
            f.write(f"Episode: {package_info['episode_name']}\n")
            f.write(f"Total Files: {package_info['total_files']}\n\n")
            
            f.write("PACKAGE CONTENTS:\n")
            f.write("-" * 40 + "\n")
            for file_type, file_path in package_info["files"].items():
                f.write(f"  {file_type.upper()}: {Path(file_path).name}\n")
            
            if "zip_file" in package_info:
                f.write(f"  ZIP ARCHIVE: {Path(package_info['zip_file']).name}\n")
            
            f.write("\nANALYSIS SUMMARY:\n")
            f.write("-" * 40 + "\n")
            f.write(f"  Sync Status: {analysis_data.get('sync_status', 'Unknown')}\n")
            f.write(f"  Overall Offset: {analysis_data.get('offset_seconds', 0)*1000:+.1f}ms\n")
            f.write(f"  Confidence: {analysis_data.get('confidence', 0):.2f}\n")
            f.write(f"  File Duration: {analysis_data.get('master_duration', 0):.1f}s\n")
            f.write(f"  Chunks Analyzed: {analysis_data.get('chunks_analyzed', 0)}\n")
            f.write(f"  Reliable Chunks: {analysis_data.get('chunks_reliable', 0)}\n\n")
            
            f.write("USAGE INSTRUCTIONS:\n")
            f.write("-" * 40 + "\n")
            f.write("1. Review the analysis_report.json for technical details\n")
            f.write("2. Check repair_report.md for human-readable analysis\n")
            f.write("3. Use repair_locations.json to understand problem areas\n")
            f.write("4. Compare original vs repaired files if repair was performed\n")
            f.write("5. View sync_visualization.png for timeline overview\n\n")
            
            f.write("=" * 80 + "\n")
    
    def _create_zip_archive(self, package_dir: Path, zip_file: Path):
        """Create ZIP archive of the package"""
        with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in package_dir.rglob('*'):
                if file_path.is_file():
                    # Create relative path for archive
                    arc_path = file_path.relative_to(package_dir)
                    zf.write(file_path, arc_path)


def create_repair_package_cli():
    """CLI interface for creating repair packages"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Create comprehensive sync repair packages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s analysis.json original.mov --episode "Episode 101"
  %(prog)s analysis.json original.mov --repaired repaired.mov --episode "My Show S01E01"
  %(prog)s analysis.json original.mov --output-dir ./packages --no-zip
        """
    )
    
    parser.add_argument('analysis_file', help='Analysis JSON file')
    parser.add_argument('original_file', help='Original video file')
    parser.add_argument('--repaired', help='Repaired video file (if available)')
    parser.add_argument('--episode', default='Episode', help='Episode name')
    parser.add_argument('--output-dir', default='./repair_packages', help='Output directory')
    parser.add_argument('--no-zip', action='store_true', help='Skip creating ZIP archive')
    parser.add_argument('--no-viz', action='store_true', help='Skip creating visualization')
    
    args = parser.parse_args()
    
    # Load analysis data
    try:
        with open(args.analysis_file, 'r') as f:
            analysis_data = json.load(f)
    except Exception as e:
        print(f"Error loading analysis file: {e}")
        return 1
    
    # Create packager
    packager = SyncRepairPackager(args.output_dir)
    
    print("🔧 Creating sync repair package...")
    
    # Create package
    result = packager.create_repair_package(
        original_file=args.original_file,
        analysis_data=analysis_data,
        repaired_file=args.repaired,
        episode_name=args.episode,
        include_visualization=not args.no_viz,
        create_zip=not args.no_zip
    )
    
    if result["success"]:
        print(f"✅ Package created successfully!")
        print(f"   Directory: {result['package_directory']}")
        print(f"   Files: {result['total_files']}")
        if "zip_file" in result:
            print(f"   Archive: {result['zip_file']}")
        return 0
    else:
        print(f"❌ Package creation failed: {result['error']}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(create_repair_package_cli())