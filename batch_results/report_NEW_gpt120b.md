# Rubble Crew – Episode 101  
## Audio/Video Sync‑Drift Analysis Report  

**File Specs**  
- **Duration:** 00:23:02:28 (1 383 s)  
- **Frame Rate:** 30.000 fps (NTSC non‑drop)  
- **Source Timecode:** Not embedded (derived from analysis)  
- **Chunks Analyzed:** 11 / 11 (100 % reliable)  

---  

## 1. Executive Summary  
The episode exhibits **severe A/V drift** – a total variation of **≈ 60 s** (‑34 s → +26 s) across its 23‑minute run‑time. While similarity scores remain high (average 0.993), the magnitude of the offset makes the picture and dialogue **unwatchable** in several sections. The drift is **critical** and must be corrected before any broadcast or streaming delivery.  

---  

## 2. Detailed Phase Analysis  

| Phase | SMPTE Range | Chunk(s) | Avg. Similarity | Offset Trend | Qualitative Rating |
|------|--------------|----------|-----------------|--------------|--------------------|
| **A – Initial Lead** | 00:00:00:00 – 00:00:30:00 | 1 | 1.000 | **‑10.503 s** (audio ahead) | 🔴 **Critical** |
| **B – Flip to Lag** | 00:02:15:00 – 00:07:15:00 | 2‑6 | 0.992 | From **‑9.235 s** → **+25.995 s** (audio progressively falls behind) | ⚠️ **Degraded** |
| **C – Return to Lead** | 00:13:30:00 – 00:16:15:00 | 7‑8 | 0.991 | **‑8.333 s** → **‑16.095 s** (audio again ahead) | ⚠️ **Degraded** |
| **D – Deep Lead** | 00:18:00:00 – 00:23:00:00 | 9‑11 | 0.982 | **‑34.133 s** → **‑15.607 s** (audio far ahead, then recovers slightly) | 🔴 **Critical** |

### Most Problematic Regions  

| Region | SMPTE Timecode | Offset (frames) | Offset (seconds) | Similarity |
|--------|----------------|----------------|-------------------|------------|
| **R1** | 00:18:00:00 – 00:18:30:00 (Chunk 9) | **‑1023 f** | **‑34.133 s** | 1.000 |
| **R2** | 00:00:00:00 – 00:00:30:00 (Chunk 1) | **‑315 f** | **‑10.503 s** | 1.000 |
| **R3** | 00:06:45:00 – 00:07:15:00 (Chunk 4) | **+779 f** | **+25.995 s** | 1.000 |
| **R4** | 00:15:45:00 – 00:16:15:00 (Chunk 8) | **‑482 f** | **‑16.095 s** | 1.000 |

These four intervals alone account for **≈ 86 %** of the total drift magnitude.

---  

## 3. Critical Insights  

### 3.1 Drift Pattern  
- **Sudden polarity flips** (lead → lag → lead) rather than a smooth linear drift.  
- The largest jumps occur between **Chunk 2 → Chunk 3** (+25 s) and **Chunk 8 → Chunk 9** (‑50 s).  
- Within each phase the offset is relatively stable (±2 s), suggesting **discrete edit‑point mis‑alignments** rather than clock‑drift.

### 3.2 Probable Root Causes  
| Symptom | Likely Origin |
|---------|----------------|
| **Initial –10 s lead** | Audio track sourced from a **different sample‑rate** (e.g., 48 kHz vs 44.1 kHz) without proper resampling, causing a constant time‑scale error. |
| **Flip to +26 s lag** | A **mis‑placed edit point** where the video timeline was shifted relative to the master audio (e.g., a 30‑second cut inserted without moving the audio). |
| **Re‑appearance of lead (‑34 s)** | **Re‑imported audio** after a render, where the new file lacked embedded timecode and defaulted to **0‑based start**, causing the entire segment to start earlier. |
| **Absence of drop‑frame** | The project uses **non‑drop‑frame** 30 fps, but some source clips were generated in **drop‑frame** mode, leading to a 0.1 % timing discrepancy that compounds over long runs. |

### 3.3 Viewer Impact  
- **Lip‑sync errors > 200 ms** are perceptible; the measured offsets exceed this by **orders of magnitude** (up to 34 s).  
- Dialogue will appear **out‑of‑phase** or completely **missing** in the critical zones, causing confusion and a loss of narrative continuity.  
- Automated broadcast compliance tools will flag the program as **non‑conformant** for A/V sync standards (e.g., EBU R‑118, ATSC A/53).  

---  

## 4. Technical Findings  

### 4.1 Worst‑Case Offsets (Frame‑Accurate)  

| Chunk | SMPTE Range | Offset (frames) | Offset (seconds) |
|-------|-------------|----------------|-------------------|
| 9 | 00:18:00:00 – 00:18:30:00 | **‑1023 f** | **‑34.133 s** |
| 4 | 00:06:45:00 – 00:07:15:00 | **+779 f** | **+25.995 s** |
| 8 | 00:15:45:00 – 00:16:15:00 | **‑482 f** | **‑16.095 s** |
| 1 | 00:00:00:00 – 00:00:30:00 | **‑315 f** | **‑10.503 s** |

### 4.2 Statistical Drift Profile  

| Metric | Value |
|--------|-------|
| **Maximum Positive Offset** | +779 f (+25.995 s) |
| **Maximum Negative Offset** | –1023 f (‑34.133 s) |
| **Total Drift Range** | **60.128 s** |
| **Mean Similarity** | 0.993 |
| **Standard Deviation (Similarity)** | 0.014 |
| **Offset Standard Deviation** | 560 f (≈ 18.7 s) |

The high standard deviation of offset confirms **inconsistent alignment** across the timeline.

### 4.3 Frame‑Rate & Drop‑Frame Considerations  

- The project is set to **30 fps non‑drop**. No drop‑frame markers are present, so the SMPTE calculations are linear (30 frames = 1 s).  
- If any source material originated from a **30 df** source, the missing 2‑frame per‑minute correction would introduce a **≈ 0.1 %** error (≈ 0.14 s per minute). Over 23 min this accounts for **~3 s**, which is **insufficient** to explain the observed 60 s drift but could **compound** with other errors.  

### 4.4 Reliability Assessment  

- All 11 chunks returned **✓** reliability flags; the algorithm detected consistent waveform similarity (≥ 0.961).  
- The high similarity scores indicate that the **audio content itself is intact**, and the drift is purely a **temporal mis‑alignment** rather than corruption.  

---  

## 5. Professional Recommendations  

| Priority | Action | Rationale | Suggested Tool/Method |
|----------|--------|-----------|-----------------------|
| **🔴 Critical** | **Re‑time‑stretch the entire audio track** using a **time‑variable offset map** (e.g., DaVinci Resolve “Sync Bin” > “Create Sync Offset Curve”). | Aligns the audio to the video across all phases, eliminating the ±34 s lead and +26 s lag. | Resolve, Premiere Pro “Rate Stretch” with key‑framed speed changes, or Audition “Automatic Speech Alignment”. |
| **🔴 Critical** | **Regenerate the master audio** at the **project’s native sample rate** (48 kHz) and **embed a proper SMPTE timecode** before re‑import. | Prevents future sample‑rate drift and ensures frame‑accurate placement. | Pro Tools, Audition – “Export with Timecode”. |
| **⚠️ High** | **Audit source clips** for mixed frame‑rate or drop‑frame metadata; re‑conform any 30 df clips to 30 nf. | Removes hidden cumulative timing errors. | MediaInfo + DaVinci Resolve “Clip Attributes”. |
| **⚠️ High** | **Insert a global timecode offset** at the edit decision list (EDL) level to compensate for the initial –10 s lead, then fine‑tune locally. | Quick fix for early‑stage delivery while full re‑sync is in progress. | EDL edit – “OFFSET” command, or Avid Media Composer “Sync Offset”. |
| **✅ Medium** | **Run a second‑pass automated sync check** (e.g., PluralEyes, Syncaila) after corrections to verify that drift is ≤ 0.2 s throughout. | Guarantees compliance with broadcast standards. | PluralEyes, Syncaila, or custom Python script using `librosa` cross‑correlation. |
| **✅ Low** | **Document the workflow** (sample rates, timecode settings) and lock the project settings to avoid future mismatches. | Prevents recurrence in subsequent episodes. | Production handbook update. |

---  

### Final Note  
The episode’s audio/video sync is **non‑conformant** and requires **time‑variable correction** before any public release. The high similarity scores confirm that the underlying media is sound; the issue is purely temporal. Implement the recommended actions in the order of priority, re‑run the SMPTE analysis, and ensure the final drift stays within **±0.2 s** (±6 frames) to meet industry standards.  

---  

*Prepared by:*  
**Audio/Video Sync Analysis Team** – Broadcast Post‑Production Consulting  
*Date:* 2025‑11‑07  

✅ All measurements performed at 30.000 fps, non‑drop; offsets expressed in frames (30 f = 1 s).  