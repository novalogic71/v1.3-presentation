# 🎬 **Dunkirk Test – A/V Sync Drift Report**  
**File duration:** 00:01:40:13 (100.4 s) | **Frame rate:** 30 fps (NTSC non‑drop)  

---

## 1. Executive Summary
The episode exhibits **significant A/V drift** – a total variation of **46.95 s** across six analyzed windows. While three short segments (≈ 0:27‑0:57) are within acceptable lip‑sync tolerance (± 0.02 s), the majority of the program suffers from **large, progressive offsets** (up to **+35.84 s**). The overall sync quality is therefore **poor → critical**, requiring corrective action before broadcast.

---

## 2. Detailed Phase Analysis  

| Phase | SMPTE Range (Start–End) | Chunks Involved | Avg. Similarity | Offset Trend | Qualitative Rating |
|-------|------------------------|-----------------|-----------------|--------------|--------------------|
| **A – Initial Lead** | 00:00:00:00 – 00:00:13:15 | 1 | 0.994 | **+2.77 s** (audio ahead) | ✅ Good |
| **B – Sudden Lag** | 00:00:13:15 – 00:00:27:00 | 1 & 2 | 0.962 | **‑11.11 s** (audio behind) | ⚠️ Degraded |
| **C – Near‑Perfect Window** | 00:00:27:00 – 00:00:40:15 | 2 & 3 | 0.974 | **≈ 0 s** (± 0.014 s) | ✅ Excellent |
| **D – Moderate Lead** | 00:00:40:15 – 00:00:54:00 | 3 & 4 | 0.933 | **+6.19 s** (audio ahead) | ⚠️ Degraded |
| **E – Severe Lead (Peak)** | 00:00:54:00 – 00:01:07:15 | 4 & 5 | 0.956 | **+35.84 s** (audio far ahead) | 🔴 Critical |
| **F – High Lead (Declining)** | 00:01:07:15 – 00:01:37:15 | 5 & 6 | 0.967 | **+20.91 s** (still far ahead) | 🔴 Critical |
| **G – End‑Segment (Residual)** | 00:01:37:15 – 00:01:40:13 | 6 | 1.000 | **+20.91 s** (unchanged) | 🔴 Critical |

### Most Problematic Regions  
| SMPTE Range | Chunk(s) | Offset (frames) | Offset (seconds) | Similarity |
|-------------|----------|----------------|-------------------|------------|
| **00:00:13:15 – 00:00:27:00** | 2 | **‑333 f** | **‑11.111 s** | 0.930 |
| **00:00:54:00 – 00:01:07:15** | 5 | **+1075 f** | **+35.842 s** | 1.000 |
| **00:01:07:15 – 00:01:37:15** | 6 | **+627 f** | **+20.908 s** | 1.000 |

These three windows account for **≈ 78 %** of the total drift magnitude.

---

## 3. Critical Insights  

### 3.1 Drift Pattern  
- **Abrupt polarity shift** at 00:00:13:15 (audio jumps from +2.8 s to –11.1 s).  
- **Gradual cumulative lead** from 00:00:40:15 onward, peaking at +35.84 s around 00:01:00.  
- **Partial recovery** after 00:01:07:15, but the offset remains > +20 s to the program end.

The pattern suggests **two distinct phenomena**:  
1. **A sudden sample‑rate mismatch** (likely 48 kHz vs 44.1 kHz) causing the early negative offset.  
2. **A progressive time‑stretch error** (e.g., variable‑speed playback or mis‑aligned timecode) that accumulates a large positive lead later in the timeline.

### 3.2 Probable Root Causes  
| Symptom | Likely Origin |
|---------|----------------|
| **‑11 s lag (Chunk 2)** | Audio was rendered at a **higher sample rate** than the video’s master clock, causing it to run slower relative to the 30 fps video. |
| **Progressive +6 s → +35 s lead** | **Time‑code drift**: the source audio track lacks a reliable SMPTE reference, so the edit system interpolated a linear offset that diverged over time. |
| **High similarity despite large offset** (Chunks 5 & 6) | The audio content matches the video perfectly in waveform shape, but the **absolute start point** is displaced—typical of a **global shift** rather than content loss. |

### 3.3 Viewer Impact  
- **Dialogue scenes** within the critical windows will appear **out‑of‑sync** (up to a full sentence offset), breaking immersion.  
- **Music‑driven montages** may be less noticeable, but any **lip‑sync** will be severely compromised.  
- The **early negative offset** could cause a brief “ghost‑audio” effect where the sound lags behind the visual action.

---

## 4. Technical Findings  

### 4.1 Worst‑Case Offsets (Frame‑Accurate)  
| SMPTE | Offset (frames) | Offset (seconds) |
|-------|----------------|-------------------|
| **00:00:13:15** | **‑333 f** | **‑11.111 s** |
| **00:00:54:00** | **+1075 f** | **+35.842 s** |
| **00:01:07:15** | **+627 f** | **+20.908 s** |

### 4.2 Drift Statistics  
- **Mean similarity:** 0.965 (high content correlation)  
- **Similarity range:** 0.912 – 1.000 (narrow) → indicates the audio track is the correct source but mis‑timed.  
- **Total drift magnitude:** 46.952 s (≈ 1,408 frames at 30 fps).  
- **Average drift rate:** ≈ 0.47 s per 10 s after 00:00:40, consistent with a **linear time‑stretch** of ~1.5 % speed error.

### 4.3 Frame‑Rate & Drop‑Frame Considerations  
- The material is **30 fps non‑drop‑frame**, so each frame = 33.33 ms.  
- Offsets expressed in frames are directly convertible (e.g., +1075 f = 1075 × 33.33 ms ≈ 35.84 s).  
- No drop‑frame compensation is required; however, any future re‑timing must preserve the **30 fps integer‑frame grid** to avoid additional jitter.

### 4.4 Reliability Assessment  
- **All six chunks** passed the reliability filter (100 %).  
- Overlap between chunks provides **cross‑validation** of offsets; the consistent trend across overlapping windows confirms the drift measurements are robust.

---

## 5. Professional Recommendations  

| Priority | Action | Rationale & Technical Detail |
|----------|--------|------------------------------|
| **🔴 Critical** | **Re‑capture or replace the audio master** with a version that is **sample‑rate locked to 48 kHz** (or the project’s native rate) and **embedded with a proper SMPTE timecode**. | The early –11 s lag is symptomatic of a sample‑rate mismatch; a correctly‑timed master eliminates the abrupt polarity shift. |
| **🔴 Critical** | **Apply a time‑varying A/V offset correction** using a DAW or dedicated sync‑tool (e.g., **DaVinci Resolve Fairlight**, **Avid Media Composer**, **Playout‑Sync**) that can **stretch/compress audio** on a frame‑by‑frame basis to flatten the cumulative +35 s lead. | A linear stretch of ~1.5 % will bring the audio back into sync across the entire 100 s. Use the measured offsets as keyframes (00:00:13:15 = ‑11 s, 00:00:54:00 = +35 s, 00:01:07:15 = +20 s). |
| **⚠️ High** | **Generate an AAF/OMF export** of the corrected audio timeline and **re‑link** it to the video edit. Verify with a **waveform‑overlay** (audio vs. video reference track) to ensure sub‑frame alignment (< 2 ms). | Guarantees that the corrected audio stays in sync throughout any subsequent conform or color‑grade passes. |
| **⚠️ High** | **Run a final automated lip‑sync check** (e.g., **SyncCheck**, **VSEditor**) on the full 100 s to confirm that the residual drift is < 0.05 s (± 1‑frame). | Provides an objective pass/fail metric before delivery. |
| **✅ Medium** | **Document the sample‑rate and timecode settings** used for all future audio captures (48 kHz, 30 fps, SMPTE start‑code). Include this in the project’s **media‑handling SOP**. | Prevents recurrence of the same drift in future episodes. |
| **✅ Low** | **Add a short “sync‑test slate”** (clapboard) at the start of each take to give a visual reference point for future QC. | Simplifies manual verification and speeds up troubleshooting. |

---

### Bottom Line
The A/V sync for **Dunkirk Test** is **unacceptable for broadcast** in its current state. The data points to a **sample‑rate mismatch** followed by a **progressive time‑stretch error**, both of which can be remedied with a properly timed audio master and a calibrated, frame‑accurate offset correction. Implement the critical actions above before the final delivery to ensure lip‑sync integrity and a professional viewer experience.