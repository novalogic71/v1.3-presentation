# CSV Batch: Analyze + Auto‑Repair + Package (v1.3)

This guide explains the enhanced CSV workflow that analyzes each pair,
optionally auto‑repairs when needed, and creates a complete repair package per
row — all from a single command. Now includes **SMPTE timecode support** and
**AI-enhanced LLM reporting** for professional broadcast workflows.

## Requirements
- ffmpeg/ffprobe available on PATH
- Python environment with project dependencies installed
- Input CSV with valid absolute paths
- **NEW**: Ollama LLM service running at localhost:11434 (for enhanced reports)
- **NEW**: SMPTE timecode utilities for professional broadcast analysis

## CSV Format
Required columns:
- master_file: absolute path to master/reference media
- dub_file: absolute path to dub/test media
- episode_name: user‑friendly label for the pair

Optional columns:
- chunk_size: per‑row analysis chunk size (seconds)

Example:
```csv
master_file,dub_file,episode_name,chunk_size
/mnt/data/master1.mov,/mnt/data/dub1.mov,RubbleAndCrew Episode 101,45
/mnt/data/master2.mov,/mnt/data/dub2.mov,RubbleAndCrew Episode 101_2_0,30
```

## One‑Shot Command
Analyze + auto‑repair (when offset ≥ threshold) + package, for each CSV row:

```
python csv_batch_processor.py batch.csv \
  --output-dir ./batch_results \
  --auto-repair --repair-threshold 100 \
  --repair-output-dir ./repaired_sync_files \
  --create-package --package-dir ./repair_packages \
  --plot --max-workers 3
```

What it does per row:
- Runs comprehensive analysis and writes `<episode>_analysis.json`
- Generates a formatted markdown report (unless `--skip-reports`)
- If overall offset ≥ `--repair-threshold`:
  - Applies intelligent repair and writes repaired file to `--repair-output-dir`
  - If `--create-package` is set, creates a bundle (folder + ZIP) in `--package-dir`

Notes:
- Default threshold is 100 ms. Adjust with `--repair-threshold`.
- Repaired files use safe names: `<episode>_REPAIRED.<ext>`.
- Packages include original (dub) file, repaired media, analysis JSON, repair report,
  visualization, and a summary.

## GPU‑Accelerated Mode
For faster analysis on supported systems, use the optimized GPU analyzer:

```
python csv_batch_processor.py batch.csv \
  --use-optimized-cli --gpu \
  --output-dir ./batch_results \
  --auto-repair --repair-threshold 100 \
  --repair-output-dir ./repaired_sync_files \
  --create-package --package-dir ./repair_packages \
  --max-workers 2 --max-chunks 50
```

- `--use-optimized-cli`: routes analysis via `sync_analyzer.cli.optimized_sync_cli`.
- `--gpu`: enables CUDA acceleration.
- Tune `--max-workers` to avoid I/O thrash with large MOV/ProRes inputs.

## Outputs
- Analysis & reports: `--output-dir`
  - `sync_report_<episode>_<hash>_<timestamp>.json` (SMPTE-enhanced analysis)
  - `<episode>_formatted_report.md` (AI-enhanced with SMPTE timecodes)
  - `<episode>_sync_chart.png` (with `--plot`)
  - `batch_processing_summary.json`
  - `batch_results_summary.csv` (see columns below)
- Repaired media: `--repair-output-dir`
- Packages: `--package-dir` (folder + `.zip`)

`batch_results_summary.csv` columns:
- Episode, Status, Duration_Seconds, JSON_Output, Report_Output
- Repaired_Output (present when `--auto-repair`)
- Package_Dir, Package_Zip (present when `--auto-repair --create-package`)

## Return Codes & Console Summary
- The batch prints a summary including successes, drift detections, failures,
  throughput, and when enabled, counts of repairs/packages created.
- Non‑zero exit when one or more rows fail analysis.

## Additional Options
- `--skip-reports` to suppress formatted markdown generation
- `--chunk-size 45` default; CSV can override per row via `chunk_size`
- `--max-workers N` parallel workers (default auto‑detects GPU count via nvidia‑smi)

## New Features in v1.3

### SMPTE Timecode Support
- **Frame-accurate analysis**: All reports now include SMPTE timecodes (HH:MM:SS:FF)
- **Frame rate detection**: Automatic detection of 23.976, 24, 25, 29.97, 30, 50, 59.94, 60 fps
- **Source timecode extraction**: Reads embedded timecodes from source files
- **Drop-frame compensation**: Proper handling of 29.97 fps drop-frame timecode
- **Professional terminology**: Industry-standard broadcast and post-production language

### AI-Enhanced LLM Reporting
- **Intelligent analysis**: Uses Llama 3.1 LLM for sophisticated report generation
- **SMPTE-formatted reports**: All time references use professional timecode format
- **Frame-offset calculations**: Precise frame-based offset measurements (e.g., "-7f (-0.320s)")
- **Professional insights**: Broadcast-quality analysis with actionable recommendations
- **Fallback support**: Graceful fallback to rule-based reports if LLM unavailable

Example enhanced report output:
```
### Critical Sync Issues
🔴 **SMPTE Timecode:** 00:06:45:00 - 00:07:15:00
✗ **Frame Offset:** -7f (-0.320s)
✗ **Similarity Score:** 0.450
```

## Troubleshooting
- **LLM Service**: Ensure Ollama is running: `curl http://localhost:11434/api/tags`
- **Model availability**: Verify llama3.1:8b model is installed: `ollama list`
- ProRes/MOV sources: the repair flow preserves video by copying to a MOV
  intermediate to avoid container incompatibilities; audio is corrected and
  re‑encoded (AAC) on mux. If you require MP4 output for a ProRes source, re‑encode
  video explicitly.
- "file not found" rows are skipped with a warning; verify CSV paths.
- Ensure ffmpeg/ffprobe are on PATH: `ffmpeg -version`, `ffprobe -version`.
- **Filename length**: Fixed filesystem limits for long filenames in optimized CLI
- If `repair_report.md` contains an error like "expected str, bytes or os.PathLike…",
  it indicates LLM formatting fell back incorrectly. This is fixed in v1.3; re‑run
  packaging to regenerate the report.

## Quick Examples
- Analyze only:
  `python csv_batch_processor.py example_batch.csv --output-dir batch_results`

- Analyze + auto‑repair + package:
  `python csv_batch_processor.py example_batch.csv --output-dir batch_results --auto-repair --repair-threshold 120 --repair-output-dir ./repaired_sync_files --create-package --package-dir ./repair_packages --plot --max-workers 2`

## Where This Is Implemented
- CLI: `csv_batch_processor.py` (flags: `--auto-repair`, `--repair-threshold`,
  `--repair-output-dir`, `--create-package`, `--package-dir`)
- Repair: `intelligent_sync_repair.py`
- Packaging: `sync_repair_packager.py`
- **NEW**: SMPTE utilities: `smpte_utils.py`
- **NEW**: LLM reporting: `llm_report_formatter.py`
- **NEW**: Enhanced metadata: `fastapi_app/app/api/v1/endpoints/files.py`
