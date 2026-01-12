"""
CSV Batch Import API

Provides CSV file upload for batch sync analysis jobs.
Auto-detects standard vs componentized mode based on grouping rows by master file.

CSV Format expected:
  AREF,Wild
  /path/to/master.mp4,/path/to/dub.mxf
  /path/to/master.mp4,/path/to/another_dub.mxf  (same master = componentized)
  /path/to/other.mp4,/path/to/audio.mxf  (different master = standard)
"""

import csv
import io
import re
import uuid
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from pydantic import BaseModel, Field

from ....services.componentized_service import (
    is_safe_path,
    run_componentized_analysis,
)
from ....services.job_manager import job_manager
from ....tasks.analysis_tasks import run_componentized_analysis_task

logger = logging.getLogger(__name__)
router = APIRouter()


# Request/Response Models

class CSVImportResult(BaseModel):
    """Result of CSV import."""
    success: bool
    total_rows: int
    jobs_created: int
    standard_jobs: int
    componentized_jobs: int
    errors: List[str] = []
    jobs: List[Dict[str, Any]] = []


class ImportedJob(BaseModel):
    """A single imported job."""
    id: str
    type: str  # 'standard' or 'componentized'
    master_path: str
    master_name: str
    components: List[Dict[str, str]]  # [{path, label, name}]
    status: str = "queued"


# Component label extraction patterns
LABEL_PATTERNS = [
    # _a0, _a1, _a2, _a3 patterns (common for MXF)
    (r'_a(\d+)\.', lambda m: f'a{m.group(1)}'),
    # _A, _B, _C, _D patterns
    (r'_([A-H])\.', lambda m: m.group(1)),
    # 5_1, 2_0_LTRT patterns
    (r'[_-]5[_-]1[_-]?', lambda m: '5.1'),
    (r'[_-]2[_-]0[_-]?LTRT', lambda m: '2.0 LTRT'),
    (r'[_-]2[_-]0[_-]?', lambda m: '2.0'),
    (r'[_-]STEREO', lambda m: 'Stereo'),
    # Channel names
    (r'[_-](LT|Lt|lt)\.', lambda m: 'Lt'),
    (r'[_-](RT|Rt|rt)\.', lambda m: 'Rt'),
    (r'[_-](C|CENTER|Center)\.', lambda m: 'C'),
    (r'[_-](LFE|Lfe|lfe)\.', lambda m: 'LFE'),
    (r'[_-](LS|Ls|ls)\.', lambda m: 'Ls'),
    (r'[_-](RS|Rs|rs)\.', lambda m: 'Rs'),
    # 1_2, 3_4, 5_6, 7_8, 9_10 patterns
    (r'[_-](\d+)[_-](\d+)[_-]([A-Z])\.', lambda m: f'{m.group(1)}_{m.group(2)} ({m.group(3)})'),
    (r'[_-](\d+)[_-](\d+)\.', lambda m: f'{m.group(1)}_{m.group(2)}'),
]


def extract_component_label(filename: str, index: int) -> str:
    """
    Extract component label from filename.
    
    Args:
        filename: Component filename
        index: Component index (fallback)
        
    Returns:
        Extracted label or fallback like 'c0', 'c1', etc.
    """
    for pattern, extractor in LABEL_PATTERNS:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            return extractor(match)
    
    # Fallback to index-based label
    return f'c{index}'


def parse_csv_content(content: str) -> List[Dict[str, str]]:
    """
    Parse CSV content into list of master/dub pairs.
    
    Args:
        content: CSV file content
        
    Returns:
        List of dicts with 'master' and 'dub' keys
    """
    rows = []
    
    # Try to detect delimiter
    lines = content.strip().split('\n')
    if not lines:
        return rows
    
    # Check first line for delimiter
    first_line = lines[0]
    delimiter = ','
    if '\t' in first_line and ',' not in first_line:
        delimiter = '\t'
    elif ';' in first_line and ',' not in first_line:
        delimiter = ';'
    
    reader = csv.reader(io.StringIO(content), delimiter=delimiter)
    
    # Read header
    header = next(reader, None)
    if not header:
        return rows
    
    # Normalize header names
    header = [h.strip().lower() for h in header]
    
    # Find column indices
    master_col = None
    dub_col = None
    
    # Common header names for master
    master_names = ['aref', 'master', 'master_file', 'reference', 'ref', 'source']
    # Common header names for dub
    dub_names = ['wild', 'dub', 'dub_file', 'component', 'audio', 'target']
    
    for i, h in enumerate(header):
        if h in master_names:
            master_col = i
        elif h in dub_names:
            dub_col = i
    
    # If no match found, assume first two columns
    if master_col is None:
        master_col = 0
    if dub_col is None:
        dub_col = 1 if len(header) > 1 else 0
    
    logger.info(f"CSV columns detected: master={header[master_col] if master_col < len(header) else master_col}, "
                f"dub={header[dub_col] if dub_col < len(header) else dub_col}")
    
    # Parse data rows
    for row_num, row in enumerate(reader, start=2):
        if len(row) < 2:
            continue
        
        master = row[master_col].strip() if master_col < len(row) else ''
        dub = row[dub_col].strip() if dub_col < len(row) else ''
        
        if master and dub:
            rows.append({
                'master': master,
                'dub': dub,
                'row': row_num
            })
    
    return rows


def group_by_master(rows: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    """
    Group rows by master file path.
    
    Args:
        rows: List of parsed CSV rows
        
    Returns:
        Dict mapping master path to list of dub paths
    """
    groups = defaultdict(list)
    
    for row in rows:
        master = row['master']
        groups[master].append(row)
    
    return dict(groups)


def create_job_from_group(
    master_path: str, 
    dub_rows: List[Dict[str, str]],
    job_index: int
) -> Dict[str, Any]:
    """
    Create a job definition from a grouped master/dubs set.
    
    Args:
        master_path: Path to master file
        dub_rows: List of dub row dicts
        job_index: Index for job ID
        
    Returns:
        Job definition dict
    """
    master_name = Path(master_path).name
    
    # Build components list with labels
    components = []
    for i, row in enumerate(dub_rows):
        dub_path = row['dub']
        dub_name = Path(dub_path).name
        label = extract_component_label(dub_name, i)
        
        components.append({
            'path': dub_path,
            'name': dub_name,
            'label': label,
            'row': row.get('row', i)
        })
    
    # Determine job type
    job_type = 'standard' if len(components) == 1 else 'componentized'
    
    return {
        'id': f'csv-{job_index}-{uuid.uuid4().hex[:8]}',
        'type': job_type,
        'master': {
            'path': master_path,
            'name': master_name
        },
        'components': components,
        'status': 'queued',
        'progress': 0,
        'createdAt': datetime.utcnow().isoformat() + 'Z'
    }


@router.post("/import", response_model=CSVImportResult)
async def import_csv(
    file: UploadFile = File(...),
    auto_queue: bool = Form(default=True),
    background_tasks: BackgroundTasks = None
):
    """
    Import CSV file and create batch jobs.
    
    The CSV should have columns for master and dub file paths.
    Rows with the same master file are grouped as componentized jobs.
    
    Args:
        file: CSV file upload
        auto_queue: If True, automatically queue jobs for processing
        
    Returns:
        Import result with created jobs
    """
    logger.info(f"CSV import started: {file.filename}")
    
    # Validate file type
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported"
        )
    
    errors = []
    
    try:
        # Read file content
        content = await file.read()
        
        # Try UTF-8 first, then Latin-1
        try:
            csv_content = content.decode('utf-8')
        except UnicodeDecodeError:
            csv_content = content.decode('latin-1')
        
        # Parse CSV
        rows = parse_csv_content(csv_content)
        total_rows = len(rows)
        
        if total_rows == 0:
            return CSVImportResult(
                success=False,
                total_rows=0,
                jobs_created=0,
                standard_jobs=0,
                componentized_jobs=0,
                errors=["No valid rows found in CSV"]
            )
        
        logger.info(f"Parsed {total_rows} rows from CSV")
        
        # Group by master
        groups = group_by_master(rows)
        logger.info(f"Grouped into {len(groups)} master(s)")
        
        # Create jobs
        jobs = []
        standard_count = 0
        componentized_count = 0
        
        for i, (master_path, dub_rows) in enumerate(groups.items()):
            # Validate paths
            if not is_safe_path(master_path):
                errors.append(f"Master path not allowed: {master_path}")
                continue
            
            for row in dub_rows:
                if not is_safe_path(row['dub']):
                    errors.append(f"Dub path not allowed (row {row.get('row', '?')}): {row['dub']}")
            
            # Filter out invalid dubs
            valid_dubs = [r for r in dub_rows if is_safe_path(r['dub'])]
            if not valid_dubs:
                continue
            
            # Check if files exist
            if not Path(master_path).exists():
                errors.append(f"Master file not found: {master_path}")
                continue
            
            missing_dubs = [r for r in valid_dubs if not Path(r['dub']).exists()]
            for r in missing_dubs:
                errors.append(f"Dub file not found (row {r.get('row', '?')}): {r['dub']}")
            
            valid_dubs = [r for r in valid_dubs if Path(r['dub']).exists()]
            if not valid_dubs:
                continue
            
            # Create job
            job = create_job_from_group(master_path, valid_dubs, i)
            jobs.append(job)
            
            if job['type'] == 'standard':
                standard_count += 1
            else:
                componentized_count += 1
        
        logger.info(f"Created {len(jobs)} jobs: {standard_count} standard, {componentized_count} componentized")
        
        return CSVImportResult(
            success=True,
            total_rows=total_rows,
            jobs_created=len(jobs),
            standard_jobs=standard_count,
            componentized_jobs=componentized_count,
            errors=errors,
            jobs=jobs
        )
        
    except Exception as e:
        logger.error(f"CSV import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import/preview")
async def preview_csv_import(file: UploadFile = File(...)):
    """
    Preview CSV import without creating jobs.
    
    Returns grouping information without queuing jobs.
    """
    logger.info(f"CSV preview: {file.filename}")
    
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")
    
    try:
        content = await file.read()
        try:
            csv_content = content.decode('utf-8')
        except UnicodeDecodeError:
            csv_content = content.decode('latin-1')
        
        rows = parse_csv_content(csv_content)
        groups = group_by_master(rows)
        
        preview = {
            'total_rows': len(rows),
            'unique_masters': len(groups),
            'groups': []
        }
        
        for master_path, dub_rows in groups.items():
            master_name = Path(master_path).name
            job_type = 'standard' if len(dub_rows) == 1 else 'componentized'
            
            components = []
            for i, row in enumerate(dub_rows):
                dub_name = Path(row['dub']).name
                label = extract_component_label(dub_name, i)
                components.append({
                    'name': dub_name,
                    'label': label,
                    'exists': Path(row['dub']).exists()
                })
            
            preview['groups'].append({
                'master': master_name,
                'master_exists': Path(master_path).exists(),
                'type': job_type,
                'component_count': len(components),
                'components': components
            })
        
        return preview
        
    except Exception as e:
        logger.error(f"CSV preview failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

