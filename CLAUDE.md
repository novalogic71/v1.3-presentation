- add to memeory
- add to memory
- add this to memory
- add to memory
- add this to memory
- Add to memory
- add to memory

# Recent Critical Fixes (January 2026)

## AI-Powered GPU Analysis (NEW)
- FEATURE: Wav2Vec2 GPU-accelerated sync detection
- IMPLEMENTATION: `sync_analyzer/core/simple_gpu_sync.py`
- PERFORMANCE: 10-50x faster than CPU methods
- FEATURES:
  - Full PyTorch GPU acceleration
  - Cross-correlation using FFT on GPU
  - Automatic bars/tone detection at file head
  - Smart hybrid mode with MFCC verification

## Cross-Browser Sync (NEW)
- FEATURE: Server-side batch queue storage in Redis
- ENDPOINT: `/api/v1/batch-queue` - GET/POST/PUT/DELETE
- BEHAVIOR: Jobs sync across all browser sessions in real-time
- FILES:
  - `fastapi_app/app/api/v1/endpoints/batch_queue.py`
  - `web_ui/app.js` - `loadBatchQueueFromServer()`, `syncFromServer()`

## API Job Discovery (NEW)
- FEATURE: Jobs submitted via API automatically appear in UI
- ENDPOINT: `/api/v1/job-registry` - Tracks all jobs
- POLLING: UI polls every 10 seconds for new API jobs
- FILES:
  - `fastapi_app/app/api/v1/endpoints/job_registry.py`
  - `fastapi_app/app/api/v1/endpoints/componentized.py` - Registers jobs
  - `web_ui/app.js` - `pollForNewApiJobs()`

## Smart Hybrid Analysis (NEW)
- FEATURE: GPU analysis with automatic MFCC verification
- TRIGGER: When GPU results across components are inconsistent (spread > 0.5s)
- REFINEMENT: Targeted MFCC on individual components for sub-frame accuracy
- FILE: `fastapi_app/app/services/componentized_service.py`

## Audio Fingerprinting (NEW)
- FEATURE: Chromaprint-based fingerprint sync detection
- FILE: `sync_analyzer/core/fingerprint_sync.py`
- DEPENDENCY: `pyacoustid`, `chromaprint` (fpcalc)
- NOTE: Not suitable for dubbed content (different languages)

## Analysis Findings Display (NEW)
- FEATURE: Detailed messaging for each component
- FINDINGS: Bars/tone detected, tail length, head offset differences
- UI: Finding tags with color coding (info, warning, error)
- FILE: `web_ui/app.js` - `getFindingTagClass()`

## UI Enhancements (NEW)
- Job dropdown styled to match Export button (green)
- Refresh button to manually sync job statuses
- Restart button for completed jobs
- Offset visualization in batch details
- Compact QC/Repair modals with text truncation

# Recent Critical Fixes (September 2025)

## Offset Calculation Fixes
- FIXED: Cross-correlation offset calculation in all methods (MFCC, Onset, Spectral, Chunked)
- FIXED: Sample rate mismatch between 48kHz original files and 22kHz resampled analysis
- ACCURACY: Improved from 7+ second errors to ~0.3 second accuracy
- FILES: optimized_large_file_detector.py:347, audio_sync_detector.py:265,335,408

## Multi-GPU Support Added
- FEATURE: Automatic workload distribution across all available GPUs
- PERFORMANCE: Round-robin GPU assignment prevents memory exhaustion
- BATCH FIX: Resolved 90% hang issue in batch processing
- IMPLEMENTATION: Process ID-based GPU selection in all components

# Critical Fixes (October 2025) - v1.2

## Frame Rate Detection & Display System
- FIXED: ffprobe endpoint returning 500 errors due to missing binary PATH resolution
- FIXED: FastAPI route ordering - /probe endpoint was being caught by /{file_id} catch-all
- ACCURACY: Frame rate now detected via ffprobe (23.976 fps instead of hardcoded 24 fps)
- SCOPE: Frame rate detection implemented across ALL interfaces (batch, QC, repair)
- FILES MODIFIED:
  * fastapi_app/app/api/v1/endpoints/files.py - Backend ffprobe fixes
  * web_ui/app.js - Batch mode frame rate detection per item
  * web_ui/qc-interface.js - QC interface frame rate display
  * web_ui/repair-preview-interface.js - Repair preview frame rate display

## Frame Rate Implementation Details
- BATCH MODE: Detects frame rate individually for each batch item before processing
- STORAGE: Frame rate stored with each batch item (item.frameRate)
- DISPLAY: All offset displays show accurate frame counts (e.g., "-240f @ 23.976fps")
- INTERFACES: Frame rate passed to QC and Repair interfaces via syncData object
- LOCATIONS UPDATED:
  * Batch table results column
  * Batch completion logs
  * Batch details panel (main offset + per-channel results)
  * Action recommendations panel
  * QC interface header, waveform overlays, timeline tooltips
  * Repair preview overall and per-segment displays

## Important Technical Notes
- AUDIO ANALYSIS: Works in time domain (seconds) - frame rate NOT needed for analysis
- FRAME CONVERSION: Frame rate only used for converting seconds to video frames for display
- BACKEND: Detects offset in seconds (universal unit)
- FRONTEND: Converts seconds to frames using detected video frame rate
- BRANCH: All fixes committed to v1.2 branch (commit a9026fa)

# Critical Fixes (December 2025) - v1.3

## Raw Analysis Data Display Fix
- FIXED: Raw Analysis Data section in batch details was empty in Docker container
- ISSUE: Flask server endpoint only returned simplified analysis results without method_results
- ROOT CAUSE: server.py discarded sync_results and ai_result from analyze() function
- SOLUTION: Modified server.py to capture and include all method results in API response

### Files Modified:
- **web_ui/server.py:393** - Changed `consensus, _, _ = analyze(...)` to capture all results
  - Now captures: `consensus, sync_results, ai_result = analyze(...)`
  - Builds `method_results` array with individual method results (MFCC, onset, spectral, correlation, AI)
  - Adds `consensus_offset` object to response

- **web_ui/operator-console.css** - Added JSON display styling
  - Dark theme styling for `.json-display` pre element
  - Monospace font, scrolling, proper padding

- **web_ui/styles/redesign.css** - Added force-display CSS rules
  - Ensures expanded sections display content with `!important` overrides
  - Added min-height to prevent content collapse

### Data Structure Returned:
```javascript
{
  "method_results": [
    {"method": "mfcc", "offset_seconds": -15.023, "confidence": 1.0, "quality_score": 0.54},
    {"method": "onset", "offset_seconds": -15.023, "confidence": 1.0, "quality_score": 1.0},
    {"method": "spectral", "offset_seconds": -15.023, "confidence": 1.0, "quality_score": 1.0},
    {"method": "correlation", "offset_seconds": -15.024, "confidence": 1.0, "quality_score": 1.0},
    {"method": "ai", "offset_seconds": -8.0, "confidence": 0.999, "quality_score": 0.0}
  ],
  "consensus_offset": {
    "offset_seconds": -15.023,
    "confidence": 1.0
  }
}
```

## Docker Image Creation
- CREATED: Production Docker image with GPU support
- IMAGE: v13-presentation-sync-analyzer:latest (ID: a17a5bb2c0ac)
- FEATURES:
  - Multi-GPU support (NVIDIA) with automatic workload distribution
  - FastAPI backend (port 8000) + Flask web UI (port 3002)
  - Persistent volumes for uploads, models, logs, reports, sync data
  - Health checks for both services
  - Auto-restart unless stopped

### Docker Compose Configuration:
- GPU Support: All NVIDIA GPUs enabled with full capabilities
- Volumes: 10 persistent volume mounts including raw analysis data
- Network: Bridge network for service communication
- Environment: GPU enabled, 48GB+ models cached