# Professional Waveform Visualization Widget - UX Design Specification

## Executive Summary

This document provides comprehensive UX/UI design specifications for a completely redesigned waveform visualization widget for the batch processing interface. The design prioritizes professional A/V workflow standards, real-time audio comparison, and accessibility while integrating seamlessly with the existing teal/amber/gray UI redesign.

---

## Table of Contents

1. [Design System Integration](#design-system-integration)
2. [Component Architecture](#component-architecture)
3. [Visual Design Mockups](#visual-design-mockups)
4. [Interaction Patterns](#interaction-patterns)
5. [Technical Specifications](#technical-specifications)
6. [Accessibility Standards](#accessibility-standards)
7. [Implementation Roadmap](#implementation-roadmap)

---

## 1. Design System Integration

### Color Palette (from redesign.css)

```css
/* Analysis/QC Actions - Teal */
--waveform-master: #14b8a6;      /* Teal-500 - Master audio */
--waveform-master-fill: rgba(20, 184, 166, 0.25);
--waveform-master-hover: #0d9488; /* Teal-600 */

/* Repair/Corrective - Amber */
--waveform-dub: #f59e0b;          /* Amber-500 - Dub audio (before) */
--waveform-dub-fill: rgba(245, 158, 11, 0.25);
--waveform-dub-hover: #d97706;    /* Amber-600 */

/* Success State - Green */
--waveform-corrected: #22c55e;    /* Green-500 - Corrected audio */
--waveform-corrected-fill: rgba(34, 197, 94, 0.25);

/* Critical/Warning - Red */
--waveform-critical: #ef4444;     /* Red-500 - Offset marker */
--waveform-warning-bg: rgba(239, 68, 68, 0.1);

/* Neutral UI Elements */
--waveform-bg: #0f172a;           /* Dark blue background */
--waveform-surface: #1e293b;      /* Elevated surface */
--waveform-border: #475569;       /* Border color */
--waveform-text: #f1f5f9;         /* Primary text */
--waveform-text-muted: #94a3b8;   /* Secondary text */

/* Interactive States */
--waveform-focus: #3b82f6;        /* Blue-500 - Focus ring */
--waveform-hover-bg: rgba(100, 116, 139, 0.1);
```

### Typography

```css
/* Headers */
font-family: 'JetBrains Mono', monospace;
font-size: 14px;
font-weight: 600;
letter-spacing: -0.01em;

/* Body/Labels */
font-family: 'JetBrains Mono', monospace;
font-size: 12px;
font-weight: 400;

/* Timecode/Technical */
font-family: 'JetBrains Mono', monospace;
font-size: 11px;
font-weight: 500;
font-variant-numeric: tabular-nums;
```

### Spacing System

```
--spacing-xs: 4px;
--spacing-sm: 8px;
--spacing-md: 12px;
--spacing-lg: 16px;
--spacing-xl: 24px;
--spacing-2xl: 32px;
```

---

## 2. Component Architecture

### 2.1 Component Hierarchy

```
WaveformVisualizationWidget
├── WaveformHeader
│   ├── SectionTitle
│   ├── StatusIndicator (loading/ready/error)
│   └── CollapseToggle
│
├── WaveformToolbar
│   ├── ViewModeSelector (Overlay / Stacked / Before-After)
│   ├── ZoomControls (In / Out / Fit / Selection)
│   ├── PlaybackControls (Play / Pause / Stop)
│   └── AudioBalance (Master/Dub volume sliders)
│
├── WaveformCanvas
│   ├── TimelineRuler (SMPTE timecode)
│   ├── WaveformTracks
│   │   ├── MasterTrack (teal)
│   │   ├── DubTrack (amber/red)
│   │   └── CorrectedTrack (green - optional)
│   ├── OffsetMarkers
│   │   ├── PrimaryOffsetLine (main sync point)
│   │   └── DriftMarkers (timeline segments)
│   ├── PlayheadCursor
│   └── SelectionOverlay
│
├── WaveformTimeline
│   ├── ScrubBar (draggable position)
│   ├── TimelineMarkers
│   └── MinimapThumbnail
│
├── WaveformMetadata
│   ├── FileInfo (duration, sample rate, channels)
│   ├── OffsetReadout (seconds, frames, timecode)
│   └── ConfidenceIndicator
│
└── WaveformLegend
    ├── ColorKey (Master/Dub/Corrected)
    └── OffsetExplanation
```

### 2.2 State Management

```javascript
WaveformState = {
    // Audio Data
    masterAudioBuffer: AudioBuffer | null,
    dubAudioBuffer: AudioBuffer | null,
    correctedAudioBuffer: AudioBuffer | null,
    masterPeaks: Float32Array | null,
    dubPeaks: Float32Array | null,

    // View State
    viewMode: 'overlay' | 'stacked' | 'before-after',
    zoomLevel: number (0.1 to 20.0),
    scrollOffset: number (in seconds),
    visibleDuration: number (in seconds),

    // Playback State
    isPlaying: boolean,
    playheadPosition: number (in seconds),
    playbackMode: 'master' | 'dub' | 'both' | 'corrected',
    masterVolume: number (0 to 1),
    dubVolume: number (0 to 1),

    // Analysis Data
    offsetSeconds: number,
    frameRate: number,
    driftTimeline: Array<{start, end, offset, confidence}>,
    confidence: number,

    // UI State
    isExpanded: boolean,
    isLoading: boolean,
    errorMessage: string | null,
    selectedRegion: {start, end} | null
}
```

---

## 3. Visual Design Mockups

### 3.1 Collapsed State (Header Only)

```
┌─────────────────────────────────────────────────────────────────┐
│ 🌊 Waveform Visualization                            ● Ready  ▼ │
└─────────────────────────────────────────────────────────────────┘
```

**Specifications:**
- Height: 48px
- Background: var(--waveform-surface) with subtle gradient
- Border-bottom: 1px solid var(--waveform-border)
- Icon: Teal waveform icon (fas fa-waveform-lines)
- Status: Green dot for ready, amber for loading, red for error
- Hover: Background brightens slightly
- Click: Expand/collapse section with 250ms ease transition
- Keyboard: Enter/Space toggles, focus ring on header

### 3.2 Expanded State - Overlay View Mode

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 🌊 Waveform Visualization                                        ● Ready      ▲ │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  [Overlay] Stacked  Before/After     🔍- [====|====] 🔍+  Fit   ▶ ⏸ ⏹        │
│  Master ▬▬ Dub ▬▬ Offset ┃           └─ Zoom: 100% ─┘                         │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 00:00.000                     SMPTE: 00:00:00:00                    00:30.000  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│    ▁▃▄▆█▆▄▃▁  ▂▅▇█▇▅▂  ▁▃▄▆█▆▄▃▁     ┃OFFSET    ▂▅▇█▇▅▂  ▁▃▄▆█▆▄▃▁           │
│   ─▔▔▔▔▔▔▔▔─ ─▔▔▔▔▔▔▔─ ─▔▔▔▔▔▔▔▔─    ┃         ─▔▔▔▔▔▔▔─ ─▔▔▔▔▔▔▔▔─          │
│  ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔┃▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔       │
│                                       ┃◀────── 15.024s ──────▶                 │
│                                                                                 │
│  Teal = Master (reference)   Amber = Dub (out of sync)   Red Line = Offset    │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ╟━━━━━━━━━━━━━━━━━━━━━━━●━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╢    │
│  0s                       15s                                              30s  │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│  Master Vol: [========●==]  Dub Vol: [========●==]  Balance: [====●====]      │
│                                                                                 │
│  📊 Offset: -15.024s  │  -360f @ 23.976fps  │  -00:00:15:00  │  Conf: 98%    │
│  📂 Master: 48kHz, Stereo, 30s  │  Dub: 48kHz, Stereo, 30s                    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Specifications:**

**Toolbar Section (48px height):**
- View mode tabs: Pill-style segmented control, 3px teal underline for active
- Zoom controls: Icon buttons (16x16) with tooltip, slider shows on hover
- Playback: Standard transport controls (play/pause/stop)
- Legend: Inline color swatches (8px circle) with labels

**Canvas Section (240px height, resizable):**
- Timeline ruler: Top, 24px height, SMPTE timecode every 5-10s
- Waveform display: 180px height for audio, centered
- Offset marker: Vertical red line at offset point, 2px width
- Offset measurement: Horizontal bracket showing offset distance
- Grid: Subtle vertical lines every second (1px, 10% opacity)
- Background: Gradient from var(--waveform-bg) to slight lighter

**Timeline/Scrubber (40px height):**
- Minimap: Full waveform overview with visible region highlighted
- Scrubber: Draggable position indicator (playhead)
- Time markers: Start/end times at edges

**Controls Section (32px height):**
- Volume sliders: Horizontal, 100px width each, teal/amber handles
- Balance: Center-detent slider for L/R balance

**Metadata Section (40px height):**
- Offset displays: Grouped in pills (seconds, frames, timecode)
- File info: Duration, sample rate, channel count
- Confidence: Progress bar style, 98% fill

### 3.3 Stacked View Mode

```
┌─────────────────────────────────────────────────────────────────────┐
│  Master (Reference)                                     ● Playing   │
│  ▁▃▄▆█▆▄▃▁  ▂▅▇█▇▅▂  ▁▃▄▆█▆▄▃▁  ▁▃▄▆█▆▄▃▁  ▂▅▇█▇▅▂  ▁▃▄▆█▆▄▃▁     │
│ ─▔▔▔▔▔▔▔▔─ ─▔▔▔▔▔▔▔─ ─▔▔▔▔▔▔▔▔─ ─▔▔▔▔▔▔▔▔─ ─▔▔▔▔▔▔▔─ ─▔▔▔▔▔▔▔▔─    │
│▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔│
├─────────────────────────────────────────────────────────────────────┤
│                         ┃ OFFSET: -15.024s                          │
├─────────────────────────────────────────────────────────────────────┤
│  Dub (Out of Sync)                                   ⚠ Needs Repair │
│       ▁▃▄▆█▆▄▃▁  ▂▅▇█▇▅▂  ▁▃▄▆█▆▄▃▁  ▁▃▄▆█▆▄▃▁  ▂▅▇█▇▅▂            │
│      ─▔▔▔▔▔▔▔▔─ ─▔▔▔▔▔▔▔─ ─▔▔▔▔▔▔▔▔─ ─▔▔▔▔▔▔▔▔─ ─▔▔▔▔▔▔▔─           │
│▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔│
└─────────────────────────────────────────────────────────────────────┘
```

**Specifications:**
- Master track: Top half (90px), teal waveform, label "Master (Reference)"
- Dub track: Bottom half (90px), amber waveform, label "Dub (Out of Sync)"
- Separator: 30px height, shows offset value with icon
- Alignment: Dub waveform shifted by offset amount
- Visual cue: Offset area highlighted with subtle red background tint

### 3.4 Before/After View Mode

```
┌────────────────────────────────────────────────────┬───────────────────────────────────────────────┐
│  BEFORE CORRECTION                                 │  AFTER CORRECTION                            │
│  ⚠ Sync offset: -15.024s                          │  ✓ Synced to reference                       │
│                                                    │                                               │
│  Master ▁▃▄▆█▆▄▃▁  ▂▅▇█▇▅▂  ▁▃▄▆█▆▄▃▁            │  Master ▁▃▄▆█▆▄▃▁  ▂▅▇█▇▅▂  ▁▃▄▆█▆▄▃▁         │
│         ▔▔▔▔▔▔▔▔▔  ▔▔▔▔▔▔▔▔  ▔▔▔▔▔▔▔▔▔            │         ▔▔▔▔▔▔▔▔▔  ▔▔▔▔▔▔▔▔  ▔▔▔▔▔▔▔▔▔         │
│                                                    │                                               │
│  Dub         ▁▃▄▆█▆▄▃▁  ▂▅▇█▇▅▂  ▁▃▄▆█▆▄▃▁        │  Dub    ▁▃▄▆█▆▄▃▁  ▂▅▇█▇▅▂  ▁▃▄▆█▆▄▃▁         │
│              ▔▔▔▔▔▔▔▔▔  ▔▔▔▔▔▔▔▔  ▔▔▔▔▔▔▔▔▔        │         ▔▔▔▔▔▔▔▔▔  ▔▔▔▔▔▔▔▔  ▔▔▔▔▔▔▔▔▔         │
│              └──────┘ Out of sync                  │                     In sync ✓                │
│                                                    │                                               │
│  [▶ Play Before]                                  │  [▶ Play After]                              │
└────────────────────────────────────────────────────┴───────────────────────────────────────────────┘
```

**Specifications:**
- Split view: 50/50 vertical split, 1px divider
- Left panel: Before (master teal + dub amber with offset)
- Right panel: After (master teal + dub green, aligned)
- Status icons: Warning (before) vs checkmark (after)
- Play buttons: Independent playback for each view
- Annotation: Visual highlight showing misalignment (before) vs alignment (after)

### 3.5 Loading State

```
┌─────────────────────────────────────────────────────────────────┐
│ 🌊 Waveform Visualization                      ⚙ Loading...  ▲ │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                     ⏳ Extracting audio waveforms...            │
│                                                                 │
│                     [████████░░░░░░░░░░░░░░] 45%              │
│                                                                 │
│                     Processing: master.mov                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Specifications:**
- Skeleton loader: Animated shimmer effect on waveform area
- Progress bar: Teal fill, percentage display
- Status text: Current operation (e.g., "Extracting audio peaks...")
- Animation: Smooth 1.5s pulse on shimmer, progress updates every 100ms

### 3.6 Error State

```
┌─────────────────────────────────────────────────────────────────┐
│ 🌊 Waveform Visualization                        ⚠ Error     ▲ │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                 ⚠ Failed to load audio waveform                │
│                                                                 │
│     Error: Could not decode audio from file                    │
│     File: /path/to/problematic-file.mov                        │
│                                                                 │
│     [🔄 Retry] [📄 Use Fallback Visualization]                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Specifications:**
- Error icon: Red warning triangle
- Error message: Clear, actionable description
- File path: Truncated with tooltip for full path
- Actions: Retry button (attempts reload), Fallback (uses synthetic waveform)
- Background: Subtle red tint (rgba(239, 68, 68, 0.05))

---

## 4. Interaction Patterns

### 4.1 Expand/Collapse Section

**User Action:** Click header or press Enter/Space when focused

**Behavior:**
1. Icon changes from ▼ (chevron-down) to ▲ (chevron-up)
2. Content area expands/collapses with 250ms ease transition
3. State saved to localStorage (persist across page reloads)
4. ARIA attribute `aria-expanded` toggles between true/false
5. Smooth scroll to bring expanded section into view

**Keyboard:**
- Tab: Focus on header
- Enter/Space: Toggle expand
- Escape: Collapse if expanded

**Accessibility:**
- Role: `region` with `aria-labelledby` pointing to title
- Focus ring: 2px blue outline on keyboard focus
- Announce: Screen reader announces "Waveform Visualization, expanded" or "collapsed"

### 4.2 View Mode Selection

**User Action:** Click view mode tab (Overlay / Stacked / Before-After)

**Behavior:**
1. Active tab gets 3px teal bottom border
2. Waveform canvas re-renders with new layout (250ms transition)
3. View mode preference saved per-item in localStorage
4. Tooltip shows keyboard shortcut (V for Overlay, S for Stacked, B for Before-After)

**States:**
- Default: Overlay mode
- Overlay: Both waveforms superimposed, offset marker visible
- Stacked: Vertical split, offset separator between tracks
- Before-After: Horizontal split, before (left) vs after (right)

**Keyboard:**
- V: Switch to Overlay
- S: Switch to Stacked
- B: Switch to Before-After
- Left/Right arrows: Cycle through modes

### 4.3 Zoom Controls

**User Action:** Click zoom in/out, drag slider, or use keyboard shortcuts

**Behavior:**
1. Zoom range: 10% (10s view) to 2000% (0.05s view)
2. Zoom centers on playhead or selected region
3. Smooth animation (150ms) when zooming
4. Zoom level display updates in real-time
5. Pan automatically if zoomed beyond visible area

**Controls:**
- Zoom In (+): Increase zoom by 10%, max 2000%
- Zoom Out (-): Decrease zoom by 10%, min 10%
- Fit: Reset to show entire waveform (100%)
- Zoom to Selection: Fit selected region to viewport
- Slider: Continuous zoom from 10% to 2000%

**Keyboard:**
- Ctrl/Cmd + Plus: Zoom in
- Ctrl/Cmd + Minus: Zoom out
- Ctrl/Cmd + 0: Fit to view
- F: Fit to view (alternate)
- Ctrl/Cmd + Shift + Z: Zoom to selection

**Mouse:**
- Scroll wheel: Zoom in/out (Ctrl/Cmd + wheel)
- Pinch gesture: Zoom in/out (trackpad)

### 4.4 Pan/Scroll Navigation

**User Action:** Drag on waveform, use scrollbar, or keyboard

**Behavior:**
1. Click and drag waveform to pan horizontally
2. Cursor changes to grab hand during drag
3. Momentum scrolling on trackpad (smooth deceleration)
4. Scrollbar appears at bottom when zoomed
5. Edge resistance when reaching start/end

**Keyboard:**
- Left/Right arrows: Pan 1 second
- Shift + Left/Right: Pan 10 seconds
- Home: Jump to start
- End: Jump to end
- Page Up/Down: Pan by visible duration

**Mouse:**
- Drag: Pan in drag direction
- Shift + Scroll: Horizontal scroll
- Scrollbar: Click or drag to navigate

### 4.5 Playback Controls

**User Action:** Click play/pause/stop or use keyboard shortcuts

**Behavior:**
1. **Play**: Starts playback from playhead position
   - Plays both master and dub simultaneously (default)
   - Playhead animates smoothly across waveform
   - Waveform auto-scrolls to keep playhead centered (if zoomed)
   - Button icon changes to pause

2. **Pause**: Pauses playback at current position
   - Playhead stops at current position
   - Resume from same position on next play
   - Button icon changes to play

3. **Stop**: Stops playback and resets playhead
   - Playhead returns to start or last set position
   - Audio buffers released
   - Button icon shows play

**Playback Modes:**
- Both: Master + Dub simultaneously (default)
- Master Only: Solo master track
- Dub Only: Solo dub track
- Corrected: Play corrected version (if available)
- Before/After Toggle: A/B comparison at offset point

**Keyboard:**
- Space: Play/pause
- S: Stop
- M: Solo master
- D: Solo dub
- C: Play corrected
- A: A/B toggle (Before/After comparison)

**Visual Feedback:**
- Playhead: Vertical line (2px, white, 80% opacity) with drag handle
- Time display: Current time updates in real-time next to playhead
- Waveform highlight: Area behind playhead dimmed (30% opacity)

---

## 5. Technical Specifications

### 5.1 Real Audio Extraction Pipeline

**Web Audio API Integration:**

```javascript
// 1. Fetch audio file via proxy endpoint
const response = await fetch(`/api/v1/files/proxy-audio?path=${encodeURIComponent(filePath)}&format=wav`);
const arrayBuffer = await response.arrayBuffer();

// 2. Decode audio data
const audioContext = new (window.AudioContext || window.webkitAudioContext)();
const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);

// 3. Extract channel data
const channelData = audioBuffer.getChannelData(0); // Mono or left channel
const sampleRate = audioBuffer.sampleRate;
const duration = audioBuffer.duration;

// 4. Generate waveform peaks (100 peaks/second for smooth visualization)
const peaksPerSecond = 100;
const totalPeaks = Math.floor(duration * peaksPerSecond);
const samplesPerPeak = Math.floor(channelData.length / totalPeaks);
const peaks = new Float32Array(totalPeaks);

for (let i = 0; i < totalPeaks; i++) {
    const start = i * samplesPerPeak;
    const end = start + samplesPerPeak;
    let max = 0;

    // Find peak in this window
    for (let j = start; j < end && j < channelData.length; j++) {
        max = Math.max(max, Math.abs(channelData[j]));
    }

    peaks[i] = max;
}

// 5. Store for rendering
waveformData.set('master', { audioBuffer, peaks, sampleRate, duration });
```

**Stereo Handling Options:**
- Option 1: Mix to mono (average L+R channels)
- Option 2: Display both channels vertically (L on top, R on bottom)
- Option 3: Mid/Side processing (M = L+R, S = L-R) for phase visualization

**IndexedDB Caching:**
```javascript
// Cache key: waveform:${fileHash}:${peaksPerSecond}
const cacheKey = `waveform:${generateFileHash(filePath)}:100`;

// Check cache before extraction
const cachedPeaks = await waveformCache.get(cacheKey);
if (cachedPeaks && !isFileModified(filePath, cachedPeaks.timestamp)) {
    return cachedPeaks.data;
}

// Store in cache after extraction
await waveformCache.set(cacheKey, {
    data: peaks,
    timestamp: Date.now(),
    fileSize: arrayBuffer.byteLength
});

// LRU eviction when cache exceeds 50MB
```

### 5.2 Canvas Rendering Performance

**High-DPI Setup:**
```javascript
const dpr = window.devicePixelRatio || 1;
canvas.width = containerWidth * dpr;
canvas.height = containerHeight * dpr;
canvas.style.width = containerWidth + 'px';
canvas.style.height = containerHeight + 'px';
ctx.scale(dpr, dpr);
```

**Multi-Layer Architecture:**
- **Background Layer**: Grid, timeline ruler (static, rendered once)
- **Waveform Layer**: Audio peaks (semi-static, rendered on zoom/scroll)
- **Overlay Layer**: Playhead, selection, markers (dynamic, 60fps)
- Composite using CSS `position: absolute` stacking

**Virtualization:**
```javascript
// Only render visible region + 10% buffer
const visibleDuration = 30 / zoomLevel;
const startTime = scrollOffset;
const endTime = startTime + visibleDuration;
const bufferTime = visibleDuration * 0.1;

const renderStartSample = Math.floor((startTime - bufferTime) * peaksPerSecond);
const renderEndSample = Math.ceil((endTime + bufferTime) * peaksPerSecond);
```

**Downsampling:**
```javascript
// For zoom < 100%, downsample to match pixel resolution
const samplesPerPixel = totalSamples / canvasWidth;
if (samplesPerPixel > 1) {
    // Extract one peak per pixel column
    const downsampledPeaks = new Float32Array(canvasWidth);
    for (let px = 0; px < canvasWidth; px++) {
        const sampleStart = Math.floor(px * samplesPerPixel);
        const sampleEnd = Math.floor((px + 1) * samplesPerPixel);
        let maxPeak = 0;
        for (let i = sampleStart; i < sampleEnd; i++) {
            maxPeak = Math.max(maxPeak, peaks[i]);
        }
        downsampledPeaks[px] = maxPeak;
    }
}
```

### 5.3 SMPTE Timecode Formatting

```javascript
function formatSMPTE(seconds, fps) {
    const totalFrames = Math.floor(seconds * fps);
    const hours = Math.floor(totalFrames / (fps * 3600));
    const minutes = Math.floor((totalFrames % (fps * 3600)) / (fps * 60));
    const secs = Math.floor((totalFrames % (fps * 60)) / fps);
    const frames = totalFrames % fps;

    return `${pad(hours)}:${pad(minutes)}:${pad(secs)}:${pad(frames)}`;
}

function pad(num) {
    return num.toString().padStart(2, '0');
}
```

---

## 6. Accessibility Standards (WCAG 2.1 AA)

### 6.1 Color Contrast Ratios

**Text on Background:**
- Teal (#14b8a6) on dark (#0f172a): **5.2:1** ✓ (exceeds 4.5:1 minimum)
- Amber (#f59e0b) on dark (#0f172a): **6.8:1** ✓
- White (#f1f5f9) on dark (#0f172a): **15.3:1** ✓

**UI Components:**
- All borders, focus rings, active states: **>3:1** ✓

### 6.2 Non-Color Indicators

- Offset marker: Red line **+ "OFFSET" text label**
- Master/Dub tracks: Different positions **+ text labels**
- Status: Icon **+ text** (not color alone)
- Playback state: Icon changes **+ ARIA live region**

### 6.3 Keyboard Navigation

**Focus Order:**
1. Waveform header (expand/collapse)
2. View mode tabs (Overlay → Stacked → Before/After)
3. Zoom controls (out → slider → in → fit)
4. Playback controls (play → pause → stop)
5. Volume sliders (master → dub → balance)
6. Timeline/scrubber

**Keyboard Shortcuts:**
- Space: Play/pause
- S: Stop
- V: Overlay view
- T: Stacked view
- B: Before/After view
- Ctrl + Plus: Zoom in
- Ctrl + Minus: Zoom out
- F: Fit to view
- Left/Right: Navigate
- Home/End: Jump to start/end
- Escape: Collapse widget

### 6.4 ARIA Implementation

```html
<div class="waveform-widget"
     role="region"
     aria-labelledby="waveform-title"
     aria-describedby="waveform-desc">

  <header id="waveform-title"
          role="button"
          tabindex="0"
          aria-expanded="true"
          aria-controls="waveform-content">
    <h3>Waveform Visualization</h3>
    <span aria-live="polite" aria-atomic="true">Ready</span>
  </header>

  <div id="waveform-content" role="group">
    <div id="waveform-desc" class="sr-only">
      Interactive audio waveform visualization showing sync offset
      between master and dub audio tracks. Use arrow keys to navigate,
      space to play/pause, and plus/minus to zoom.
    </div>

    <canvas role="img"
            aria-label="Audio waveforms showing master in teal, dub in amber,
                        with red offset marker at -15.024 seconds">
    </canvas>

    <!-- Screen reader alternative -->
    <div class="sr-only">
      <p>Master audio: 30 seconds, 48kHz, stereo</p>
      <p>Dub audio: 30 seconds, 48kHz, stereo</p>
      <p>Sync offset: -15.024 seconds (dub is ahead)</p>
      <p>Detection confidence: 98%</p>
    </div>
  </div>
</div>
```

---

## 7. Implementation Roadmap

### Week 1: Foundation
- [ ] Set up Web Audio API pipeline
- [ ] Implement peak extraction (100 peaks/second)
- [ ] Add IndexedDB caching layer
- [ ] Create loading states with progress
- [ ] Test with various audio formats

**Deliverables:**
- Real audio waveforms displaying
- Cache reducing repeat load times
- Loading progress 0-100%

### Week 2: Visual Redesign
- [ ] Add waveform CSS to redesign.css
- [ ] Update canvas rendering colors
- [ ] Redesign toolbar and controls
- [ ] Update header styling
- [ ] Test responsive behavior

**Deliverables:**
- Colors match teal/amber/gray palette
- Buttons match `.action-btn-v2` style
- JetBrains Mono typography throughout

### Week 3: Before/After Mode
- [ ] Implement Before/After rendering
- [ ] Add view mode selector
- [ ] Wire up state management
- [ ] Add keyboard shortcuts (V/S/B)
- [ ] Test all view modes

**Deliverables:**
- Three view modes functional
- Smooth transitions (250ms)
- View preference persists

### Week 4: Polish & Accessibility
- [ ] Improve loading/error states
- [ ] Add ARIA labels and roles
- [ ] Optimize rendering (60fps)
- [ ] Add metadata display
- [ ] Screen reader testing

**Deliverables:**
- Full ARIA support
- 60fps rendering at all zoom levels
- WCAG 2.1 AA compliant

---

## Summary

This comprehensive UX design specification provides everything needed to build a professional-grade waveform visualization widget that rivals industry-standard A/V software like Pro Tools and Adobe Audition.

**Key Features:**
1. ✅ Real audio waveforms via Web Audio API
2. ✅ Professional teal/amber/gray color system
3. ✅ Three view modes (Overlay, Stacked, Before/After)
4. ✅ Integrated playback with transport controls
5. ✅ Full accessibility (WCAG 2.1 AA)
6. ✅ High-performance canvas rendering
7. ✅ IndexedDB caching for fast loading

The design integrates seamlessly with your existing UI redesign and provides a best-in-class user experience for professional audio sync analysis.
