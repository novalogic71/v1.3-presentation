#!/usr/bin/env python3
"""
Reports endpoints for generating and retrieving analysis reports.
"""

import logging
import json
import subprocess
from typing import List, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, Path as FastAPIPath, Query, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app.models.sync_models import (
    AnalysisReport, ReportListResponse, SyncAnalysisResult
)
from app.services.sync_analyzer_service import sync_analyzer_service

logger = logging.getLogger(__name__)

router = APIRouter()

class FormattedReportResponse(BaseModel):
    success: bool
    report_html: str
    report_markdown: str
    analysis_id: str
    episode_name: Optional[str] = None

class BatchUploadResponse(BaseModel):
    success: bool
    message: str
    batch_id: str
    episodes_count: int
    csv_preview: List[dict]

@router.get("/debug/{analysis_id}")
async def debug_analysis(analysis_id: str):
    """Debug endpoint to show raw database result."""
    try:
        from sync_analyzer.db.report_db import get_by_analysis_id
        from pathlib import Path
        db_path = Path("../sync_reports/sync_reports.db")
        result = get_by_analysis_id(analysis_id, db_path)
        if not result:
            raise HTTPException(status_code=404, detail="Analysis not found")
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"debug_analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search")
async def search_latest_report(master_file: str, dub_file: str):
    """Return the latest persisted report for a given master/dub pair from the DB."""
    try:
        from sync_analyzer.db.report_db import get_latest_by_pair
        rec = get_latest_by_pair(master_file, dub_file)
        if not rec:
            raise HTTPException(status_code=404, detail="No report found for specified files")
        return {"success": True, "report": rec}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"search_latest_report error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{analysis_id}", response_model=AnalysisReport)
async def get_analysis_report(
    analysis_id: str = FastAPIPath(..., description="Analysis identifier")
):
    """
    Get analysis report for a completed analysis.
    
    This endpoint returns a comprehensive report for a completed sync analysis,
    including all results, metadata, and recommendations.
    
    ## Example Response
    
    ```json
    {
      "report_id": "report_20250827_143052",
      "analysis_result": {
        "analysis_id": "analysis_20250827_143052_abc12345",
        "status": "completed",
        "consensus_offset": {
          "offset_seconds": -2.456,
          "confidence": 0.94
        }
      },
      "report_format": "json",
      "generated_at": "2025-08-27T14:30:52Z",
      "file_path": "/reports/sync_report_20250827_143052.json",
      "file_size": 2048
    }
    ```
    
    ## Curl Example
    
    ```bash
    curl -X GET "http://localhost:8000/api/v1/reports/analysis_20250827_143052_abc12345"
    ```
    """
    try:
        # Get analysis result
        analysis_result = await sync_analyzer_service.get_analysis_result(analysis_id)
        
        if not analysis_result:
            raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")
        
        # Create report
        report = AnalysisReport(
            report_id=f"report_{analysis_id}",
            analysis_result=analysis_result,
            report_format="json",
            generated_at=analysis_result.completed_at or analysis_result.created_at
        )
        
        return report
        
    except Exception as e:
        logger.error(f"Error getting analysis report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=ReportListResponse)
async def list_reports(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page")
):
    """
    List all available reports with pagination.
    
    ## Example Response
    
    ```json
    {
      "success": true,
      "reports": [
        {
          "report_id": "report_20250827_143052",
          "analysis_result": {
            "analysis_id": "analysis_20250827_143052_abc12345",
            "status": "completed"
          },
          "report_format": "json",
          "generated_at": "2025-08-27T14:30:52Z"
        }
      ],
      "total_count": 1,
      "page": 1,
      "page_size": 20,
      "total_pages": 1,
      "timestamp": "2025-08-27T19:00:00Z"
    }
    ```
    
    ## Curl Example
    
    ```bash
    curl -X GET "http://localhost:8000/api/v1/reports/?page=1&page_size=20"
    ```
    """
    try:
        # Get all analyses
        analyses, total_count = await sync_analyzer_service.list_analyses(page, page_size)
        
        # Convert to reports
        reports = []
        for analysis in analyses:
            if analysis.status.value == "completed":
                report = AnalysisReport(
                    report_id=f"report_{analysis.analysis_id}",
                    analysis_result=analysis,
                    report_format="json",
                    generated_at=analysis.completed_at or analysis.created_at
                )
                reports.append(report)
        
        # Calculate pagination
        total_pages = (len(reports) + page_size - 1) // page_size
        
        return ReportListResponse(
            reports=reports,
            total_count=len(reports),
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            message=f"Retrieved {len(reports)} reports"
        )
        
    except Exception as e:
        logger.error(f"Error listing reports: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{analysis_id}/formatted", response_model=FormattedReportResponse)
async def get_formatted_report(
    analysis_id: str = FastAPIPath(..., description="Analysis identifier"),
    episode_name: Optional[str] = Query(None, description="Episode name for report header")
):
    """
    Get a professionally formatted report for an analysis.
    
    Returns both HTML and Markdown formatted versions of the analysis report
    with phase analysis, drift detection, and recommendations.
    """
    try:
        # Get analysis result first
        analysis_result = await sync_analyzer_service.get_analysis_result(analysis_id)
        
        if not analysis_result:
            raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")
        
        # Check if we have timeline data available
        if not hasattr(analysis_result, 'timeline') or not analysis_result.timeline:
            raise HTTPException(
                status_code=400, 
                detail="No timeline data available for formatting. Analysis may not be a continuous sync analysis."
            )
        
        # Create temporary JSON file for the formatter
        temp_json_path = Path(f"/tmp/{analysis_id}_temp.json")
        
        # Convert analysis result to JSON format expected by formatter
        temp_data = {
            "analysis_id": analysis_result.analysis_id,
            "timeline": analysis_result.timeline,
            "master_duration": getattr(analysis_result, 'master_duration', 0),
            "drift_analysis": getattr(analysis_result, 'drift_analysis', {}),
            "consensus_offset": {
                "offset_seconds": analysis_result.consensus_offset.offset_seconds if analysis_result.consensus_offset else 0,
                "confidence": analysis_result.consensus_offset.confidence if analysis_result.consensus_offset else 0
            }
        }
        
        with open(temp_json_path, 'w') as f:
            json.dump(temp_data, f, indent=2)
        
        # Generate formatted report using our sync_report_analyzer
        cmd = [
            'python', '../sync_report_analyzer.py',
            str(temp_json_path),
            '--name', episode_name or f"Analysis {analysis_id}"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Clean up temp file
        temp_json_path.unlink(missing_ok=True)
        
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Report generation failed: {result.stderr}")
        
        markdown_report = result.stdout
        
        # Convert markdown to HTML (simple conversion)
        html_report = markdown_to_html(markdown_report)
        
        return FormattedReportResponse(
            success=True,
            report_html=html_report,
            report_markdown=markdown_report,
            analysis_id=analysis_id,
            episode_name=episode_name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating formatted report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/batch/csv", response_model=BatchUploadResponse)
async def upload_batch_csv(
    file: UploadFile = File(..., description="CSV file with batch processing instructions"),
    output_dir: str = Query("batch_results", description="Output directory for batch results")
):
    """
    Upload CSV file for batch processing of sync analyses.
    
    Expected CSV format:
    - master_file: Path to master/reference video
    - dub_file: Path to dub/test video  
    - episode_name: Display name for the episode
    - chunk_size (optional): Analysis chunk size
    """
    try:
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="File must be a CSV")
        
        # Save uploaded CSV
        import uuid
        batch_id = str(uuid.uuid4())[:8]
        csv_path = Path(f"/tmp/batch_{batch_id}.csv")
        
        content = await file.read()
        with open(csv_path, 'wb') as f:
            f.write(content)
        
        # Parse CSV and validate
        import csv
        episodes = []
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            required_cols = ['master_file', 'dub_file', 'episode_name']
            
            if not all(col in reader.fieldnames for col in required_cols):
                raise HTTPException(
                    status_code=400, 
                    detail=f"CSV must contain columns: {required_cols}"
                )
            
            for row in reader:
                episodes.append(dict(row))
        
        if not episodes:
            raise HTTPException(status_code=400, detail="CSV contains no valid rows")
        
        # Store batch info for later processing
        batch_info = {
            "batch_id": batch_id,
            "csv_path": str(csv_path),
            "output_dir": output_dir,
            "episodes": episodes,
            "status": "uploaded"
        }
        
        # Save batch info (in production, use database)
        batch_info_path = Path(f"/tmp/batch_{batch_id}_info.json")
        with open(batch_info_path, 'w') as f:
            json.dump(batch_info, f, indent=2)
        
        return BatchUploadResponse(
            success=True,
            message=f"CSV uploaded successfully. Use batch ID {batch_id} to start processing.",
            batch_id=batch_id,
            episodes_count=len(episodes),
            csv_preview=episodes[:5]  # Show first 5 rows
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading CSV: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/batch/{batch_id}/process")
async def start_batch_processing(
    batch_id: str = FastAPIPath(..., description="Batch ID from CSV upload"),
    max_workers: Optional[int] = Query(None, description="Max parallel workers"),
    generate_plots: bool = Query(True, description="Generate sync visualization plots")
):
    """
    Start batch processing for uploaded CSV.
    
    This will launch the csv_batch_processor with the uploaded CSV file.
    """
    try:
        # Load batch info
        batch_info_path = Path(f"/tmp/batch_{batch_id}_info.json")
        if not batch_info_path.exists():
            raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")
        
        with open(batch_info_path) as f:
            batch_info = json.load(f)
        
        if batch_info.get("status") == "processing":
            raise HTTPException(status_code=409, detail="Batch is already being processed")
        
        # Update status
        batch_info["status"] = "processing"
        with open(batch_info_path, 'w') as f:
            json.dump(batch_info, f, indent=2)
        
        # Build command
        cmd = [
            'python', '../csv_batch_processor.py',
            batch_info["csv_path"],
            '--output-dir', batch_info["output_dir"]
        ]
        
        if max_workers:
            cmd.extend(['--max-workers', str(max_workers)])
        
        if generate_plots:
            cmd.append('--plot')
        
        # Start processing in background
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Store process info
        batch_info["process_id"] = process.pid
        batch_info["status"] = "processing"
        with open(batch_info_path, 'w') as f:
            json.dump(batch_info, f, indent=2)
        
        return {
            "success": True,
            "message": f"Batch processing started for {len(batch_info['episodes'])} episodes",
            "batch_id": batch_id,
            "process_id": process.pid,
            "output_dir": batch_info["output_dir"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting batch processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/batch/{batch_id}/status")
async def get_batch_status(
    batch_id: str = FastAPIPath(..., description="Batch ID")
):
    """Get status of batch processing."""
    try:
        batch_info_path = Path(f"/tmp/batch_{batch_id}_info.json")
        if not batch_info_path.exists():
            raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")
        
        with open(batch_info_path) as f:
            batch_info = json.load(f)
        
        # Check if results are available
        output_dir = Path(batch_info["output_dir"])
        summary_file = output_dir / "batch_processing_summary.json"
        
        if summary_file.exists():
            with open(summary_file) as f:
                summary_data = json.load(f)
            
            batch_info["status"] = "completed"
            batch_info["results"] = summary_data
        
        return {"success": True, "batch_info": batch_info}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting batch status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def markdown_to_html(markdown: str) -> str:
    """Simple markdown to HTML conversion."""
    html = markdown
    
    # Headers
    html = html.replace('# ', '<h1>').replace('\n## ', '</h1>\n<h2>').replace('\n### ', '</h2>\n<h3>')
    
    # Bold text
    import re
    html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
    
    # Lists
    lines = html.split('\n')
    in_list = False
    result_lines = []
    
    for line in lines:
        if line.strip().startswith('- '):
            if not in_list:
                result_lines.append('<ul>')
                in_list = True
            result_lines.append(f'<li>{line.strip()[2:]}</li>')
        else:
            if in_list:
                result_lines.append('</ul>')
                in_list = False
            result_lines.append(line)
    
    if in_list:
        result_lines.append('</ul>')
    
    # Paragraphs
    html = '\n'.join(result_lines)
    html = html.replace('\n\n', '</p>\n<p>')
    html = f'<p>{html}</p>'
    
    # Clean up
    html = html.replace('<p></p>', '')
    html = html.replace('<p><h', '<h')
    html = html.replace('</h1></p>', '</h1>')
    html = html.replace('</h2></p>', '</h2>')
    html = html.replace('</h3></p>', '</h3>')
    html = html.replace('<p><ul>', '<ul>')
    html = html.replace('</ul></p>', '</ul>')
    
    return html
