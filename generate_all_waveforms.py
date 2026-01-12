#!/usr/bin/env python3
"""
Generate waveforms for all completed jobs in the database.

This script queries all completed jobs and reports, and generates waveform data
for QC visualization. Run this once to populate the waveform cache
for existing jobs.

Usage:
    python generate_all_waveforms.py [--limit N] [--force]
"""

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from sync_analyzer.db.job_db import list_jobs
from sync_analyzer.utils.waveform_generator import WaveformGenerator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_completed_jobs(limit: int = 1000) -> list:
    """Get all completed jobs from the jobs database."""
    jobs = list_jobs(status='completed', limit=limit)
    logger.info(f"Found {len(jobs)} completed jobs in jobs database")
    return jobs


def get_reports(limit: int = 1000) -> list:
    """Get all reports from the reports database."""
    reports_db = PROJECT_ROOT / 'sync_reports' / 'sync_reports.db'
    
    if not reports_db.exists():
        logger.warning(f"Reports database not found: {reports_db}")
        return []
    
    try:
        conn = sqlite3.connect(str(reports_db))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(f'''
            SELECT analysis_id, master_file, dub_file 
            FROM reports 
            ORDER BY created_at DESC 
            LIMIT {limit}
        ''')
        reports = [dict(row) for row in cursor.fetchall()]
        conn.close()
        logger.info(f"Found {len(reports)} reports in reports database")
        return reports
    except Exception as e:
        logger.error(f"Error reading reports database: {e}")
        return []


def extract_file_paths(job: dict) -> tuple:
    """Extract master and dub file paths from job request params."""
    try:
        params_str = job.get('request_params', '{}')
        if isinstance(params_str, str):
            params = json.loads(params_str)
        else:
            params = params_str
        
        master = params.get('master_file') or params.get('master_path')
        dub = params.get('dub_file') or params.get('dub_path')
        
        return master, dub
    except Exception as e:
        logger.warning(f"Failed to parse params for job {job.get('job_id')}: {e}")
        return None, None


def main():
    parser = argparse.ArgumentParser(description='Generate waveforms for all completed jobs')
    parser.add_argument('--limit', type=int, default=1000, help='Max number of jobs to process')
    parser.add_argument('--force', action='store_true', help='Force regeneration even if cached')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without doing it')
    parser.add_argument('--source', choices=['all', 'jobs', 'reports'], default='all',
                        help='Which database to process')
    args = parser.parse_args()
    
    # Initialize waveform generator
    generator = WaveformGenerator()
    logger.info(f"Waveform cache directory: {generator.output_dir}")
    
    # Collect all items to process
    items = []
    
    if args.source in ['all', 'jobs']:
        jobs = get_completed_jobs(args.limit)
        for job in jobs:
            job_id = job.get('job_id', 'unknown')
            master_path, dub_path = extract_file_paths(job)
            if master_path and dub_path:
                items.append({
                    'job_id': job_id,
                    'master_path': master_path,
                    'dub_path': dub_path,
                    'source': 'jobs'
                })
    
    if args.source in ['all', 'reports']:
        reports = get_reports(args.limit)
        for report in reports:
            job_id = report.get('analysis_id', 'unknown')
            master_path = report.get('master_file')
            dub_path = report.get('dub_file')
            if master_path and dub_path:
                # Avoid duplicates
                if not any(item['job_id'] == job_id for item in items):
                    items.append({
                        'job_id': job_id,
                        'master_path': master_path,
                        'dub_path': dub_path,
                        'source': 'reports'
                    })
    
    if not items:
        logger.info("No items to process")
        return
    
    logger.info(f"Total items to process: {len(items)}")
    
    # Process each item
    success_count = 0
    skip_count = 0
    error_count = 0
    files_not_found = 0
    
    for i, item in enumerate(items, 1):
        job_id = item['job_id']
        master_path = item['master_path']
        dub_path = item['dub_path']
        
        # Check if files exist
        master_exists = Path(master_path).exists()
        dub_exists = Path(dub_path).exists()
        
        if not master_exists or not dub_exists:
            logger.debug(f"[{i}/{len(items)}] Files not found: {job_id}")
            files_not_found += 1
            continue
        
        # Check if waveforms already cached
        cache_file = generator.output_dir / f"{job_id}_waveforms.json"
        if cache_file.exists() and not args.force:
            logger.debug(f"[{i}/{len(items)}] Already cached: {job_id}")
            skip_count += 1
            continue
        
        if args.dry_run:
            logger.info(f"[{i}/{len(items)}] Would generate: {job_id}")
            logger.info(f"  Master: {Path(master_path).name}")
            logger.info(f"  Dub: {Path(dub_path).name}")
            continue
        
        # Generate waveforms
        try:
            logger.info(f"[{i}/{len(items)}] Generating waveforms for {job_id}...")
            result = generator.generate_pair(
                master_path,
                dub_path,
                job_id,
                force_regenerate=args.force
            )
            logger.info(f"  Master: {result['master']['width']} points, {result['master']['duration']:.1f}s")
            logger.info(f"  Dub: {result['dub']['width']} points, {result['dub']['duration']:.1f}s")
            success_count += 1
            
        except Exception as e:
            logger.error(f"[{i}/{len(items)}] Failed for {job_id}: {e}")
            error_count += 1
    
    # Summary
    logger.info("=" * 60)
    logger.info("WAVEFORM GENERATION COMPLETE")
    logger.info(f"  Total items: {len(items)}")
    logger.info(f"  Generated: {success_count}")
    logger.info(f"  Already cached: {skip_count}")
    logger.info(f"  Files not found: {files_not_found}")
    logger.info(f"  Errors: {error_count}")
    logger.info(f"  Cache directory: {generator.output_dir}")


if __name__ == '__main__':
    main()

