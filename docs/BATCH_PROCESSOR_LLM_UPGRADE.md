# ✅ Batch Processor Now Uses LLM Reports

**Date**: November 7, 2025
**Status**: ✅ COMPLETE
**Impact**: All batch processing now generates professional 120B model reports by default

---

## What Changed

The CSV batch processor (`scripts/batch/csv_batch_processor.py`) has been upgraded to use the **LLM report formatter** with the **gpt-oss:120b** model instead of the basic report formatter.

### Before:
```python
# Line 120: OLD
report_cmd = [
    'python', '-m', 'scripts.repair.sync_report_analyzer',  # Basic formatter
    str(json_output),
    '--name', episode_name,
    '--output', str(report_output)
]
```

### After:
```python
# Line 122: NEW
report_cmd = [
    'python', '-m', 'scripts.repair.llm_report_formatter',  # LLM formatter (120B)
    str(json_output),
    '--name', episode_name,
    '--output', str(report_output)
]
```

---

## Report Quality Improvements

| Aspect | Basic Reports (OLD) | LLM Reports (NEW) | Improvement |
|--------|---------------------|-------------------|-------------|
| **Content Size** | ~1-2 KB | ~8-10 KB | **5-8x more** ✅ |
| **Detail Level** | Basic metrics | Comprehensive analysis | ✅ |
| **Root Cause** | Generic list | Technical hypotheses | ✅ |
| **Recommendations** | Simple bullets | Prioritized action items | ✅ |
| **Formatting** | Plain markdown | Professional tables | ✅ |
| **Compliance** | Not mentioned | EBU R-118, ATSC A/53 | ✅ |
| **Viewer Impact** | Not mentioned | Detailed analysis | ✅ |
| **Statistics** | Basic | Complete metrics table | ✅ |

---

## New Command-Line Options

### **Default Behavior (LLM Reports)**
```bash
PYTHONPATH=. python scripts/batch/csv_batch_processor.py batch.csv \
  --use-optimized-cli \
  --gpu \
  --output-dir batch_results/
```
This will now automatically use **gpt-oss:120b** for professional reports.

### **If You Want Basic Reports (Faster)**
```bash
PYTHONPATH=. python scripts/batch/csv_batch_processor.py batch.csv \
  --use-optimized-cli \
  --gpu \
  --basic-reports \
  --output-dir batch_results/
```
Use `--basic-reports` flag to get the old simple reports (faster, less detail).

---

## Automatic Fallback

If the LLM report generation fails (e.g., Ollama server down), the system will **automatically fall back** to the basic report formatter:

```
⚠️  LLM report generation failed for Episode_101, falling back to basic report
```

This ensures you **always get a report**, even if the LLM is unavailable.

---

## Output Displays

When you run the batch processor, you'll now see:

```
🔥 CSV Batch Sync Processor
📁 CSV file: batch.csv
📊 File pairs to process: 3
🎯 GPUs available: 1
⚡ Max parallel workers: 1
📈 Generate plots: No
🚀 Engine: optimized CLI (GPU ON)
📝 Report generator: LLM (gpt-oss:120b) - Professional  ← NEW
💾 Output directory: batch_results/
```

The **"📝 Report generator"** line shows which formatter is being used.

---

## Performance Impact

| Metric | Basic Reports | LLM Reports | Difference |
|--------|---------------|-------------|------------|
| **Generation Time** | ~1 second | ~30 seconds | **+29s per file** |
| **Quality** | Good | Excellent | ✅ |
| **Client Ready** | No | Yes | ✅ |

**Trade-off**: Each report takes ~30 seconds longer to generate, but produces **broadcast-quality professional reports** suitable for client delivery.

---

## Example Output Comparison

### **Basic Report** (1.2 KB):
```markdown
📊 **Dunkirk Test Sync Analysis Report**
**Overall Offset:** +5.047s (+121f @ 24fps)
**Drift Detected:** Yes - 15.26s variation across file

## 💡 **Recommendations:**
- ✅ **File acceptable** - minor drift within tolerance
```

### **LLM Report** (8.5 KB):
```markdown
# Dunkirk Test – Audio/Video Sync Analysis Report

## 🚨 EXECUTIVE SUMMARY
**Status**: ⚠️ REQUIRES CORRECTION
**Critical Issue**: 15-second audio offset detected in final segment
**Impact**: Audio is 15 seconds LATE relative to video
**Action Required**: Apply constant time shift correction before delivery

| Region | SMPTE Timecode | Offset (frames) | Offset (seconds) | Severity |
|--------|----------------|----------------|-------------------|----------|
| R1 | 00:01:30:00 – 00:01:42:00 | +360 f | +15.01 s | 🔴 CRITICAL |

### Root Cause Analysis
| Symptom | Likely Origin |
|---------|----------------|
| +15s lag | Audio track sourced from different sample-rate (48kHz vs 44.1kHz) |
| Constant offset | Timecode mismatch at edit point |

### Recommended Fix
**Method**: Constant Offset Correction
**Tool**: DaVinci Resolve / Premiere Pro
**Steps**: Apply -15.01s time shift to audio track
```

---

## Configuration Files Updated

1. **`scripts/batch/csv_batch_processor.py`** (Lines 118-147, 308-311, 352-353, 399, 421)
   - Added LLM report generation logic
   - Added `--use-llm-reports` flag (default: True)
   - Added `--basic-reports` flag for fallback
   - Added automatic fallback on LLM failure
   - Added status display

2. **`scripts/repair/llm_report_formatter.py`** (Line 264-265)
   - Fixed command-line default to use `gpt-oss:120b`
   - Previously had incorrect `llama3.2` default

---

## Testing

Tested with:
- ✅ Dunkirk Test files (1.7 minutes, 6 chunks)
- ✅ Rubble Crew Ep101 (23 minutes, 11 chunks)
- ✅ Batch processing with 3 files
- ✅ Automatic fallback when LLM unavailable

**All tests passed** ✅

---

## Migration Notes

### For Existing Workflows:

**No action required** - The change is backward compatible:
- Default behavior now uses LLM (better quality)
- Use `--basic-reports` to get old behavior
- Automatic fallback ensures reports always generated

### For Scripts/Automation:

If you have automated scripts calling the batch processor:
- **No changes needed** - will automatically use LLM reports
- Add `--basic-reports` flag if you need faster processing
- Check for new status line: `📝 Report generator: LLM (gpt-oss:120b)`

---

## Troubleshooting

### "LLM report generation failed"
**Cause**: Ollama server not running or model not available
**Solution**: Check `ollama list` and ensure `gpt-oss:120b` is installed
**Workaround**: System automatically falls back to basic reports

### Reports still showing basic format
**Cause**: `--basic-reports` flag is being used
**Solution**: Remove the flag to use LLM reports
**Check**: Look for `📝 Report generator: Basic - Fast` in output

### LLM reports too slow
**Cause**: 120B model takes ~30s per report
**Solution**: Use `--basic-reports` for faster processing
**Alternative**: Consider using 20B model (edit line 27 in llm_report_formatter.py)

---

## Next Steps (Optional Enhancements)

1. **Model Selection**: Add `--llm-model` flag to choose between 8B/20B/120B
2. **Parallel Generation**: Generate multiple LLM reports in parallel
3. **Caching**: Cache LLM responses for identical analysis data
4. **Custom Templates**: Add industry-specific report templates

---

**Bottom Line**: The batch processor now generates **professional broadcast-quality reports** by default, with automatic fallback to ensure reliability. No changes needed to your existing workflows! 🎯

