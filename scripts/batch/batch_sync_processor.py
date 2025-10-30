#!/usr/bin/env python3
"""
Batch Multi-GPU Sync Processor

Automatically processes multiple file pairs across available GPUs for maximum throughput.
"""

import os
import sys
import time
import json
import subprocess
import argparse
from pathlib import Path
from typing import List, Tuple, Dict
from concurrent.futures import ProcessPoolExecutor, as_completed

def get_gpu_count():
    """Get number of available GPUs"""
    try:
        result = subprocess.run(['nvidia-smi', '-L'], capture_output=True, text=True)
        return len([line for line in result.stdout.split('\n') if 'GPU' in line])
    except:
        return 0

def process_file_pair(args_tuple):
    """Process a single file pair - designed for multiprocessing"""
    master_file, dub_file, output_dir, chunk_size, extra_args = args_tuple
    
    pair_name = f"{Path(master_file).stem}_vs_{Path(dub_file).stem}"
    output_json = output_dir / f"{pair_name}_analysis.json"
    
    cmd = [
        'python', 'continuous_sync_monitor.py',
        master_file, dub_file,
        '--output', str(output_json),
        '--chunk-size', str(chunk_size),
        '--quiet'
    ]
    
    if extra_args:
        cmd.extend(extra_args)
    
    print(f"🚀 Starting analysis: {pair_name}")
    start_time = time.time()
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)  # 1 hour timeout
        duration = time.time() - start_time
        
        if result.returncode == 0:
            status = "✅ SUCCESS"
        elif result.returncode == 2:
            status = "⚠️ DRIFT DETECTED"
        else:
            status = "❌ FAILED"
            
        return {
            'pair_name': pair_name,
            'master_file': master_file,
            'dub_file': dub_file,
            'output_file': str(output_json),
            'status': status,
            'duration': duration,
            'return_code': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr
        }
        
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        return {
            'pair_name': pair_name,
            'master_file': master_file,
            'dub_file': dub_file,
            'output_file': str(output_json),
            'status': "⏰ TIMEOUT",
            'duration': duration,
            'return_code': -1,
            'error': 'Analysis timed out after 1 hour'
        }
    except Exception as e:
        duration = time.time() - start_time
        return {
            'pair_name': pair_name,
            'master_file': master_file,
            'dub_file': dub_file,
            'output_file': str(output_json),
            'status': "💥 ERROR", 
            'duration': duration,
            'return_code': -1,
            'error': str(e)
        }

def find_file_pairs(directory: str, pattern_pairs: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """Find matching file pairs in directory"""
    pairs = []
    directory = Path(directory)
    
    for master_pattern, dub_pattern in pattern_pairs:
        master_files = list(directory.rglob(master_pattern))
        dub_files = list(directory.rglob(dub_pattern))
        
        # Simple matching - same base directory
        for master in master_files:
            for dub in dub_files:
                if master.parent == dub.parent:
                    pairs.append((str(master), str(dub)))
                    
    return pairs

def main():
    parser = argparse.ArgumentParser(
        description="Batch Multi-GPU Sync Processor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process specific file pairs
  %(prog)s --pairs master1.mov dub1.mov master2.mov dub2.mov --output-dir results/

  # Auto-find pairs in directory  
  %(prog)s --directory /path/to/files --patterns "*Original*.mov:*v1.1*.mov" --output-dir results/
  
  # Use all 3 GPUs with custom settings
  %(prog)s --pairs file1.mov file2.mov file3.mov file4.mov --output-dir results/ --max-workers 3
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--pairs', nargs='+', help='List of master/dub file pairs (master1 dub1 master2 dub2 ...)')
    group.add_argument('--directory', help='Directory to search for file pairs')
    
    parser.add_argument('--patterns', nargs='+', default=['*Original*:*v1.1*'], 
                       help='Pattern pairs for auto-discovery (master_pattern:dub_pattern)')
    parser.add_argument('--output-dir', required=True, help='Output directory for results')
    parser.add_argument('--chunk-size', type=float, default=45.0, help='Chunk size in seconds')
    parser.add_argument('--max-workers', type=int, help='Max parallel processes (default: GPU count)')
    parser.add_argument('--plot', action='store_true', help='Generate plots for each analysis')
    
    args = parser.parse_args()
    
    # Prepare file pairs
    if args.pairs:
        if len(args.pairs) % 2 != 0:
            print("Error: --pairs requires even number of arguments (master1 dub1 master2 dub2 ...)")
            sys.exit(1)
        file_pairs = [(args.pairs[i], args.pairs[i+1]) for i in range(0, len(args.pairs), 2)]
    else:
        # Auto-discover pairs
        pattern_pairs = [tuple(p.split(':')) for p in args.patterns]
        file_pairs = find_file_pairs(args.directory, pattern_pairs)
        
    if not file_pairs:
        print("Error: No file pairs found")
        sys.exit(1)
        
    # Setup output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine worker count
    gpu_count = get_gpu_count()
    max_workers = args.max_workers or gpu_count or 1
    
    print(f"🔥 Batch Multi-GPU Sync Processor")
    print(f"📁 File pairs found: {len(file_pairs)}")
    print(f"🎯 GPUs available: {gpu_count}")
    print(f"⚡ Max parallel workers: {max_workers}")
    print(f"📊 Chunk size: {args.chunk_size}s")
    print(f"💾 Output directory: {output_dir}")
    print("-" * 60)
    
    # Prepare extra arguments
    extra_args = []
    if args.plot:
        extra_args.extend(['--plot', 'sync_plot.png'])
    
    # Process all pairs
    process_args = [(master, dub, output_dir, args.chunk_size, extra_args) 
                   for master, dub in file_pairs]
    
    start_time = time.time()
    results = []
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_pair = {executor.submit(process_file_pair, args): args[0:2] 
                         for args in process_args}
        
        for future in as_completed(future_to_pair):
            result = future.result()
            results.append(result)
            
            print(f"{result['status']} {result['pair_name']} ({result['duration']:.1f}s)")
            
    total_time = time.time() - start_time
    
    # Summary report
    print("\n" + "="*60)
    print("BATCH PROCESSING SUMMARY")
    print("="*60)
    
    success_count = sum(1 for r in results if r['status'] in ['✅ SUCCESS', '⚠️ DRIFT DETECTED'])
    failed_count = len(results) - success_count
    
    print(f"Total pairs processed: {len(results)}")
    print(f"Successful analyses: {success_count}")
    print(f"Failed analyses: {failed_count}")
    print(f"Total processing time: {total_time/60:.1f} minutes")
    print(f"Average time per pair: {total_time/len(results):.1f} seconds")
    print(f"Throughput: {len(results)/(total_time/60):.1f} pairs/minute")
    
    # Detailed results
    print(f"\nDetailed Results:")
    for result in results:
        print(f"  {result['status']} {result['pair_name']} -> {Path(result['output_file']).name}")
    
    # Export summary
    summary_file = output_dir / "batch_processing_summary.json"
    with open(summary_file, 'w') as f:
        json.dump({
            'summary': {
                'total_pairs': len(results),
                'successful': success_count,
                'failed': failed_count,
                'total_time_seconds': total_time,
                'average_time_per_pair': total_time/len(results),
                'throughput_pairs_per_minute': len(results)/(total_time/60),
                'gpu_count': gpu_count,
                'max_workers': max_workers
            },
            'results': results
        }, f, indent=2)
    
    print(f"\n📋 Summary exported to: {summary_file}")
    
    if failed_count == 0:
        print(f"\n🎉 All analyses completed successfully!")
        sys.exit(0)
    else:
        print(f"\n⚠️  {failed_count} analyses failed - check logs for details")
        sys.exit(1)

if __name__ == "__main__":
    main()