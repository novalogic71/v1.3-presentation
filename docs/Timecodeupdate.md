# Offset Display Update - Timecode Format

## Goal
Change offset display from seconds-based to timecode-based format for editor-friendly output.

**Current format:**
```
+15.024s (-360f @ 23.976fps)
```

**New format:**
```
Timecode Offset: 00:00:15:00 (-360f @ 23.976fps)
```

---

## 1. Add Timecode Formatter Function

Add this helper function to `web_ui/app.js` (near other format functions ~line 1570):

```javascript
formatTimecode(seconds, fps = 23.976) {
    /**
     * Convert seconds to SMPTE timecode format HH:MM:SS:FF
     */
    const sign = seconds < 0 ? '-' : '';
    const absSeconds = Math.abs(seconds);

    const hours = Math.floor(absSeconds / 3600);
    const minutes = Math.floor((absSeconds % 3600) / 60);
    const secs = Math.floor(absSeconds % 60);
    const frames = Math.round((absSeconds % 1) * fps);

    return `${sign}${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}:${frames.toString().padStart(2, '0')}`;
}
```

---

## 2. Files to Update

### web_ui/app.js

| Line | Current | New |
|------|---------|-----|
| 1619 | `` `${frameSign}${frames}f @ ${defaultFps}fps` `` | `` `${this.formatTimecode(offsetSeconds, defaultFps)} (${frameSign}${frames}f @ ${defaultFps}fps)` `` |
| 2052 | `this.formatOffsetDisplay(item.result.offset_seconds, true, fps)` | Update `formatOffsetDisplay` to use timecode |
| 2204 | `` `${(offsetSeconds * itemFps).toFixed(0)} frames @ ${itemFps}fps` `` | Use timecode format |
| 3124 | `` `${result.offset_seconds.toFixed(3)}s (${frameSign}${framesDetectedRec}f @ ${itemFps}fps)` `` | Use timecode format |

### web_ui/qc-interface.js

| Line | Current | New |
|------|---------|-----|
| 364 | `` `${sign}${offset.toFixed(3)}s (${frameSign}${frames}f @ ${fps}fps)` `` | `` `${formatTimecode(offset, fps)} (${frameSign}${frames}f @ ${fps}fps)` `` |
| 590 | Same pattern | Use timecode |
| 616 | Same pattern | Use timecode |
| 724 | Same pattern | Use timecode |

### web_ui/repair-preview-interface.js

| Line | Current | New |
|------|---------|-----|
| 387 | `` `Offset: ${...}s (${frameSign}${frames}f @ ${fps}fps)` `` | `` `Timecode Offset: ${formatTimecode(...)} (${frameSign}${frames}f @ ${fps}fps)` `` |
| 591 | Same pattern | Use timecode |

---

## 3. Example Conversion

```javascript
// Input
offsetSeconds = 15.024
fps = 23.976

// Calculation
frames = Math.round(15.024 * 23.976) = 360
timecode = "00:00:15:00"  // 15 seconds, frame 0 (360.24 rounds to frame 0 of second 15)

// Output
"Timecode Offset: 00:00:15:00 (-360f @ 23.976fps)"
```

---

## 4. Drop-Frame Timecode (Optional)

For 23.976/29.97 fps, you may want drop-frame notation (`;` separator):
```
00:00:15;00  (drop-frame)
00:00:15:00  (non-drop-frame)
```

Standard practice:
- 23.976 fps → non-drop `:`
- 29.97 fps → drop-frame `;`
- 24/25/30 fps → non-drop `:`

---

## 5. Quick Reference

| Seconds | 23.976 fps | 24 fps | 29.97 fps |
|---------|------------|--------|-----------|
| 15.024s | 00:00:15:00 (360f) | 00:00:15:00 (360f) | 00:00:15:00 (450f) |
| 1.000s  | 00:00:01:00 (24f) | 00:00:01:00 (24f) | 00:00:01:00 (30f) |
| 0.042s  | 00:00:00:01 (1f) | 00:00:00:01 (1f) | 00:00:00:01 (1f) |