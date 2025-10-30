#!/usr/bin/env python3
"""
Professional Audio Sync Analyzer API
====================================

Flask-based REST API for the Professional Master-Dub Audio Sync Analyzer.
Provides HTTP endpoints for sync detection, file uploads, and analysis results.

Author: AI Audio Engineer
Version: 1.0.0
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import tempfile
import shutil

from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS
from werkzeug.utils import secure_filename
import numpy as np

# Import our sync detection modules
try:
    from ..core.audio_sync_detector import ProfessionalSyncDetector
    from ..ai.embedding_sync_detector import AISyncDetector, EmbeddingConfig
    from ..reports.sync_reporter import ProfessionalSyncReporter
except ImportError:
    # Fallback for direct execution
    import sys
    sys.path.append(str(Path(__file__).parent.parent))
    from core.audio_sync_detector import ProfessionalSyncDetector
    from ai.embedding_sync_detector import AISyncDetector, EmbeddingConfig
    from reports.sync_reporter import ProfessionalSyncReporter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app configuration
app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = Path('./uploads')
TEMP_FOLDER = Path('./temp')
REPORTS_FOLDER = Path('./sync_reports')
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'flac', 'm4a', 'aac', 'ogg', 'mov', 'mp4', 'avi'}

# Ensure directories exist
UPLOAD_FOLDER.mkdir(exist_ok=True)
TEMP_FOLDER.mkdir(exist_ok=True)
REPORTS_FOLDER.mkdir(exist_ok=True)

# Global sync detector instances
sync_detector = None
ai_detector = None

def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def initialize_detectors():
    """Initialize sync detection systems."""
    global sync_detector, ai_detector
    
    try:
        # Initialize traditional sync detector
        sync_detector = ProfessionalSyncDetector(
            sample_rate=22050,
            window_size_seconds=30.0,
            confidence_threshold=0.7
        )
        logger.info("✅ Traditional sync detector initialized")
        
        # Initialize AI-based detector
        ai_config = EmbeddingConfig(
            model_name="wav2vec2",
            use_gpu=torch.cuda.is_available()
        )
        ai_detector = AISyncDetector(ai_config)
        logger.info("✅ AI sync detector initialized")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize detectors: {e}")
        # Continue with basic functionality

def extract_audio_features(audio_path: Path) -> Dict[str, Any]:
    """Extract basic audio features for analysis."""
    try:
        import librosa
        
        # Load audio
        y, sr = librosa.load(str(audio_path), sr=None)
        
        # Basic features
        duration = len(y) / sr
        rms = np.sqrt(np.mean(y**2))
        
        return {
            "duration": duration,
            "sample_rate": sr,
            "channels": 1 if len(y.shape) == 1 else y.shape[1],
            "rms_energy": float(rms),
            "file_size": audio_path.stat().st_size
        }
    except Exception as e:
        logger.error(f"Failed to extract audio features: {e}")
        return {"error": str(e)}

@app.route('/')
def index():
    """API home page with documentation."""
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Professional Audio Sync Analyzer API</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .endpoint { background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; }
            .method { font-weight: bold; color: #0066cc; }
            .url { font-family: monospace; background: #e0e0e0; padding: 2px 6px; }
        </style>
    </head>
    <body>
        <h1>🎵 Professional Audio Sync Analyzer API</h1>
        <p>REST API for master-dub audio synchronization analysis</p>
        
        <h2>📋 Available Endpoints</h2>
        
        <div class="endpoint">
            <div class="method">POST</div>
            <div class="url">/api/sync/analyze</div>
            <p>Analyze sync between master and dub audio files</p>
        </div>
        
        <div class="endpoint">
            <div class="method">POST</div>
            <div class="url">/api/sync/upload</div>
            <p>Upload audio files for analysis</p>
        </div>
        
        <div class="endpoint">
            <div class="method">GET</div>
            <div class="url">/api/sync/status</div>
            <p>Get API status and system information</p>
        </div>
        
        <div class="endpoint">
            <div class="method">GET</div>
            <div class="url">/api/sync/reports</div>
            <p>List available sync analysis reports</p>
        </div>
        
        <div class="endpoint">
            <div class="method">GET</div>
            <div class="url">/api/sync/report/<id></div>
            <p>Get specific sync analysis report</p>
        </div>
        
        <h2>🔧 System Status</h2>
        <p>Traditional Sync Detector: {{ '✅ Ready' if sync_detector else '❌ Not Available' }}</p>
        <p>AI Sync Detector: {{ '✅ Ready' if ai_detector else '❌ Not Available' }}</p>
        <p>GPU Available: {{ '✅ Yes' if torch.cuda.is_available() else '❌ No' }}</p>
    </body>
    </html>
    """, sync_detector=sync_detector, ai_detector=ai_detector, torch=torch)

@app.route('/api/sync/status', methods=['GET'])
def get_status():
    """Get API status and system information."""
    try:
        import torch
        
        status = {
            "status": "operational",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "detectors": {
                "traditional": sync_detector is not None,
                "ai": ai_detector is not None
            },
            "gpu": {
                "available": torch.cuda.is_available(),
                "device": str(torch.cuda.get_device_name(0)) if torch.cuda.is_available() else None
            },
            "storage": {
                "uploads": str(UPLOAD_FOLDER.absolute()),
                "temp": str(TEMP_FOLDER.absolute()),
                "reports": str(REPORTS_FOLDER.absolute())
            }
        }
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/sync/upload', methods=['POST'])
def upload_files():
    """Upload master and dub audio files."""
    try:
        if 'master' not in request.files or 'dub' not in request.files:
            return jsonify({"error": "Both master and dub files are required"}), 400
        
        master_file = request.files['master']
        dub_file = request.files['dub']
        
        if master_file.filename == '' or dub_file.filename == '':
            return jsonify({"error": "No files selected"}), 400
        
        if not (allowed_file(master_file.filename) and allowed_file(dub_file.filename)):
            return jsonify({"error": "Invalid file type"}), 400
        
        # Create unique session ID
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        session_dir = UPLOAD_FOLDER / session_id
        session_dir.mkdir(exist_ok=True)
        
        # Save files
        master_path = session_dir / secure_filename(master_file.filename)
        dub_path = session_dir / secure_filename(dub_file.filename)
        
        master_file.save(master_path)
        dub_file.save(dub_path)
        
        # Extract basic info
        master_info = extract_audio_features(master_path)
        dub_info = extract_audio_features(dub_path)
        
        response = {
            "session_id": session_id,
            "files": {
                "master": {
                    "filename": master_file.filename,
                    "path": str(master_path),
                    "info": master_info
                },
                "dub": {
                    "filename": dub_file.filename,
                    "path": str(dub_path),
                    "info": dub_info
                }
            },
            "message": "Files uploaded successfully"
        }
        
        logger.info(f"Files uploaded for session {session_id}")
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/sync/analyze', methods=['POST'])
def analyze_sync():
    """Analyze sync between master and dub audio files."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        # Get file paths
        master_path = Path(data.get('master_path', ''))
        dub_path = Path(data.get('dub_path', ''))
        
        if not master_path.exists() or not dub_path.exists():
            return jsonify({"error": "One or both audio files not found"}), 400
        
        # Analysis options
        methods = data.get('methods', ['all'])
        enable_ai = data.get('enable_ai', True)
        sample_rate = data.get('sample_rate', 22050)
        window_size = data.get('window_size', 30.0)
        confidence_threshold = data.get('confidence_threshold', 0.7)
        
        results = {}
        
        # Traditional sync detection
        if sync_detector and ('traditional' in methods or 'all' in methods):
            try:
                logger.info("Running traditional sync detection...")
                sync_result = sync_detector.detect_sync(master_path, dub_path)
                
                results['traditional'] = {
                    "offset_samples": sync_result.offset_samples,
                    "offset_seconds": sync_result.offset_seconds,
                    "confidence": sync_result.confidence,
                    "method_used": sync_result.method_used,
                    "correlation_peak": sync_result.correlation_peak,
                    "quality_score": sync_result.quality_score
                }
                
            except Exception as e:
                logger.error(f"Traditional detection failed: {e}")
                results['traditional'] = {"error": str(e)}
        
        # AI-based sync detection
        if ai_detector and enable_ai and ('ai' in methods or 'all' in methods):
            try:
                logger.info("Running AI-based sync detection...")
                ai_result = ai_detector.detect_sync(master_path, dub_path)
                
                results['ai'] = {
                    "offset_samples": ai_result.offset_samples,
                    "offset_seconds": ai_result.offset_seconds,
                    "confidence": ai_result.confidence,
                    "embedding_similarity": ai_result.embedding_similarity,
                    "temporal_consistency": ai_result.temporal_consistency,
                    "method_details": ai_result.method_details
                }
                
            except Exception as e:
                logger.error(f"AI detection failed: {e}")
                results['ai'] = {"error": str(e)}
        
        # Generate report
        if results:
            try:
                reporter = ProfessionalSyncReporter()
                report = reporter.generate_report(
                    master_path=master_path,
                    dub_path=dub_path,
                    results=results,
                    output_dir=REPORTS_FOLDER
                )
                
                results['report'] = {
                    "report_id": report.get('report_id'),
                    "report_path": str(report.get('report_path')),
                    "generated_at": datetime.now().isoformat()
                }
                
            except Exception as e:
                logger.error(f"Report generation failed: {e}")
                results['report'] = {"error": str(e)}
        
        return jsonify({
            "analysis_id": datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3],
            "timestamp": datetime.now().isoformat(),
            "files": {
                "master": str(master_path),
                "dub": str(dub_path)
            },
            "results": results
        })
        
    except Exception as e:
        logger.error(f"Sync analysis failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/sync/reports', methods=['GET'])
def list_reports():
    """List available sync analysis reports."""
    try:
        reports = []
        
        for report_file in REPORTS_FOLDER.glob("*.json"):
            try:
                with open(report_file, 'r') as f:
                    report_data = json.load(f)
                
                reports.append({
                    "filename": report_file.name,
                    "path": str(report_file),
                    "size": report_file.stat().st_size,
                    "modified": datetime.fromtimestamp(report_file.stat().st_mtime).isoformat(),
                    "data": report_data
                })
                
            except Exception as e:
                logger.warning(f"Failed to read report {report_file}: {e}")
        
        return jsonify({
            "reports": reports,
            "count": len(reports),
            "directory": str(REPORTS_FOLDER.absolute())
        })
        
    except Exception as e:
        logger.error(f"Failed to list reports: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/sync/report/<report_id>', methods=['GET'])
def get_report(report_id: str):
    """Get specific sync analysis report."""
    try:
        # Look for report by ID or filename
        report_path = None
        
        for report_file in REPORTS_FOLDER.glob("*.json"):
            if report_id in report_file.name:
                report_path = report_file
                break
        
        if not report_path or not report_path.exists():
            return jsonify({"error": "Report not found"}), 404
        
        with open(report_path, 'r') as f:
            report_data = json.load(f)
        
        return jsonify({
            "report_id": report_id,
            "filename": report_path.name,
            "path": str(report_path),
            "data": report_data
        })
        
    except Exception as e:
        logger.error(f"Failed to get report {report_id}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/sync/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })

if __name__ == '__main__':
    # Initialize detectors
    initialize_detectors()
    
    # Run the API
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    logger.info(f"🚀 Starting Professional Audio Sync Analyzer API on port {port}")
    logger.info(f"📁 Upload folder: {UPLOAD_FOLDER.absolute()}")
    logger.info(f"📁 Reports folder: {REPORTS_FOLDER.absolute()}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
