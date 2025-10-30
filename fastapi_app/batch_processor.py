#!/usr/bin/env python3
"""
Simple Python script for batch processing sync analysis via the API.
"""

import requests
import json
import time
import sys
import argparse
from datetime import datetime

API_BASE = "http://localhost:8000/api/v1"

def upload_batch_csv(csv_file_path, description="Batch processing", priority="normal"):
    """Upload a batch CSV file."""
    url = f"{API_BASE}/analysis/batch/upload-csv"
    
    try:
        with open(csv_file_path, 'rb') as f:
            files = {'file': f}
            data = {
                'description': description,
                'priority': priority
            }
            
            response = requests.post(url, files=files, data=data)
            response.raise_for_status()
            return response.json()
    except FileNotFoundError:
        print(f"Error: CSV file '{csv_file_path}' not found")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Error uploading CSV: {e}")
        sys.exit(1)

def start_batch_processing(batch_id, parallel_jobs=2, priority="normal"):
    """Start batch processing."""
    url = f"{API_BASE}/analysis/batch/{batch_id}/start"
    
    data = {
        'parallel_jobs': parallel_jobs,
        'priority': priority
    }
    
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error starting batch processing: {e}")
        sys.exit(1)

def monitor_batch_progress(batch_id, check_interval=10, verbose=True):
    """Monitor batch processing progress."""
    url = f"{API_BASE}/analysis/batch/{batch_id}/status"
    
    if verbose:
        print(f"Monitoring batch {batch_id}...")
        print("=" * 60)
    
    start_time = datetime.now()
    
    while True:
        try:
            response = requests.get(url, params={'include_details': False})
            response.raise_for_status()
            status_data = response.json()
            
            status = status_data['status']
            progress = status_data['progress']
            completed = status_data['items_completed']
            total = status_data['items_total']
            failed = status_data['items_failed']
            processing = status_data['items_processing']
            
            elapsed = datetime.now() - start_time
            elapsed_str = str(elapsed).split('.')[0]  # Remove microseconds
            
            if verbose:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Status: {status.upper()}")
                print(f"  Progress: {progress:.1f}% | Items: {completed}/{total} completed, {failed} failed, {processing} processing")
                print(f"  Elapsed: {elapsed_str}")
                
                if 'estimated_completion' in status_data and status_data['estimated_completion']:
                    est_completion = status_data['estimated_completion']
                    print(f"  Estimated completion: {est_completion}")
                print("-" * 60)
            
            if status in ['completed', 'failed', 'cancelled']:
                return status_data
            
            time.sleep(check_interval)
            
        except requests.exceptions.RequestException as e:
            print(f"Error monitoring progress: {e}")
            time.sleep(check_interval)
        except KeyboardInterrupt:
            print("\nMonitoring interrupted by user")
            return None

def get_batch_results(batch_id):
    """Get batch processing results."""
    url = f"{API_BASE}/analysis/batch/{batch_id}/results"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error getting batch results: {e}")
        sys.exit(1)

def print_summary(results):
    """Print a formatted summary of batch results."""
    print("\n" + "=" * 60)
    print("BATCH PROCESSING SUMMARY")
    print("=" * 60)
    
    summary = results['summary']
    print(f"Batch ID: {results['batch_id']}")
    print(f"Final Status: {results['status'].upper()}")
    print(f"Total Items: {summary['items_total']}")
    print(f"Completed Successfully: {summary['items_completed']}")
    print(f"Failed: {summary['items_failed']}")
    
    if summary['average_confidence'] > 0:
        print(f"Average Confidence: {summary['average_confidence']:.3f}")
    
    print(f"Total Processing Time: {summary['processing_time_seconds']:.1f} seconds")
    
    # Show individual results
    print("\nINDIVIDUAL RESULTS:")
    print("-" * 60)
    
    for result in results['results']:
        print(f"Item {result['item_id']}: {result['status'].upper()}")
        
        if result['status'] == 'completed' and result.get('result'):
            res = result['result']
            print(f"  Offset: {res['offset_seconds']:.3f} seconds")
            print(f"  Confidence: {res['confidence']:.3f}")
            print(f"  Method: {res['method_used']}")
        elif result['status'] == 'failed':
            print(f"  Error: {result.get('error', 'Unknown error')}")
        
        print()

def main():
    parser = argparse.ArgumentParser(
        description="Process batch sync analysis via API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python batch_processor.py sample_batch.csv
  python batch_processor.py batch.csv --jobs 4 --priority high
  python batch_processor.py batch.csv --description "Daily batch" --output results.json
        """
    )
    
    parser.add_argument('csv_file', help='Path to CSV file with batch items')
    parser.add_argument('--description', '-d', default='Batch processing', help='Batch description')
    parser.add_argument('--priority', '-p', choices=['low', 'normal', 'high'], default='normal', help='Processing priority')
    parser.add_argument('--jobs', '-j', type=int, default=2, help='Number of parallel jobs (1-8)')
    parser.add_argument('--output', '-o', help='Output JSON file for results')
    parser.add_argument('--interval', '-i', type=int, default=10, help='Status check interval in seconds')
    parser.add_argument('--quiet', '-q', action='store_true', help='Minimal output')
    
    args = parser.parse_args()
    
    try:
        # Validate parallel jobs
        if args.jobs < 1 or args.jobs > 8:
            print("Error: Number of parallel jobs must be between 1 and 8")
            sys.exit(1)
        
        if not args.quiet:
            print("Professional Audio Sync Analyzer - Batch Processor")
            print("=" * 60)
        
        # Upload CSV
        if not args.quiet:
            print(f"📤 Uploading batch CSV: {args.csv_file}")
        
        upload_result = upload_batch_csv(args.csv_file, args.description, args.priority)
        batch_id = upload_result['batch_id']
        items_count = upload_result['items_count']
        
        if not args.quiet:
            print(f"✅ Batch uploaded successfully!")
            print(f"   Batch ID: {batch_id}")
            print(f"   Items: {items_count}")
            print()
        
        # Start processing
        if not args.quiet:
            print(f"🚀 Starting batch processing with {args.jobs} parallel jobs...")
        
        start_result = start_batch_processing(batch_id, args.jobs, args.priority)
        
        if not args.quiet:
            print(f"✅ Batch processing started!")
            print(f"   Processing: {start_result['items_processing']} items initially")
            if 'estimated_completion' in start_result:
                print(f"   Estimated completion: {start_result['estimated_completion']}")
            print()
        
        # Monitor progress
        final_status = monitor_batch_progress(batch_id, args.interval, not args.quiet)
        
        if final_status is None:
            print("Monitoring cancelled by user")
            sys.exit(0)
        
        # Get results
        if not args.quiet:
            print("📊 Getting batch results...")
        
        results = get_batch_results(batch_id)
        
        # Save results to file if specified
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            if not args.quiet:
                print(f"💾 Results saved to {args.output}")
        
        # Print summary
        if not args.quiet:
            print_summary(results)
        else:
            # Quiet mode - just print essential info
            summary = results['summary']
            print(f"Batch {batch_id}: {results['status']} - {summary['items_completed']}/{summary['items_total']} completed")
        
        # Exit with appropriate code
        if results['status'] == 'completed':
            sys.exit(0)
        else:
            sys.exit(1)
        
    except KeyboardInterrupt:
        print("\n🛑 Process interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()