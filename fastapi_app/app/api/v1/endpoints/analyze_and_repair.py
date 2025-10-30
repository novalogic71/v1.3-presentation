#!/usr/bin/env python3
"""
Complete Analyze-and-Repair Workflow Endpoint

Provides a comprehensive API endpoint that performs analysis, repair, and packaging
in a single operation for streamlined sync correction workflows.
"""

import os
import json
import logging
import tempfile
import asyncio
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class AnalyzeAndRepairRequest(BaseModel):
    """Request model for complete analyze-and-repair workflow"""
    master_file: str = Field(..., description="Path to master/reference file")
    dub_file: str = Field(..., description="Path to dub file to be analyzed and repaired")
    episode_name: str = Field(default="Episode", description="Name for the episode/content")
    
    # Analysis options
    chunk_size: float = Field(default=30.0, description="Chunk size in seconds for analysis")
    enable_gpu: bool = Field(default=True, description="Enable GPU acceleration")
    
    # Repair options
    auto_repair: bool = Field(default=True, description="Automatically apply repair if needed")
    repair_threshold: float = Field(default=100.0, description="Offset threshold in ms for repair")
    repair_output_path: Optional[str] = Field(None, description="Custom path for repaired file")
    
    # Package options
    create_package: bool = Field(default=True, description="Create comprehensive repair package")
    include_visualization: bool = Field(default=True, description="Include sync visualization in package")
    create_zip: bool = Field(default=True, description="Create ZIP archive of package")
    
    # Output options
    output_directory: str = Field(default="./repair_workflows", description="Base output directory")


class AnalyzeAndRepairResponse(BaseModel):
    """Response model for analyze-and-repair workflow"""
    success: bool
    workflow_id: str
    status: str  # 'processing', 'completed', 'failed'
    
    # Analysis results
    analysis_completed: bool = False
    sync_status: Optional[str] = None
    offset_ms: Optional[float] = None
    confidence: Optional[float] = None
    
    # Repair results
    repair_needed: bool = False
    repair_applied: bool = False
    repair_type: Optional[str] = None
    repaired_file_path: Optional[str] = None
    
    # Package results
    package_created: bool = False
    package_directory: Optional[str] = None
    package_zip_file: Optional[str] = None
    
    # File paths
    analysis_file: Optional[str] = None
    repair_report: Optional[str] = None
    visualization_file: Optional[str] = None
    
    # Progress info
    processing_time: Optional[float] = None
    current_step: Optional[str] = None
    error_message: Optional[str] = None


# In-memory storage for workflow status (in production, use Redis or database)
workflow_status: Dict[str, Dict[str, Any]] = {}


def _is_safe_path(path: str) -> bool:
    """Check if path is safe and within allowed directory"""
    try:
        return str(Path(path).resolve()).startswith(str(Path(settings.MOUNT_PATH).resolve()))
    except Exception:
        return False


def _generate_workflow_id() -> str:
    """Generate unique workflow ID"""
    import uuid
    return f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


async def _run_analysis(request: AnalyzeAndRepairRequest, workflow_id: str) -> Dict[str, Any]:
    """
    Run sync analysis using the optimized large file detector
    """
    logger.info(f"Starting analysis for workflow {workflow_id}")
    
    # Update status
    workflow_status[workflow_id].update({
        'current_step': 'analysis',
        'status': 'processing'
    })
    
    try:
        # Import analysis components
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))
        from sync_analyzer.core.optimized_large_file_detector import OptimizedLargeFileDetector
        
        # Initialize detector
        detector = OptimizedLargeFileDetector(
            gpu_enabled=request.enable_gpu,
            chunk_size=request.chunk_size,
            max_chunks=50  # Allow more chunks for comprehensive analysis
        )
        
        # Run analysis
        analysis_result = detector.analyze_sync_chunked(request.master_file, request.dub_file)
        
        if 'error' in analysis_result:
            raise Exception(f"Analysis failed: {analysis_result['error']}")
        
        # Save analysis results
        output_dir = Path(request.output_directory) / workflow_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        analysis_file = output_dir / "analysis_results.json"
        with open(analysis_file, 'w') as f:
            json.dump(analysis_result, f, indent=2, default=str)
        
        # Update workflow status
        workflow_status[workflow_id].update({
            'analysis_completed': True,
            'sync_status': analysis_result.get('sync_status'),
            'offset_ms': analysis_result.get('offset_seconds', 0) * 1000,
            'confidence': analysis_result.get('confidence', 0),
            'analysis_file': str(analysis_file),
            'current_step': 'analysis_complete'
        })
        
        logger.info(f"Analysis completed for workflow {workflow_id}")
        return analysis_result
        
    except Exception as e:
        logger.error(f"Analysis failed for workflow {workflow_id}: {e}")
        workflow_status[workflow_id].update({
            'status': 'failed',
            'error_message': str(e),
            'current_step': 'analysis_failed'
        })
        raise


async def _run_repair(analysis_result: Dict[str, Any], request: AnalyzeAndRepairRequest, workflow_id: str) -> Optional[str]:
    """
    Run intelligent repair if needed
    """
    logger.info(f"Evaluating repair need for workflow {workflow_id}")
    
    offset_ms = abs(analysis_result.get('offset_seconds', 0) * 1000)
    
    if not request.auto_repair or offset_ms < request.repair_threshold:
        logger.info(f"No repair needed for workflow {workflow_id} (offset: {offset_ms:.1f}ms < threshold: {request.repair_threshold}ms)")
        workflow_status[workflow_id].update({
            'repair_needed': False,
            'current_step': 'repair_skipped'
        })
        return None
    
    # Update status
    workflow_status[workflow_id].update({
        'repair_needed': True,
        'current_step': 'repair',
        'status': 'processing'
    })
    
    try:
        # Import repair components
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))
        from scripts.repair.intelligent_sync_repair import IntelligentSyncRepairer
        
        # Determine repair output path
        if request.repair_output_path:
            repair_output = request.repair_output_path
        else:
            dub_path = Path(request.dub_file)
            output_dir = Path(request.output_directory) / workflow_id
            repair_output = str(output_dir / f"{dub_path.stem}_repaired{dub_path.suffix}")
        
        # Save analysis to temporary file for repairer
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(analysis_result, f, indent=2, default=str)
            temp_analysis_file = f.name
        
        try:
            # Initialize repairer and perform repair
            repairer = IntelligentSyncRepairer()
            repair_result = repairer.repair_file(request.dub_file, temp_analysis_file, repair_output)
            
            if repair_result["success"]:
                # Update workflow status
                workflow_status[workflow_id].update({
                    'repair_applied': True,
                    'repair_type': repair_result['repair_type'],
                    'repaired_file_path': repair_output,
                    'current_step': 'repair_complete'
                })
                
                logger.info(f"Repair completed for workflow {workflow_id}: {repair_result['repair_type']}")
                return repair_output
            else:
                raise Exception(f"Repair failed: {repair_result.get('error', 'Unknown error')}")
                
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_analysis_file)
            except:
                pass
                
    except Exception as e:
        logger.error(f"Repair failed for workflow {workflow_id}: {e}")
        workflow_status[workflow_id].update({
            'status': 'failed',
            'error_message': str(e),
            'current_step': 'repair_failed'
        })
        raise


async def _create_package(analysis_result: Dict[str, Any], request: AnalyzeAndRepairRequest, 
                         workflow_id: str, repaired_file: Optional[str]) -> Optional[Dict[str, str]]:
    """
    Create comprehensive repair package
    """
    if not request.create_package:
        workflow_status[workflow_id].update({
            'current_step': 'package_skipped'
        })
        return None
    
    logger.info(f"Creating package for workflow {workflow_id}")
    
    # Update status
    workflow_status[workflow_id].update({
        'current_step': 'packaging',
        'status': 'processing'
    })
    
    try:
        # Import packager
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))
        from sync_repair_packager import SyncRepairPackager
        
        # Create packager
        output_dir = Path(request.output_directory)
        packager = SyncRepairPackager(str(output_dir))
        
        # Generate package
        package_result = packager.create_repair_package(
            original_file=request.dub_file,
            analysis_data=analysis_result,
            repaired_file=repaired_file,
            episode_name=request.episode_name,
            include_visualization=request.include_visualization,
            create_zip=request.create_zip
        )
        
        if package_result["success"]:
            # Update workflow status
            package_info = {
                'package_directory': package_result['package_directory'],
            }
            
            if 'zip_file' in package_result:
                package_info['package_zip_file'] = package_result['zip_file']
            
            # Extract specific file paths
            files = package_result.get('files', {})
            if 'repair_report' in files:
                package_info['repair_report'] = files['repair_report']
            if 'visualization' in files:
                package_info['visualization_file'] = files['visualization']
            
            workflow_status[workflow_id].update({
                'package_created': True,
                'current_step': 'package_complete',
                **package_info
            })
            
            logger.info(f"Package created for workflow {workflow_id}: {package_result['package_name']}")
            return package_info
        else:
            raise Exception(f"Package creation failed: {package_result.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"Package creation failed for workflow {workflow_id}: {e}")
        workflow_status[workflow_id].update({
            'status': 'failed',
            'error_message': str(e),
            'current_step': 'package_failed'
        })
        raise


async def _run_complete_workflow(request: AnalyzeAndRepairRequest, workflow_id: str):
    """
    Run the complete analyze-and-repair workflow
    """
    start_time = datetime.now()
    
    try:
        # Step 1: Analysis
        analysis_result = await _run_analysis(request, workflow_id)
        
        # Step 2: Repair (if needed)
        repaired_file = await _run_repair(analysis_result, request, workflow_id)
        
        # Step 3: Package (if requested)
        package_info = await _create_package(analysis_result, request, workflow_id, repaired_file)
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Final status update
        workflow_status[workflow_id].update({
            'status': 'completed',
            'current_step': 'completed',
            'processing_time': processing_time
        })
        
        logger.info(f"Workflow {workflow_id} completed successfully in {processing_time:.2f} seconds")
        
    except Exception as e:
        processing_time = (datetime.now() - start_time).total_seconds()
        workflow_status[workflow_id].update({
            'status': 'failed',
            'processing_time': processing_time,
            'error_message': str(e)
        })
        logger.error(f"Workflow {workflow_id} failed: {e}")


@router.post("/analyze-and-repair", response_model=AnalyzeAndRepairResponse, status_code=202)
async def start_analyze_and_repair_workflow(
    request: AnalyzeAndRepairRequest,
    background_tasks: BackgroundTasks
):
    """
    Start a complete analyze-and-repair workflow.
    
    This endpoint performs the full sync correction workflow:
    1. Analyzes sync using the optimized large file detector (always long method)
    2. Applies intelligent repair if offset exceeds threshold
    3. Creates comprehensive package with reports and visualizations
    
    The workflow runs asynchronously in the background. Use the workflow_id
    to check status and retrieve results.
    
    ## Workflow Steps
    
    1. **Analysis**: Uses OptimizedLargeFileDetector with chunked processing
    2. **Repair**: Applies IntelligentSyncRepairer if offset > threshold
    3. **Packaging**: Creates comprehensive package with all outputs
    
    ## Example Request
    
    ```json
    {
        "master_file": "/mnt/data/master.mov",
        "dub_file": "/mnt/data/dub.mov",
        "episode_name": "Episode 101",
        "auto_repair": true,
        "repair_threshold": 100.0,
        "create_package": true
    }
    ```
    """
    try:
        # Validate file paths
        if not _is_safe_path(request.master_file) or not os.path.exists(request.master_file):
            raise HTTPException(status_code=400, detail="Invalid or missing master file path")
        
        if not _is_safe_path(request.dub_file) or not os.path.exists(request.dub_file):
            raise HTTPException(status_code=400, detail="Invalid or missing dub file path")
        
        # Generate workflow ID
        workflow_id = _generate_workflow_id()
        
        # Initialize workflow status
        workflow_status[workflow_id] = {
            'workflow_id': workflow_id,
            'status': 'processing',
            'current_step': 'initialized',
            'analysis_completed': False,
            'repair_needed': False,
            'repair_applied': False,
            'package_created': False,
            'created_at': datetime.now().isoformat(),
            'request_params': request.dict()
        }
        
        # Start background processing
        background_tasks.add_task(_run_complete_workflow, request, workflow_id)
        
        # Return immediate response
        return AnalyzeAndRepairResponse(
            success=True,
            workflow_id=workflow_id,
            status='processing',
            current_step='initialized'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start analyze-and-repair workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analyze-and-repair/{workflow_id}/status", response_model=AnalyzeAndRepairResponse)
async def get_workflow_status(workflow_id: str):
    """
    Get the status of a running or completed workflow.
    
    Returns detailed information about the workflow progress, including:
    - Current processing step
    - Analysis results (if completed)
    - Repair status and results
    - Package creation status
    - File paths for generated outputs
    
    ## Status Values
    
    - `processing`: Workflow is currently running
    - `completed`: Workflow finished successfully
    - `failed`: Workflow encountered an error
    
    ## Steps
    
    - `initialized`: Workflow started
    - `analysis`: Running sync analysis
    - `analysis_complete`: Analysis finished
    - `repair`: Applying sync repair
    - `repair_complete`: Repair finished
    - `repair_skipped`: No repair needed
    - `packaging`: Creating output package
    - `package_complete`: Package created
    - `completed`: All steps finished
    """
    if workflow_id not in workflow_status:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    status = workflow_status[workflow_id]
    
    return AnalyzeAndRepairResponse(
        success=status['status'] != 'failed',
        workflow_id=workflow_id,
        status=status['status'],
        current_step=status.get('current_step'),
        
        # Analysis results
        analysis_completed=status.get('analysis_completed', False),
        sync_status=status.get('sync_status'),
        offset_ms=status.get('offset_ms'),
        confidence=status.get('confidence'),
        
        # Repair results
        repair_needed=status.get('repair_needed', False),
        repair_applied=status.get('repair_applied', False),
        repair_type=status.get('repair_type'),
        repaired_file_path=status.get('repaired_file_path'),
        
        # Package results
        package_created=status.get('package_created', False),
        package_directory=status.get('package_directory'),
        package_zip_file=status.get('package_zip_file'),
        
        # File paths
        analysis_file=status.get('analysis_file'),
        repair_report=status.get('repair_report'),
        visualization_file=status.get('visualization_file'),
        
        # Progress info
        processing_time=status.get('processing_time'),
        error_message=status.get('error_message')
    )


@router.get("/analyze-and-repair/{workflow_id}/download/{file_type}")
async def download_workflow_file(workflow_id: str, file_type: str):
    """
    Download files generated by the workflow.
    
    ## Available File Types
    
    - `analysis`: JSON analysis results
    - `repaired`: Repaired audio/video file
    - `report`: Markdown repair report
    - `visualization`: Sync visualization PNG
    - `package`: ZIP package containing all outputs
    
    ## Example Usage
    
    ```
    GET /api/v1/analyze-and-repair/workflow_123/download/package
    GET /api/v1/analyze-and-repair/workflow_123/download/repaired
    ```
    """
    if workflow_id not in workflow_status:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    status = workflow_status[workflow_id]
    
    # Map file types to status keys
    file_mapping = {
        'analysis': 'analysis_file',
        'repaired': 'repaired_file_path', 
        'report': 'repair_report',
        'visualization': 'visualization_file',
        'package': 'package_zip_file'
    }
    
    if file_type not in file_mapping:
        raise HTTPException(status_code=400, detail=f"Invalid file type. Available: {list(file_mapping.keys())}")
    
    file_path = status.get(file_mapping[file_type])
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"{file_type} file not found or not generated")
    
    # Determine media type
    media_types = {
        'analysis': 'application/json',
        'report': 'text/markdown',
        'visualization': 'image/png',
        'package': 'application/zip'
    }
    
    media_type = media_types.get(file_type, 'application/octet-stream')
    filename = Path(file_path).name
    
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename
    )


@router.delete("/analyze-and-repair/{workflow_id}")
async def cleanup_workflow(workflow_id: str):
    """
    Clean up workflow data and temporary files.
    
    This will:
    - Remove workflow from memory
    - Clean up temporary files (optional, use with caution)
    
    Note: This does not delete the output package directory or repaired files.
    """
    if workflow_id not in workflow_status:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Remove from memory
    del workflow_status[workflow_id]
    
    return JSONResponse({
        'success': True,
        'message': f'Workflow {workflow_id} cleaned up'
    })


@router.get("/analyze-and-repair/workflows")
async def list_workflows():
    """
    List all workflows and their current status.
    
    Returns a summary of all workflows in memory with basic status information.
    """
    workflows = []
    
    for workflow_id, status in workflow_status.items():
        workflows.append({
            'workflow_id': workflow_id,
            'status': status['status'],
            'current_step': status.get('current_step'),
            'created_at': status.get('created_at'),
            'episode_name': status.get('request_params', {}).get('episode_name', 'Unknown'),
            'processing_time': status.get('processing_time')
        })
    
    return JSONResponse({
        'success': True,
        'workflows': workflows,
        'total_count': len(workflows)
    })