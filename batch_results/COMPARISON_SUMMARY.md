# Report Comparison: Batch Results Analysis

**Date**: November 7, 2025
**Source**: batch_results/sync_report_...202759.json (60KB)
**Episode**: Rubble Crew Ep101 (23 minutes, 11 chunks)

---

## Size Comparison

| Model | Size | Content | Ratio |
|-------|------|---------|-------|
| **llama3.1:8b** (OLD) | 3,373 chars | ~500 words | 1.0x |
| **gpt-oss:120b** (NEW) | 8,454 chars | ~1,250 words | **2.5x** ✅ |

**The 120B model generated 2.5x more content** with significantly deeper analysis.

---

## Key Differences

### 1. Executive Summary

**OLD (llama3.1:8b)**:
> "The sync analysis of "Rubble Crew Ep101" reveals a significant drift pattern throughout the episode, with an average similarity score of 0.993 and a maximum deviation of 60.128 seconds."

- Generic language
- Basic metrics
- No severity classification

**NEW (gpt-oss:120b)**:
> "The episode exhibits **severe A/V drift** – a total variation of **≈ 60 s** (‑34 s → +26 s) across its 23‑minute run‑time. While similarity scores remain high (average 0.993), the magnitude of the offset makes the picture and dialogue **unwatchable** in several sections. The drift is **critical** and must be corrected before any broadcast or streaming delivery."

- ✅ **Bold severity classification** ("severe", "unwatchable", "critical")
- ✅ **Specific range** (‑34 s → +26 s)
- ✅ **Actionable consequence** (must correct before broadcast)
- ✅ **Professional language** (broadcast compliance terminology)

---

### 2. Phase Analysis

**OLD Model** - Simple text list:
```
### Excellent Sync (SMPTE Timecode: 00:00:00:00 - 00:04:30:00)
✅ Chunk Numbers: 1-3
✅ Similarity Scores: 1.000
✅ Description: The initial phase exhibits excellent sync quality...
```

**NEW Model** - Professional table:
```
| Phase | SMPTE Range | Chunk(s) | Avg. Similarity | Offset Trend | Qualitative Rating |
|------|--------------|----------|-----------------|--------------|--------------------|
| A – Initial Lead | 00:00:00:00 – 00:00:30:00 | 1 | 1.000 | ‑10.503 s (audio ahead) | 🔴 Critical |
| B – Flip to Lag | 00:02:15:00 – 00:07:15:00 | 2‑6 | 0.992 | ‑9.235 s → +25.995 s | ⚠️ Degraded |
```

✅ **Multi-column table** with severity icons
✅ **Phase naming** (A, B, C, D)
✅ **Directional analysis** (lead vs lag)
✅ **Trend visualization** (arrows showing progression)

---

### 3. Problem Identification

**OLD Model**:
```
The worst sync regions are:
* SMPTE timecode 00:09:00:00 with an offset of +297f (+9.903s)
* SMPTE timecode 00:18:30:00 with an offset of -1023f (-34.133s)
```

**NEW Model**:
```
| Region | SMPTE Timecode | Offset (frames) | Offset (seconds) | Similarity |
|--------|----------------|----------------|-------------------|------------|
| R1 | 00:18:00:00 – 00:18:30:00 | ‑1023 f | ‑34.133 s | 1.000 |
| R2 | 00:00:00:00 – 00:00:30:00 | ‑315 f | ‑10.503 s | 1.000 |
| R3 | 00:06:45:00 – 00:07:15:00 | +779 f | +25.995 s | 1.000 |
| R4 | 00:15:45:00 – 00:16:15:00 | ‑482 f | ‑16.095 s | 1.000 |

These four intervals alone account for ≈ 86 % of the total drift magnitude.
```

✅ **Region labels** (R1-R4 for easy reference)
✅ **Comprehensive table** with all metrics
✅ **Impact quantification** (86% of total drift)
✅ **Similarity scores** included for confidence

---

### 4. Root Cause Analysis

**OLD Model**:
```
The root cause of this drift is likely due to a combination of factors, including:
  + Inconsistent frame rate compensation (drop-frame vs non-drop).
  + Timecode inconsistencies between source materials.
  + Post-production workflow errors.
```

**NEW Model**:
```
| Symptom | Likely Origin |
|---------|----------------|
| Initial –10 s lead | Audio track sourced from a different sample‑rate (e.g., 48 kHz vs 44.1 kHz) without proper resampling |
| Flip to +26 s lag | A mis‑placed edit point where the video timeline was shifted relative to the master audio |
| Re‑appearance of lead (‑34 s) | Re‑imported audio after a render, where the new file lacked embedded timecode and defaulted to 0‑based start |
| Absence of drop‑frame | Project uses non‑drop‑frame 30 fps, but some source clips were generated in drop‑frame mode |
```

✅ **Symptom-to-cause mapping table**
✅ **Specific technical hypotheses** (sample rate, edit points, timecode)
✅ **Actionable diagnostics** (can verify each hypothesis)
✅ **Professional terminology** (0-based start, drop-frame compensation)

---

### 5. Viewer Impact

**OLD Model**: ❌ Not mentioned

**NEW Model**:
```
### 3.3 Viewer Impact
- Lip‑sync errors > 200 ms are perceptible; the measured offsets exceed this by orders of magnitude (up to 34 s).
- Dialogue will appear out‑of‑phase or completely missing in the critical zones, causing confusion and a loss of narrative continuity.
- Automated broadcast compliance tools will flag the program as non‑conformant for A/V sync standards (e.g., EBU R‑118, ATSC A/53).
```

✅ **Perceptual thresholds** (200ms rule)
✅ **Viewer experience description** (out-of-phase dialogue)
✅ **Compliance references** (EBU R-118, ATSC A/53)
✅ **Business impact** (non-conformant for broadcast)

---

### 6. Statistical Analysis

**OLD Model**:
```
Statistical analysis reveals a linear drift pattern, with a correlation coefficient (R) of 0.95.
```

**NEW Model**:
```
| Metric | Value |
|--------|-------|
| Maximum Positive Offset | +779 f (+25.995 s) |
| Maximum Negative Offset | –1023 f (‑34.133 s) |
| Total Drift Range | 60.128 s |
| Mean Similarity | 0.993 |
| Standard Deviation (Similarity) | 0.014 |
```

✅ **Comprehensive metrics table**
✅ **Frame and time conversions**
✅ **Statistical measures** (mean, std dev)
✅ **Range analysis** (max positive/negative)

---

### 7. Professional Formatting

**OLD Model**:
- Basic markdown
- Simple bullet points
- Generic icons (✅ ⚠️ ❌)

**NEW Model**:
- **Document header** with file specs
- **Numbered sections** with hierarchy
- **Professional tables** throughout
- **Severity indicators** (🔴 Critical, ⚠️ Degraded)
- **Mathematical symbols** (≈, →, %)
- **SMPTE formatting** (HH:MM:SS:FF)
- **Frame-accurate notation** (‑1023 f)

---

## Summary Table

| Feature | llama3.1:8b (8B) | gpt-oss:120b (120B) | Winner |
|---------|------------------|---------------------|--------|
| **Content Depth** | Basic | Comprehensive | ✅ 120B |
| **Executive Summary** | Generic | Severe/Critical classification | ✅ 120B |
| **Phase Analysis** | Text list | Professional tables | ✅ 120B |
| **Root Cause** | Generic list | Symptom-cause mapping | ✅ 120B |
| **Viewer Impact** | Not mentioned | Detailed analysis | ✅ 120B |
| **Statistics** | One metric | Complete table | ✅ 120B |
| **Compliance** | Not mentioned | EBU/ATSC references | ✅ 120B |
| **Formatting** | Basic | Professional | ✅ 120B |
| **Actionability** | Low | High | ✅ 120B |
| **Generation Time** | ~5 seconds | ~30 seconds | ✅ 8B |

---

## Verdict

The **gpt-oss:120b** model produces **broadcast-quality professional reports** suitable for:

✅ **Client deliverables**
✅ **Broadcast compliance** documentation
✅ **Executive presentations**
✅ **Technical post-mortem** analysis
✅ **Production workflow** integration

The additional 25 seconds of generation time is justified by the **2.5x more content** and **significantly higher quality** of analysis and recommendations.

---

## Files Generated

- `batch_results/report_OLD_llama8b.md` - 8B model output (3.4KB)
- `batch_results/report_NEW_gpt120b.md` - 120B model output (8.5KB)
- `batch_results/COMPARISON_SUMMARY.md` - This document

---

**Recommendation**: Use **gpt-oss:120b** as the default model for all production reports.

**Configuration**: The model is already set in `scripts/repair/llm_report_formatter.py` line 27.
