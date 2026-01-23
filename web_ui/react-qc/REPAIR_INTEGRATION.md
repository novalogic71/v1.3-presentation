# FFmpeg Repair Integration

This document describes the FFmpeg-based repair system integrated into the React Repair Interface for the Sync-Dub application.

## Overview

The repair system allows users to apply audio offset corrections to dub files using FFmpeg. It supports two modes:

1. **Standard Mode** - Single offset applied to all audio channels
2. **Componentized Mode** - Per-channel offsets for multi-track audio files

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           REPAIR WORKFLOW                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │  Analysis   │ →  │  Batch      │ →  │   Repair    │ →  │   FFmpeg    │  │
│  │  (Detect    │    │  Queue      │    │   Editor    │    │   Backend   │  │
│  │   Offset)   │    │  (Review)   │    │  (Preview)  │    │  (Apply)    │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│                                                                              │
│  User clicks       User reviews       User previews       FFmpeg applies    │
│  "Analyze"         results and        waveforms and       offset correction │
│                    clicks "Repair"    adjusts if needed   to source file    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## API Endpoints

### Standard Repair

Applies a single offset to all audio streams in the file.

**Endpoint:** `POST /api/v1/repair/standard`

**Request Body:**
```json
{
  "file_path": "/mnt/data/path/to/dub.mxf",
  "offset_seconds": 89.068,
  "output_path": "/mnt/data/path/to/dub_repaired.mxf",
  "keep_duration": true
}
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_path` | string | Yes | Absolute path to the dub file |
| `offset_seconds` | float | Yes | Offset in seconds (positive = delay, negative = trim) |
| `output_path` | string | No | Output file path (defaults to `{filename}_repaired.{ext}`) |
| `keep_duration` | bool | No | Pad/trim to maintain original duration (default: true) |

**Response:**
```json
{
  "success": true,
  "output_file": "/mnt/data/path/to/dub_repaired.mxf",
  "output_size": 1234567890,
  "offset_applied": 89.068,
  "keep_duration": true
}
```

### Per-Channel Repair

Applies different offsets to each audio channel/stream. Used for componentized analysis results.

**Endpoint:** `POST /api/v1/repair/per-channel`

**Request Body:**
```json
{
  "file_path": "/mnt/data/path/to/dub.mxf",
  "per_channel_results": {
    "a0": { "offset_seconds": 89.068 },
    "a1": { "offset_seconds": 89.100 },
    "a2": { "offset_seconds": 89.050 },
    "a3": { "offset_seconds": 89.068 }
  },
  "output_path": "/mnt/data/path/to/dub_perch_repaired.mxf",
  "keep_duration": true
}
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_path` | string | Yes | Absolute path to the dub file |
| `per_channel_results` | object | Yes | Map of channel names to offset objects |
| `output_path` | string | No | Output file path (defaults to `{filename}_perch_repaired.{ext}`) |
| `keep_duration` | bool | No | Pad/trim to maintain original duration (default: true) |

**Response:**
```json
{
  "success": true,
  "output_file": "/mnt/data/path/to/dub_perch_repaired.mxf",
  "output_size": 1234567890,
  "keep_duration": true
}
```

## Frontend Components

### RepairModal.tsx

The main repair editor component with full DAW-style editing capabilities:

- **Waveform Display** - Visual representation of master and dub tracks
- **Transport Controls** - Play, pause, stop, rewind, fast-forward
- **Track Controls** - Volume, mute, solo per track
- **Editing Tools** - Split clips, undo, drag to move/trim
- **FFmpeg Integration** - "Apply Repair" button triggers backend repair

### Key Functions

```typescript
// Apply FFmpeg repair with adjusted offsets from track positions
const handleApplyRepair = useCallback(async () => {
  if (isPerChannelMode(syncData)) {
    // Componentized repair - extract per-channel offsets from tracks
    const adjustedOffsets = calculateAdjustedOffsets(tracks, ...);
    await applyPerChannelRepair(syncData.dubPath, adjustedOffsets, ...);
  } else {
    // Standard repair - use dub track position
    const offset = tracks[1]?.clips?.[0]?.startSample / sampleRate;
    await applyStandardRepair(syncData.dubPath, offset, ...);
  }
}, [syncData, tracks]);
```

### repairApi.ts Service

API client functions for calling the backend:

```typescript
// Standard single-offset repair
export async function applyStandardRepair(
  filePath: string,
  offsetSeconds: number,
  outputPath?: string,
  keepDuration: boolean = true
): Promise<RepairResponse>

// Per-channel componentized repair
export async function applyPerChannelRepair(
  filePath: string,
  perChannelResults: PerChannelResults,
  outputPath?: string,
  keepDuration: boolean = true
): Promise<RepairResponse>

// Extract offsets from waveform editor track positions
export function calculateAdjustedOffsets(
  tracks: Array<{ name: string; clips: Array<{ startTime: number }> }>,
  originalOffsets: PerChannelResults | null,
  detectedOffset: number
): PerChannelResults
```

## FFmpeg Filter Logic

### Positive Offset (Add Delay)

When the offset is positive, audio is delayed by adding silence at the start:

```bash
ffmpeg -i input.mxf -af "adelay=89068|89068" output.mxf
```

### Negative Offset (Trim Start)

When the offset is negative, audio is trimmed from the start:

```bash
ffmpeg -i input.mxf -af "atrim=start=1.5,asetpts=PTS-STARTPTS" output.mxf
```

### Duration Preservation

When `keep_duration` is true, the output is padded/trimmed to match the original:

```bash
ffmpeg -i input.mxf -af "adelay=89068|89068,apad=whole_dur=1,atrim=duration=689.068" output.mxf
```

## User Interface

### FFmpeg Repair Settings Dialog

When the user clicks "Apply Repair (FFmpeg)", a dialog appears with:

1. **Mode Display** - Shows whether Standard or Per-Channel mode is detected
2. **Source Path** - Full path to the input dub file
3. **Output Path** - Customizable output location (optional)
4. **Keep Duration** - Checkbox to maintain original file duration
5. **Apply/Cancel** - Action buttons

### Status Feedback

After repair:
- **Success** - Green status bar with output file path and size
- **Error** - Red status bar with error message

## File Structure

```
sync-dub/
├── web_ui/
│   └── react-qc/
│       └── src/
│           ├── components/
│           │   ├── RepairModal.tsx      # Main repair editor
│           │   └── RepairModal.css      # Styles including dialog
│           ├── services/
│           │   └── repairApi.ts         # API client functions
│           └── types.ts                 # TypeScript interfaces
└── fastapi_app/
    └── app/
        └── api/
            └── v1/
                └── endpoints/
                    └── repair.py        # FFmpeg repair endpoints
```

## Usage Example

### From the Batch Queue

1. Complete an analysis (standard or componentized)
2. Click the **Repair** button (wrench icon) on a completed job
3. For componentized jobs, select which component to repair
4. Preview the waveforms in the Repair Editor
5. Optionally adjust track positions by dragging
6. Click **"Apply Repair (FFmpeg)"**
7. Configure output settings in the dialog
8. Click **"Apply Repair"** to execute

### Programmatic Access

```javascript
// Open repair interface from vanilla JS
window.openRepairInterface({
  masterFile: 'master.mp4',
  dubFile: 'dub.mxf',
  masterUrl: '/api/v1/files/proxy-audio?path=...',
  dubUrl: '/api/v1/files/proxy-audio?path=...',
  masterPath: '/mnt/data/path/to/master.mp4',
  dubPath: '/mnt/data/path/to/dub.mxf',
  detectedOffset: 89.068,
  confidence: 0.70,
  frameRate: 23.976
});
```

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| "Invalid or missing file_path" | File doesn't exist or outside mount | Verify file path is valid |
| "No audio streams found" | Input file has no audio | Check input file format |
| "ffmpeg failed" | FFmpeg process error | Check FFmpeg logs for details |
| "Rate limit exceeded" | Too many requests | Wait and retry |

## Dependencies

- **Frontend**: React, @waveform-playlist/browser, @dnd-kit/core
- **Backend**: FastAPI, FFmpeg (installed in container)
- **Audio Formats**: Supports MXF, MOV, MP4, WAV, and other FFmpeg-compatible formats

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-23 | Initial FFmpeg repair integration |
