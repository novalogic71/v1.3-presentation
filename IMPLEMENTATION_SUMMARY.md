# False Peak Detection Fix - Implementation Summary

## Problem
The sync detection algorithm was finding false correlation peaks at large offsets (e.g., 115s) when analyzing long audio files (45+ minutes). This occurred because:
1. Full-file correlation was finding similar audio content later in the files
2. Peak prominence validation was insufficient
3. SmartVerifier thresholds were too lenient for large offsets

## Solution Implemented

### 1. Limited Analysis Duration (audio_sync_detector.py)
**Location**: `analyze_sync()` method, lines ~977-995

- **Change**: Limit audio to first 5 minutes (300 seconds) before feature extraction
- **Impact**: Prevents false matches from later parts of long files
- **Applied to**: All correlation methods (MFCC, onset, spectral, raw audio)

```python
MAX_ANALYSIS_DURATION = 300.0  # 5 minutes
master_samples_limit = int(MAX_ANALYSIS_DURATION * self.sample_rate)
dub_samples_limit = int(MAX_ANALYSIS_DURATION * self.sample_rate)

if len(master_audio_for_analysis) > master_samples_limit:
    master_audio_for_analysis = master_audio_for_analysis[:master_samples_limit]
if len(dub_audio) > dub_samples_limit:
    dub_audio = dub_audio[:dub_samples_limit]
```

### 2. Peak Prominence Validation
**Location**: All correlation methods

- **Raw Audio Correlation** (lines ~733-746): Reject peaks with ratio <2.0x vs second peak
- **MFCC Correlation** (lines ~508-520): Reject peaks with ratio <1.5x vs second peak  
- **Spectral Correlation** (lines ~676-688): Reject peaks with ratio <1.5x vs second peak

**Implementation**:
```python
sorted_peaks = np.sort(correlation_abs)[-5:]  # Top 5 peaks
peak_ratio = sorted_peaks[-1] / (sorted_peaks[-2] + 1e-8)
if peak_ratio < threshold:
    confidence_penalty = peak_ratio / threshold  # Reduce confidence
```

### 3. Sanity Checks - Offset vs Duration
**Location**: All correlation methods

- **Check**: Reject offsets >50% of analysis duration
- **Impact**: Catches obviously wrong offsets before they propagate

```python
analysis_duration = min_len / self.sample_rate
max_reasonable_offset = analysis_duration * 0.5
if abs(offset_seconds) > max_reasonable_offset:
    return low_confidence_result("Offset too large")
```

### 4. Enhanced SmartVerifier Thresholds (smart_verify.py)
**Location**: `smart_verify.py`, lines 55-75

**Changes**:
- Lowered `large_offset` threshold: 10s → 5s
- Added `very_large_offset` threshold: 30s (mandatory verification)
- Lowered `VERIFICATION_THRESHOLD`: 0.30 → 0.20 (20% severity triggers)
- Increased `large_offset` weight: 0.25 → 0.35
- Added `very_large_offset` weight: 1.0 (always triggers)

**Impact**: Large offsets (>30s) now ALWAYS trigger verification, preventing false peaks from being accepted.

## Testing Recommendations

1. **Re-run the problematic batch**: Test with `wb_dubsync_batch_standard.csv`
2. **Verify false peaks are caught**: Files with 89s-212s offsets should now:
   - Either find correct offsets (<30s)
   - Or trigger SmartVerifier verification
   - Or return low-confidence results

3. **Check logs for warnings**:
   - "Low peak prominence ratio" - indicates ambiguous matches
   - "Offset exceeds 50% of analysis duration" - indicates false peak
   - "very_large_offset" - triggers mandatory verification

## Files Modified

1. `sync_analyzer/core/audio_sync_detector.py`
   - Added duration limiting in `analyze_sync()`
   - Added peak prominence validation to all correlation methods
   - Added sanity checks for offset vs duration

2. `sync_analyzer/core/smart_verify.py`
   - Lowered thresholds for large offsets
   - Added mandatory verification for offsets >30s
   - Increased severity weights for suspicious offsets

## Expected Behavior

**Before Fix**:
- Files with 115s offset accepted as correct
- SmartVerifier severity: 0.25 (below 0.30 threshold)
- No verification triggered

**After Fix**:
- Analysis limited to first 5 minutes
- Peak prominence validated (rejects ambiguous peaks)
- 115s offset triggers:
  - Sanity check failure (>50% of 5min = 150s threshold)
  - OR SmartVerifier mandatory verification (>30s)
  - OR Low confidence due to peak ratio

## Backward Compatibility

- ✅ Existing short files (<5 min) unaffected
- ✅ Existing correct offsets (<30s) unaffected  
- ✅ Only affects problematic long files with false peaks
- ✅ Low-confidence results still returned (not errors)
