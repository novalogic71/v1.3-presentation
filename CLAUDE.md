- add to memeory
- add to memory
- add this to memory
- add to memory
- add this to memory
- Add to memory
- add to memory

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