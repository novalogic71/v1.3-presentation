#!/usr/bin/env python3
"""
Batch Sync Repair System

Processes multiple files from analysis results and applies intelligent repairs.
Integrates with the CSV batch processing workflow.
"""

import os
import sys
import csv
import json
import time
import argparse
import subprocess
from pathlib import Path
from typing import List, Dict, Any
from concurrent.futures import ProcessPoolExecutor, as_completed

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from scripts.repair.intelligent_sync_repair import IntelligentSyncRepairer

def repair_from_analysis_result(repair_args):
    """Repair a single file from batch analysis results"""
    analysis_result, input_file, master_file, output_dir, validate_repairs = repair_args
    
    episode_name = analysis_result.get('episode', 'Unknown')
    analysis_file = analysis_result.get('json_output')
    
    if not analysis_file or not os.path.exists(analysis_file):
        return {
            'episode': episode_name,
            'status': 'ANALYSIS_MISSING',
            'error': 'Analysis file not found',
            'input_file': input_file
        }
    
    # Generate output filename
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    safe_name = "".join(c for c in episode_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_name = safe_name.replace(' ', '_')
    output_file = output_dir / f"{safe_name}_REPAIRED.mov"
    
    print(f"🔧 Repairing: {episode_name}")
    start_time = time.time()
    
    try:
        repairer = IntelligentSyncRepairer()
        
        # Perform intelligent repair
        repair_result = repairer.repair_file(input_file, analysis_file, str(output_file))
        
        if not repair_result["success"]:
            return {
                'episode': episode_name,
                'status': 'REPAIR_FAILED',
                'error': repair_result.get('error', 'Unknown repair error'),
                'input_file': input_file,
                'duration': time.time() - start_time
            }
        
        # Validate repair if requested and master file available
        validation_result = None
        if validate_repairs and master_file and os.path.exists(master_file):
            validation_result = repairer.validate_repair(input_file, str(output_file), master_file)
        
        duration = time.time() - start_time
        
        return {
            'episode': episode_name,
            'status': 'REPAIR_SUCCESS',
            'input_file': input_file,
            'output_file': str(output_file),
            'repair_type': repair_result['repair_type'],
            'audio_channels': repair_result['audio_channels'],
            'confidence_score': repair_result['confidence_score'],
            'segments_count': repair_result.get('segments_count', 1),
            'validation': validation_result,
            'duration': duration
        }
        
    except Exception as e:
        return {
            'episode': episode_name,
            'status': 'REPAIR_ERROR',
            'error': str(e),
            'input_file': input_file,
            'duration': time.time() - start_time
        }

def load_batch_analysis_results(batch_summary_file: str) -> List[Dict[str, Any]]:
    """Load analysis results from batch processing summary"""
    try:
        with open(batch_summary_file, 'r') as f:
            batch_data = json.load(f)
        
        # Get successful analysis results
        analysis_results = []
        for result in batch_data.get('episode_results', []):
            if result.get('status') in ['SUCCESS', 'DRIFT_DETECTED'] and result.get('json_output'):
                analysis_results.append(result)
        
        return analysis_results
        
    except Exception as e:
        print(f"Error loading batch analysis results: {e}")
        return []

def create_repair_csv_mapping(csv_file: str, analysis_results: List[Dict]) -> List[Dict]:
    """Create mapping between CSV entries and analysis results for repair"""
    # Load original CSV to get file paths
    csv_data = []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            csv_data.append(row)
    
    # Match analysis results with CSV entries
    repair_mapping = []
    for analysis in analysis_results:
        episode_name = analysis.get('episode', '')
        
        # Find matching CSV entry
        matching_csv = None
        for csv_row in csv_data:
            if csv_row.get('episode_name') == episode_name:
                matching_csv = csv_row
                break
        
        if matching_csv:
            repair_mapping.append({
                'analysis': analysis,
                'dub_file': matching_csv.get('dub_file'),
                'master_file': matching_csv.get('master_file'),
                'episode_name': episode_name
            })
    
    return repair_mapping

def main():
    parser = argparse.ArgumentParser(
        description="Batch Sync Repair System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This tool repairs multiple files based on batch analysis results.

Workflow:
1. Run csv_batch_processor.py to analyze files
2. Run this tool to repair files based on analysis
3. Validates repairs against master files

Examples:
  %(prog)s --batch-summary results/batch_processing_summary.json --csv original.csv --output-dir repaired/
  %(prog)s --batch-summary results/batch_processing_summary.json --csv original.csv --output-dir repaired/ --validate --max-workers 4
        """
    )
    
    parser.add_argument('--batch-summary', required=True, 
                       help='Batch processing summary JSON file from csv_batch_processor.py')
    parser.add_argument('--csv', required=True, 
                       help='Original CSV file used for batch processing')
    parser.add_argument('--output-dir', required=True, 
                       help='Output directory for repaired files')
    parser.add_argument('--validate', action='store_true', 
                       help='Validate repairs against master files')
    parser.add_argument('--max-workers', type=int, 
                       help='Maximum parallel repair processes')
    parser.add_argument('--preserve-quality', action='store_true', 
                       help='Use higher quality encoding (slower)')
    
    args = parser.parse_args()
    
    # Validate input files
    if not os.path.exists(args.batch_summary):
        print(f"Error: Batch summary file not found: {args.batch_summary}")
        sys.exit(1)
    
    if not os.path.exists(args.csv):
        print(f"Error: CSV file not found: {args.csv}")
        sys.exit(1)
    
    print("🔧 Batch Sync Repair System")
    print("=" * 50)
    
    # Load analysis results
    analysis_results = load_batch_analysis_results(args.batch_summary)
    if not analysis_results:
        print("No successful analysis results found for repair")
        sys.exit(1)
    
    print(f"Found {len(analysis_results)} analysis results for repair")
    
    # Create repair mapping
    repair_mapping = create_repair_csv_mapping(args.csv, analysis_results)
    if not repair_mapping:
        print("Could not match analysis results with CSV entries")
        sys.exit(1)
    
    print(f"Mapped {len(repair_mapping)} files for repair")
    
    # Determine worker count
    max_workers = args.max_workers or min(4, len(repair_mapping))
    
    print(f"Using {max_workers} parallel workers")
    print(f"Output directory: {args.output_dir}")
    print(f"Validation: {'Enabled' if args.validate else 'Disabled'}")
    print("-" * 50)
    
    # Prepare repair arguments
    repair_args = []
    for mapping in repair_mapping:
        repair_args.append((
            mapping['analysis'],
            mapping['dub_file'],
            mapping['master_file'],
            args.output_dir,
            args.validate
        ))
    
    # Process repairs
    start_time = time.time()
    repair_results = []
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_episode = {executor.submit(repair_from_analysis_result, args): args[0]['episode'] 
                            for args in repair_args}
        
        for future in as_completed(future_to_episode):
            result = future.result()
            repair_results.append(result)
            
            # Status icons
            status_icon = {
                'REPAIR_SUCCESS': '✅',
                'REPAIR_FAILED': '❌', 
                'REPAIR_ERROR': '💥',
                'ANALYSIS_MISSING': '📊'
            }.get(result['status'], '❓')
            
            print(f"{status_icon} {result['episode']} ({result.get('duration', 0):.1f}s)")
            
            # Show repair details for successful repairs
            if result['status'] == 'REPAIR_SUCCESS':
                repair_type = result.get('repair_type', 'unknown')
                channels = result.get('audio_channels', 0)
                confidence = result.get('confidence_score', 0)
                
                print(f"   └─ {repair_type} repair, {channels} audio channels, {confidence:.2f} confidence")
                
                # Show validation results if available
                if result.get('validation') and result['validation'].get('success'):
                    validation = result['validation']
                    quality = validation.get('quality', 'unknown')
                    max_offset = validation.get('max_offset', 0)
                    print(f"   └─ Validation: {quality} (max offset: {max_offset:.3f}s)")
    
    total_time = time.time() - start_time
    
    # Generate summary
    print("\n" + "=" * 50)
    print("BATCH REPAIR SUMMARY")
    print("=" * 50)
    
    successful_repairs = [r for r in repair_results if r['status'] == 'REPAIR_SUCCESS']
    failed_repairs = [r for r in repair_results if r['status'] != 'REPAIR_SUCCESS']
    
    print(f"Total files processed: {len(repair_results)}")
    print(f"Successful repairs: {len(successful_repairs)}")
    print(f"Failed repairs: {len(failed_repairs)}")
    print(f"Total processing time: {total_time/60:.1f} minutes")
    print(f"Average time per file: {total_time/len(repair_results):.1f} seconds")
    
    # Repair type breakdown
    if successful_repairs:
        repair_types = {}
        total_validation_quality = {'excellent': 0, 'good': 0, 'acceptable': 0, 'poor': 0}
        
        for result in successful_repairs:
            repair_type = result.get('repair_type', 'unknown')
            repair_types[repair_type] = repair_types.get(repair_type, 0) + 1
            
            # Count validation quality
            validation = result.get('validation')
            if validation and validation.get('success'):
                quality = validation.get('quality', 'unknown')
                if quality in total_validation_quality:
                    total_validation_quality[quality] += 1
        
        print(f"\nRepair type breakdown:")
        for repair_type, count in repair_types.items():
            print(f"  {repair_type}: {count}")
        
        if args.validate:
            print(f"\nValidation quality breakdown:")
            for quality, count in total_validation_quality.items():
                if count > 0:
                    print(f"  {quality}: {count}")
    
    # Export detailed results
    output_dir = Path(args.output_dir)
    results_file = output_dir / "repair_summary.json"
    
    summary_data = {
        'repair_summary': {
            'total_files': len(repair_results),
            'successful_repairs': len(successful_repairs),
            'failed_repairs': len(failed_repairs),
            'total_time_seconds': total_time,
            'average_time_per_file': total_time / len(repair_results),
            'validation_enabled': args.validate,
            'max_workers': max_workers
        },
        'repair_results': repair_results
    }
    
    with open(results_file, 'w') as f:
        json.dump(summary_data, f, indent=2)
    
    print(f"\n📋 Detailed results: {results_file}")
    
    # Show failed repairs
    if failed_repairs:
        print(f"\n❌ Failed repairs:")
        for result in failed_repairs:
            print(f"  {result['episode']}: {result.get('error', 'Unknown error')}")
    
    if len(successful_repairs) == len(repair_results):
        print(f"\n🎉 All files repaired successfully!")
        sys.exit(0)
    else:
        print(f"\n⚠️ {len(failed_repairs)} files failed to repair")
        sys.exit(1)

if __name__ == "__main__":
    main()