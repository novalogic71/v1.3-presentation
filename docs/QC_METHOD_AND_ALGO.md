# QC Tab and Expanded View — Method and Algorithm

This document describes the methodology, sign conventions, playback logic, and drawing algorithms used by the Quality Control (QC) modal and the Expanded Waveform view in the Web UI.

## Terminology and Sign Conventions

- `offset_seconds` (float): Signed sync offset computed by the analyzer.
  - Positive: Dub is ahead (early) relative to Master.
  - Negative: Dub is behind (late) relative to Master.
- “Before” view: Representation or playback of the natural, out‑of‑sync state.
- “After” view: Representation or playback with the correction applied (in‑sync).

These conventions are used consistently for playback across UI, QC modal, and expanded view. The Expanded View visuals also follow this; the QC waveform visuals currently invert Before/After only for drawing (see “Known Difference” below).

## Playback Algorithm (Shared)

All playback routes through `CoreAudioEngine.playComparison(offsetSeconds, corrected)`.

Inputs:
- `offsetSeconds`: signed sync offset.
- `corrected` (bool): false → play natural mismatch; true → play corrected/synchronized.

Behavior:
- When `corrected == false` (Before):
  - Play both sources starting at the same wall‑clock time and same content position. No timing adjustment. The natural offset is audible.
- When `corrected == true` (After):
  - If `offsetSeconds > 0` (dub early): delay the dub start by `offsetSeconds` seconds (schedule time shift). Master starts at `t0`, dub at `t0 + offsetSeconds`.
  - If `offsetSeconds < 0` (dub late): advance dub content by trimming its buffer offset by `abs(offsetSeconds)` (start dub further into its buffer); both streams start at the same wall‑clock time.

Routing and leveling:
- Master signal panned left, Dub panned right for A/B comparison.
- Per‑track gain, pan, mute, and master output volume are applied via the engine (`setVolume`, `setPan`, `setMute`, `setMasterOutputVolume`).
- WebAudio `AudioBufferSourceNode` path is used when decoding succeeds; otherwise a resilient fallback uses media elements (`<audio>/<video>`) with optional `MediaElementSource` nodes.

Key code:
- `web_ui/core-audio-engine.js`: `playComparison`, `setVolume`, `setPan`, `setMute`, `updateTrackGains`.
- Call sites:
  - Expanded view buttons → `WaveformVisualizer.playAudioComparison` → engine.
  - QC modal buttons → `QCInterface.playComparison` → engine.

## Waveform Visualization — Expanded View

Goals:
- Present Master and Dub waveforms on a unified timeline.
- Show “Before” (out‑of‑sync) and “After” (synchronized) views.
- Provide overlay or stacked layout; zoom/pan; time markers; offset indicators.

Data and rendering:
- Synthetic “peaks” are generated for visualization with consistent time scaling; when available, real peaks from decoded audio are used by the `CoreAudioEngine` for the QC modal.
- Pixel mapping: `pixelsPerSecond = waveformWidth / viewWindow`; `offsetPixels = offsetSeconds * pixelsPerSecond`.
- Positive offset (“dub ahead”) shifts Dub content left; negative shifts right. Implementation: use source index `i + offsetPixels` when synthesizing Dub waveform samples.

UI logic:
- Overlay vs Stacked modes toggle redraws using the same stored waveform data.
- Before view: Master vs Dub with `offsetSeconds` applied to Dub (“Out of Sync”).
- After view: Master vs Dub with zero offset (aligned), plus comparison overlay and legends (“Synchronized”).

Key code:
- `web_ui/waveform-visualizer.js`:
  - `generateUnifiedTimeline`, `drawUnifiedTimeline`, `drawOverlayWaveforms`, `drawStackedWaveforms`.
  - View toggles: `toggleBeforeAfterView`, `redrawUnifiedTimelineWithBefore`, `redrawUnifiedTimelineWithAfter`.
  - Interaction: `handleWaveformAction` for zoom/pan, play before/after, fit‑to‑offset, etc.

## QC Modal — Method and Data Flow

Purpose:
- Provide focused, review‑oriented playback and visualization with simple controls and status.

Data flow:
- Inputs come from batch rows or current selection. The UI constructs `syncData`:
  - Master/Dub filenames, paths, `detectedOffset`, and `confidence`.
  - Media URLs:
    - If video: `/api/v1/files/proxy-audio?path=...&format=wav` (server extracts audio via ffmpeg).
    - If audio: `/api/v1/files/raw?path=...` (server streams bytes).
- `QCInterface` asks `CoreAudioEngine` to load both URLs concurrently. Engine will:
  - Try WebAudio decode of raw; if it fails, try proxy transcode; if that fails, fall back to media elements and generate placeholder peaks.
  - Emit `onAudioLoaded` events and store `masterWaveformData`/`dubWaveformData` for drawing.

Playback:
- “Play Problem” → `corrected=false` (natural mismatch).
- “Play Fixed” → `corrected=true` (correction applied as described above).

Visualization:
- Draws master and dub peaks on a canvas with the same time scaling.
- Offset indicator: vertical line and label showing magnitude and direction.

Key code:
- `web_ui/qc-interface.js`: `open`, `loadAudioFilesAsync`, `playComparison`, `updateWaveform`, `drawWaveformComparison`.
- `web_ui/server.py`: `/api/v1/files/raw`, `/api/v1/files/proxy-audio` endpoints for local‑only media serving.

## Known Difference (QC Visual Toggle)

At present, QC waveform drawing uses:

```js
const isAfterView = ...;
const visualOffset = isAfterView ? offset : 0; // After shows problem; Before aligned
```

This inverts the naming compared to playback and the Expanded View (where “After” is synchronized). Playback buttons in the QC modal are correct; only the QC canvas labels/toggle semantics differ.

Recommendation:
- Update QC drawing so that:
  - Before view: draw with `visualOffset = offset` (problem).
  - After view: draw with `visualOffset = 0` (aligned).
- Align the mode labels to: `Before Fix (Out of Sync)`, `After Fix (Synchronized)`.

## Developer Pointers

- Sign convention enforcement:
  - Visualizer synthesis: `generateRealisticWaveformData(..., 'dub', offset)`; uses `i + offsetPixels` for Dub.
  - Engine correction: schedule delay when dub is early; trim dub buffer offset when dub is late.
- Global play interceptors:
  - `web_ui/app.js` patches `WaveformVisualizer.playAudioComparison` to delegate to `CoreAudioEngine` and adds a capturing click handler for `.waveform-btn[data-action^='play-']` to ensure consistent behavior.
- Media robustness:
  - Server uses ffmpeg/ffprobe; make sure they’re on PATH.
  - For large or unsupported files, engine falls back to media‑element peaks so the QC canvas still renders.

## Quick QA Checklist

- Run analysis, open Expanded View:
  - Before shows out‑of‑sync; After shows synchronized.
  - Play Before/After: audible behavior matches visuals.
- Open QC modal via batch row or Expanded View:
  - “Play Problem” = natural offset; “Play Fixed” = synchronized.
  - Waveform renders and follows the recommended toggle semantics (once aligned as above).
  - Volume/balance/mute controls affect playback.

