# LLM Model Comparison: llama3.1:8b vs gpt-oss:120b

**Test Date**: November 7, 2025
**Test File**: rubble_crew_ep110_analysis.json (56KB data)
**Purpose**: Compare report quality between 8B and 120B parameter models

---

## Report Size Comparison

| Model | Parameters | File Size | Words (approx) | Quality |
|-------|-----------|-----------|----------------|---------|
| **llama3.1:8b** | 8 billion | 2,740 bytes | ~400 words | Good |
| **gpt-oss:120b** | 120 billion | 9,734 bytes | ~1,500 words | **Excellent** ⭐ |

**The 120B model generated 3.5x more content** with significantly better detail and professionalism.

---

## Key Differences

### 1. **Structure & Formatting**

**llama3.1:8b** (Old):
- Basic markdown with simple headers
- Standard bullet points
- Plain tables
- Generic formatting

**gpt-oss:120b** (New):
- Professional document headers with metadata
- Multi-level tables with advanced formatting
- Priority indicators (🔴 🟠 🟡 🟢)
- SMPTE timecode formatting
- Statistical analysis sections
- Executive summary with severity rating

---

### 2. **Technical Depth**

**llama3.1:8b** (Old):
```
Critical Insights:
* Gradual Drift Pattern: The degraded sync phase exhibits a gradual
  increase in offset...
* Sudden Changes: The poor sync phase shows sudden changes...
* Impact Assessment: The significant drift issues will compromise viewer experience
```

**gpt-oss:120b** (New):
```
### 3.2 Probable Root Causes
| Symptom | Likely Origin |
|---------|---------------|
| Large, alternating offsets | Mismatched sample‑rate conversion (e.g., audio at 48 kHz
                              vs. video 30 fps) combined with non‑linear time‑stretch |
| Sudden ± 1 000 frame jumps | Incorrect SMPTE start code on one track or an in‑place
                               edit where a segment was replaced without re‑time‑coding |
| Low similarity scores | Audio bleed / background noise causing correlation algorithm
                          to mis‑detect sync |
```

The 120B model provides **specific technical hypotheses** with industry-standard terminology.

---

### 3. **Actionable Recommendations**

**llama3.1:8b** (Old):
```
Professional Recommendations:
1. Re-dubbing: Perform re-dubbing on critical regions
2. Time-Variable Correction: Apply time-variable correction to address gradual drift
3. Source Material Review: Review source material for potential issues
```

**gpt-oss:120b** (New):
```
| Priority | Action | Target Segment(s) | Rationale |
|----------|--------|-------------------|-----------|
| 🔴 Critical | Re‑sync the master audio track using a time‑variable offset
              (V‑time stretch) that follows the measured drift curve |
              Entire program – especially chunks 2, 11, 12, 17 |
              Eliminates the ± 1 000‑frame jumps and restores consistent lip‑sync |

Implementation Notes:
1. Dynamic Time‑Warp – Export the audio waveform, import into a DAW, and use a
   tempo‑map derived from the offset table...
2. Re‑time‑code Generation – Use a LTC generator locked to the master video
   frame clock...
```

The 120B model provides **prioritized action items** with specific implementation steps.

---

### 4. **Industry Terminology**

**llama3.1:8b** (Old):
- Uses generic terms
- Basic SMPTE references
- Simple descriptions

**gpt-oss:120b** (New):
- SMPTE timecode formatting (HH:MM:SS:FF)
- Frame-accurate measurements
- Broadcast compliance references (FCC lip-sync rules)
- Professional terminology: VITC, MTC, LTC generator, tempo-map
- Sample rate analysis (48 kHz vs 44.1 kHz)
- Industry tools mentioned (PluralEyes, DaVinci Resolve)

---

### 5. **Data Analysis**

**llama3.1:8b** (Old):
```
Worst Sync Regions:
  + SMPTE: 00:07:37:15 - 00:08:07:15 (chunk 21)
  + Offset: +12.000s
  + Similarity score: 0.015
```

**gpt-oss:120b** (New):
```
### 4.2 Statistical Overview
| Metric | Value |
|--------|-------|
| Total duration | 00:23:06:15 (1386.5 s) |
| Frame rate | 30 fps (NTSC‑Non‑Drop) |
| Number of chunks | 61 |
| Reliable chunks | 4 (6.6 %) |
| Average similarity | 0.026 |
| Mean absolute offset | ≈ + 12 s (≈ 360 frames) |
| Standard deviation of offset | ≈ 22 s (≈ 660 frames) |
| Peak drift magnitude | 45.0 s (≈ 1350 frames) |
```

The 120B model provides **comprehensive statistical analysis** with frame-accurate conversions.

---

### 6. **Problem Identification**

**llama3.1:8b** (Old):
- Lists 4 worst regions
- Basic offset numbers
- Generic descriptions

**gpt-oss:120b** (New):
- Identifies top 4 problem blocks that account for "≈ 80% of total measured drift"
- Provides polarity analysis (audio ahead vs behind)
- Explains drift patterns (alternating, gradual ramps, sudden jumps)
- Links symptoms to probable root causes
- Quantifies viewer impact (lip-sync errors > 200ms = 6 frames)

---

## Executive Summary Comparison

### llama3.1:8b (Old):
> "The sync analysis of Rubble Crew Ep110 reveals significant drift issues,
> compromising overall audio-visual synchronization. The average similarity
> score is 0.026, indicating a degraded sync quality."

**Length**: 2 sentences
**Tone**: Generic
**Actionability**: Low

### gpt-oss:120b (New):
> "The A/V relationship in Rubble Crew Ep110 is significantly degraded –
> the analysis shows a 45 s peak drift (≈ 1350 frames) across the 23 min 06 s
> program. Only 4% of the examined segments meet a reliability threshold,
> indicating that the majority of the file lacks a stable reference. The most
> severe offsets exceed ±1 000 frames (≈ ‑35 s / + 43 s), which will be
> perceptible as lip‑sync errors and timing jumps for the viewer.
>
> Severity: Critical – immediate corrective action is required before broadcast
> or streaming distribution."

**Length**: 4 sentences + severity rating
**Tone**: Professional broadcast language
**Actionability**: High - includes specific severity classification

---

## Verdict

| Aspect | llama3.1:8b (8B) | gpt-oss:120b (120B) | Winner |
|--------|------------------|---------------------|--------|
| **Content Length** | 2,740 bytes | 9,734 bytes | ✅ 120B (3.5x more) |
| **Technical Depth** | Basic | Advanced | ✅ 120B |
| **Industry Terms** | Generic | Professional | ✅ 120B |
| **Actionability** | Moderate | High | ✅ 120B |
| **Data Analysis** | Simple | Comprehensive | ✅ 120B |
| **Formatting** | Basic | Professional | ✅ 120B |
| **Root Cause Analysis** | Limited | Detailed | ✅ 120B |
| **Implementation Details** | None | Specific steps | ✅ 120B |
| **Generation Speed** | ~5 seconds | ~30 seconds | ✅ 8B |
| **Model Size** | 4.9 GB | 65 GB | ✅ 8B |

---

## Recommendation

**Use gpt-oss:120b** for production reports:

### Pros:
- ✅ **3.5x more detailed** analysis
- ✅ **Professional broadcast terminology** and formatting
- ✅ **Actionable recommendations** with priority levels
- ✅ **Frame-accurate measurements** and SMPTE compliance
- ✅ **Root cause analysis** with technical hypotheses
- ✅ **Implementation steps** for remediation
- ✅ **Statistical analysis** and data visualization

### Cons:
- ⚠️ Slower generation (~30s vs ~5s)
- ⚠️ Larger model (65GB vs 4.9GB)

### When to use llama3.1:8b:
- Quick spot checks
- Internal draft reports
- When speed is critical
- Limited GPU memory

### When to use gpt-oss:120b:
- ✅ **Client deliverables** (recommended)
- ✅ **Broadcast compliance** reports
- ✅ **Critical issue** analysis
- ✅ **Executive presentations**
- ✅ **Production workflows** (as documented)

---

**Bottom Line**: The gpt-oss:120b model produces **professional-grade reports** that are suitable for client delivery and broadcast compliance. The additional 25 seconds of generation time is a worthwhile investment for the significantly improved quality and actionability.

---

**Files Generated**:
- `report_OLD_llama3.1_8b.md` - 8B model output (2.7KB)
- `report_NEW_gpt-oss_120b.md` - 120B model output (9.7KB)
- This comparison document

**Configuration Updated**: `scripts/repair/llm_report_formatter.py` now uses `gpt-oss:120b` by default.
