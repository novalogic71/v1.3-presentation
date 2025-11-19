# Dolby Atmos Support - User Guide

## Overview

The Professional Audio Sync Analyzer now supports **Dolby Atmos** audio files, allowing you to:
- Upload and analyze Atmos files (EC3, EAC3, ADM WAV)
- Compare Atmos dub files against standard audio/video masters
- Extract Atmos bed channels for detailed analysis
- Preserve original Atmos format in repair workflows

---

## Supported Formats

| Format | Extension | Description | Support Level |
|--------|-----------|-------------|---------------|
| E-AC-3 | `.ec3`, `.eac3` | Dolby Digital Plus with Atmos | ✅ Full |
| ADM WAV | `.adm`, `.wav` | Audio Definition Model BWF WAV | ✅ Full |
| IAB | `.iab` | Immersive Audio Bitstream (SMPTE ST 2098-2) | ✅ Full |
| MXF | `.mxf` | Material eXchange Format (broadcast container) | ✅ Full |
| MP4/MOV with Atmos | `.mp4`, `.mov` | Container with Atmos audio track | ✅ Full |
| TrueHD | `.thd`, `.mlp` | TrueHD lossless with Atmos | ⚠️ Partial |

---

## Quick Start

### 1. Upload an Atmos File

The system automatically detects Atmos files based on:
- File extension (`.ec3`, `.eac3`, `.adm`)
- Audio codec in container files (MP4/MOV)
- ADM metadata in BWF WAV files

**Example**:
```bash
# Upload via CLI
curl -F "file=@my_atmos_file.ec3" http://localhost:8000/api/v1/files/upload

# Upload via API
POST /api/v1/files/upload
Content-Type: multipart/form-data
{
  "file": <atmos_file.ec3>
}
```

**Response**:
```json
{
  "success": true,
  "file_id": "file_abc123",
  "file_info": {
    "name": "atmos_dub.ec3",
    "type": "atmos",
    "size": 45678901,
    "extension": ".ec3",
    "duration_seconds": 120.5,
    "atmos_metadata": {
      "codec": "eac3",
      "bed_configuration": "7.1.2",
      "channels": 10,
      "channel_layout": "7.1.2(FL FR FC LFE SL SR BL BR TpFL TpFR)",
      "sample_rate": 48000,
      "bit_rate": 768000,
      "object_count": 48,
      "is_adm_wav": false
    }
  }
}
```

### 2. Analyze Master vs Atmos Dub

Compare a standard master file (audio or video) against an Atmos dub.

**Example**:
```bash
POST /api/v1/analysis/sync
Content-Type: application/json
{
  "master_file": "/mnt/data/masters/show_ep101_master.mov",
  "dub_file": "/mnt/data/dubs/show_ep101_atmos.ec3",
  "methods": ["mfcc", "onset"],
  "channel_strategy": "atmos_bed_mono",
  "sample_rate": 22050
}
```

**What Happens**:
1. System detects Atmos file automatically
2. Extracts Atmos bed (7.1 base channels, objects ignored)
3. Downmixes bed to mono for sync analysis
4. Runs MFCC and onset detection
5. Returns sync offset and confidence

**Response**:
```json
{
  "analysis_id": "analysis_20251119_143052",
  "status": "completed",
  "consensus_offset": {
    "offset_seconds": -2.456,
    "offset_samples": -54032,
    "offset_frames": {
      "23.976": -58.9,
      "24.0": -58.9
    },
    "confidence": 0.94
  },
  "method_results": [
    {
      "method": "mfcc",
      "offset": {"offset_seconds": -2.456, "confidence": 0.96},
      "processing_time": 3.8
    },
    {
      "method": "onset",
      "offset": {"offset_seconds": -2.460, "confidence": 0.92},
      "processing_time": 4.2
    }
  ],
  "overall_confidence": 0.94,
  "sync_status": "SYNC CORRECTION NEEDED",
  "recommendations": [
    "Dub audio is 2.46 seconds behind master",
    "High confidence in detection (94%)",
    "Atmos bed comparison used (objects ignored)"
  ]
}
```

---

## Channel Strategies for Atmos

When analyzing Atmos files, you can choose different extraction strategies:

### `atmos_bed_mono` (Recommended for Sync Analysis)
- Extracts Atmos 7.1 bed and downmixes to mono
- Fastest processing
- Best for general sync detection
- Objects are ignored

**Use case**: Standard sync analysis between Master and Atmos Dub

### `atmos_bed_stereo`
- Extracts Atmos bed and downmixes to stereo
- Preserves left/right separation
- Good for spatial analysis
- Objects are ignored

**Use case**: Spatial comparison or stereo master vs Atmos dub

### `atmos_bed_channels`
- Extracts individual bed channels (FL, FR, FC, LFE, SL, SR, BL, BR, ...)
- Per-channel sync analysis
- Most detailed comparison
- Objects are ignored

**Use case**: Per-channel offset detection or channel-specific issues

---

## Batch Processing with Atmos

### CSV Format

```csv
master,dub,methods,ai_model,description
/mnt/data/masters/ep101.mov,/mnt/data/dubs/ep101_atmos.ec3,mfcc|onset,wav2vec2,Episode 101
/mnt/data/masters/ep102.mov,/mnt/data/dubs/ep102_atmos.ec3,mfcc,,"Episode 102"
/mnt/data/masters/ep103.mov,/mnt/data/dubs/ep103_adm.wav,mfcc|spectral,,"Episode 103 ADM"
```

### Upload Batch

```bash
POST /api/v1/batch/upload
Content-Type: multipart/form-data
{
  "file": <batch.csv>,
  "description": "Atmos batch for Season 1"
}
```

### Start Processing

```bash
POST /api/v1/batch/start/{batch_id}
Content-Type: application/json
{
  "parallel_jobs": 2,
  "priority": "normal"
}
```

**Atmos Conversion**:
- Standalone Atmos files automatically converted to MP4 with black video
- Conversion happens once per file (cached)
- Original files preserved for repair workflow

---

## Atmos Metadata Extraction

### Get Detailed Atmos Metadata

```bash
GET /api/v1/files/probe?path=/mnt/data/dubs/atmos_file.ec3
```

**Response**:
```json
{
  "file_path": "/mnt/data/dubs/atmos_file.ec3",
  "duration": 120.5,
  "audio_streams": [
    {
      "codec": "eac3",
      "channels": 10,
      "channel_layout": "7.1.2(FL FR FC LFE SL SR BL BR TpFL TpFR)",
      "sample_rate": 48000,
      "bit_rate": 768000
    }
  ],
  "atmos_metadata": {
    "codec": "eac3",
    "bed_configuration": "7.1.2",
    "channels": 10,
    "object_count": 48,
    "max_objects": 128,
    "is_adm_wav": false
  }
}
```

---

## Repair Workflow with Atmos

### Current Status
⚠️ **Coming Soon** - Atmos preservation in repair workflow (Step 8)

### Planned Workflow:
1. Detect sync offset in Atmos file
2. Extract original Atmos bitstream
3. Apply time offset to audio
4. Re-mux with original Atmos format
5. Preserve all metadata (bed config, objects, etc.)

**Preservation Goals**:
- Keep original codec (EC3/EAC3/TrueHD)
- Maintain object audio
- Preserve Atmos metadata atoms
- No quality loss

---

## Technical Details

### Atmos Bed Configurations

The system supports all standard Atmos bed configurations:

| Configuration | Channels | Layout | Description |
|---------------|----------|--------|-------------|
| 7.1 | 8 | FL FR FC LFE SL SR BL BR | Standard surround |
| 7.1.2 | 10 | + TpFL TpFR | 2 height channels |
| 7.1.4 | 12 | + TpFL TpFR TpBL TpBR | 4 height channels |
| 9.1.6 | 16 | + FLC FRC TpSL TpSR | Extended bed |

### Format-Specific Details

#### IAB (Immersive Audio Bitstream)
- **Standard**: SMPTE ST 2098-2
- **Type**: Object-based audio format for cinema and broadcast
- **Processing**: Converted to PCM for analysis, encoded to AAC/EAC3 for MP4
- **Use Case**: Professional cinema mastering, broadcast deliverables
- **Detection**: File extension `.iab` or codec detection via ffprobe
- **Note**: IAB metadata is preserved where possible but may be simplified for sync analysis

#### MXF (Material eXchange Format)
- **Standard**: SMPTE 377M
- **Type**: Professional broadcast container format
- **Processing**: Audio track extracted (codec preserved), black video added if needed
- **Use Case**: Broadcast workflows, professional post-production
- **Detection**: File extension `.mxf` and container format validation
- **Note**: MXF may already contain video; audio is extracted and re-muxed with black video if needed

#### ADM WAV (Audio Definition Model)
- **Standard**: ITU-R BS.2076
- **Type**: PCM audio with object-based metadata in BWF chunks
- **Processing**: Encoded to EAC3 for Atmos compatibility (metadata simplified)
- **Use Case**: Object-based audio production and mastering
- **Detection**: `.adm` extension or BWF chunk analysis in `.wav` files

#### EC3/EAC3 (E-AC-3)
- **Standard**: ETSI TS 102 366 (Dolby Digital Plus)
- **Type**: Compressed bitstream with Atmos metadata
- **Processing**: Bitstream copied directly to MP4 (no re-encoding)
- **Use Case**: Streaming platforms, OTT delivery
- **Detection**: `.ec3` or `.eac3` extension, codec verification
- **Note**: This is the most common Atmos delivery format

### Object Audio Handling

**Current Implementation**:
- Objects are **ignored** during sync analysis
- Only the bed (base channels) is compared
- This ensures consistent comparison between versions

**Rationale**:
- Object placement may differ between master and dub
- Objects are dynamic and may not align temporally
- Bed provides stable reference for sync detection

**Future Enhancement**:
- Object stem extraction (if needed)
- Per-object timeline analysis
- Object-aware sync detection

### Sample Rate Handling

- **Analysis**: Extracts to 22050 Hz (system standard)
- **Bed Extraction**: Preserves 48000 Hz for quality
- **Conversion**: Configurable per extraction method

### Performance

**Typical Processing Times** (for 10-minute file):

| Operation | Time | Notes |
|-----------|------|-------|
| Atmos Detection | < 1s | Fast codec check |
| Bed Extraction (Mono) | 5-10s | FFmpeg decoding |
| Bed Extraction (Stereo) | 6-12s | Includes downmix |
| Per-Channel Extraction | 15-25s | All 8-16 channels |
| Sync Analysis (MFCC) | 3-8s | Standard analysis |
| Total (Mono + MFCC) | 8-18s | End-to-end |

**Optimization Tips**:
- Use `atmos_bed_mono` for fastest processing
- Enable GPU for AI methods
- Process batches in parallel (2-4 jobs)

---

## Configuration

### Environment Variables

Add to `.env` file:

```bash
# Dolby Atmos Settings
ATMOS_TEMP_DIR=./temp/atmos
ATMOS_AUTO_CONVERT=true
ATMOS_PRESERVE_ORIGINAL=true
ATMOS_DEFAULT_FPS=24.0
ATMOS_DEFAULT_RESOLUTION=1920x1080

# Path to dlb_mp4base tools (optional)
DLB_MP4BASE_PATH=/usr/local/bin

# Allowed extensions (includes Atmos)
ALLOWED_EXTENSIONS=[".wav", ".mp3", ".ec3", ".eac3", ".adm", ".iab", ".mxf", ...]
```

### Configuration Options

| Setting | Default | Description |
|---------|---------|-------------|
| `ATMOS_TEMP_DIR` | `./temp/atmos` | Temp directory for conversions |
| `ATMOS_AUTO_CONVERT` | `true` | Auto-convert standalone Atmos to MP4 |
| `ATMOS_PRESERVE_ORIGINAL` | `true` | Keep original file after conversion |
| `ATMOS_DEFAULT_FPS` | `24.0` | Frame rate for black video |
| `ATMOS_DEFAULT_RESOLUTION` | `1920x1080` | Resolution for black video |

---

## Troubleshooting

### Issue: "File is not a recognized Atmos format"

**Cause**: File may not have proper Atmos codec or metadata

**Solutions**:
1. Check file extension (`.ec3`, `.eac3`, `.adm`, `.iab`, `.mxf`)
2. Verify codec using: `ffprobe -v error -show_streams <file>`
3. Ensure file has valid Atmos bitstream
4. For MXF files, verify audio track is Atmos-compatible
5. For IAB files, ensure SMPTE ST 2098-2 compliance

### Issue: "No multichannel bed found in Atmos file"

**Cause**: Atmos file may have mono/stereo only (not a full Atmos file)

**Solutions**:
1. Verify file is true Atmos (not just EC3)
2. Check channel count: `ffprobe -show_streams <file>`
3. Use standard analysis if not multi-channel

### Issue: Slow processing on large Atmos files

**Cause**: Multi-channel extraction is CPU-intensive

**Solutions**:
1. Use `atmos_bed_mono` instead of `atmos_bed_channels`
2. Enable GPU for AI methods
3. Process batches with fewer parallel jobs
4. Ensure sufficient disk space in `ATMOS_TEMP_DIR`

### Issue: "FFmpeg failed to extract Atmos bed"

**Cause**: Unsupported codec or corrupted file

**Solutions**:
1. Update FFmpeg to latest version: `ffmpeg -version`
2. Check if FFmpeg has EC3/EAC3 support
3. Test file with: `ffmpeg -i <file> -f null -`
4. Try converting file to standard format first

---

## API Reference

### Atmos-Specific Endpoints

#### Get Atmos Metadata
```
GET /api/v1/files/atmos-metadata?path=<file_path>
```

Returns detailed Atmos metadata including bed config, object count, etc.

#### Convert Atmos to MP4
```
POST /api/v1/files/convert-atmos
{
  "atmos_path": "/path/to/atmos.ec3",
  "fps": 24.0,
  "resolution": "1920x1080"
}
```

Manually trigger Atmos to MP4 conversion.

---

## Examples

### Example 1: Basic Atmos Analysis

```python
import requests

# Upload Atmos file
files = {'file': open('atmos_dub.ec3', 'rb')}
response = requests.post(
    'http://localhost:8000/api/v1/files/upload',
    files=files
)
atmos_file = response.json()['file_info']

# Analyze vs master
analysis = requests.post(
    'http://localhost:8000/api/v1/analysis/sync',
    json={
        'master_file': '/mnt/data/master.mov',
        'dub_file': atmos_file['path'],
        'methods': ['mfcc'],
        'channel_strategy': 'atmos_bed_mono'
    }
)

print(f"Offset: {analysis.json()['consensus_offset']['offset_seconds']}s")
print(f"Confidence: {analysis.json()['overall_confidence']}")
```

### Example 2: Batch Atmos Processing

```python
import requests

# Upload CSV
files = {'file': open('atmos_batch.csv', 'rb')}
batch = requests.post(
    'http://localhost:8000/api/v1/batch/upload',
    files=files,
    data={'description': 'Season 1 Atmos batch'}
)

batch_id = batch.json()['batch_id']

# Start processing
requests.post(
    f'http://localhost:8000/api/v1/batch/start/{batch_id}',
    json={'parallel_jobs': 2}
)

# Poll status
while True:
    status = requests.get(
        f'http://localhost:8000/api/v1/batch/status/{batch_id}'
    ).json()

    print(f"Progress: {status['progress']}%")

    if status['status'] == 'completed':
        break

    time.sleep(5)

# Get results
results = requests.get(
    f'http://localhost:8000/api/v1/batch/results/{batch_id}'
).json()

print(f"Completed: {results['summary']['items_completed']}")
print(f"Average Confidence: {results['summary']['average_confidence']}")
```

### Example 3: Extract Atmos Metadata

```python
import requests

response = requests.get(
    'http://localhost:8000/api/v1/files/probe',
    params={'path': '/mnt/data/atmos_file.ec3'}
)

metadata = response.json()['atmos_metadata']

print(f"Bed Config: {metadata['bed_configuration']}")
print(f"Channels: {metadata['channels']}")
print(f"Objects: {metadata['object_count']}")
print(f"Codec: {metadata['codec']}")
```

---

## Roadmap

### ✅ Completed (Steps 1-6)
- [x] dlb_mp4base installation and setup
- [x] Atmos metadata extraction
- [x] Black video generation
- [x] Atmos to MP4 conversion
- [x] Bed extraction (mono/stereo/per-channel)
- [x] Sync analysis API models
- [x] Automatic Atmos detection

### 🚧 In Progress
- [ ] Batch processing UI updates (Step 7)
- [ ] Atmos indicators in file browser
- [ ] Conversion progress display

### 📋 Planned
- [ ] Repair workflow with Atmos preservation (Step 8)
- [ ] Re-mux with original format
- [ ] Metadata preservation

### 🔮 Future Enhancements
- [ ] Object audio extraction
- [ ] Per-object analysis
- [ ] Dolby Vision metadata support
- [ ] Advanced MP4 atom manipulation

---

## Support

### Documentation
- Full implementation details: `ATMOS_IMPLEMENTATION_SUMMARY.md`
- System architecture: `DIRECTORY_STRUCTURE.md`
- API reference: `/api/v1/docs`

### Issues
Report bugs or request features:
- GitHub Issues: (your repo URL)
- Email: (your support email)

### Community
- Discord: (your Discord link)
- Forum: (your forum link)

---

## Credits

**Implementation**: Claude Code + Professional Audio Sync Analyzer Team
**Dolby Atmos**: Dolby Laboratories
**dlb_mp4base**: https://github.com/DolbyLaboratories/dlb_mp4base
**License**: MIT (dlb_mp4base), Your License (system)

---

**Version**: 1.0
**Last Updated**: 2025-11-19
**Branch**: `feature/atmos-support`
