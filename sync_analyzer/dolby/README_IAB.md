# IAB (Immersive Audio Bitstream) Support

This module adds Dolby IAB handling for MXF and .iab assets by wrapping a Dolby renderer (or Atmos Conversion Tool) to produce PCM WAV for the sync analyzer.

## Required Binaries
- `iab_renderer` (Dolby IAB renderer) **or** `cmdline_atmos_conversion_tool` (Dolby Atmos Conversion Tool v2.x)

Place the binary in `sync_analyzer/dolby/bin/` or ensure it is on `PATH`. You can also point to an explicit location via environment variable:
- `IAB_IAB_RENDERER_PATH` (works for either renderer name)
- `ATMOS_CONVERSION_TOOL_HOME` pointing to the unpacked `dolby-atmos-conversion-tool-*/` directory (auto-detects the binary under `bin/`)

If `cmdline_atmos_conversion_tool` is present, the wrapper will use it to generate a WAV (via `-f wav`) and then downmix/resample with ffmpeg to the requested channel count and sample rate.

For analysis runs, IAB assets are converted to an ADM-style WAV via the Atmos Conversion Tool first, then processed through the existing ADM WAV pipeline before sync analysis.

## Configuration
Defaults live in `sync_analyzer/dolby/iab_config.json`. Command arguments are templated; adjust them to match your renderer build if flags differ. Example:
```json
{
  "iab_renderer": {
    "binary_name": "iab_renderer",
    "args": ["-i", "{input}", "-o", "{output}", "-sr", "{sample_rate}", "-ch", "{channels}"]
  }
}
```

## Head-only renders for sync checks
Set `IAB_HEAD_DURATION_SECONDS` (e.g., `300` or `600`) to have the pipeline render only the first N seconds via the conversion tool (default is 300 seconds / 5 minutes). This speeds up sync validation on long MXFs while preserving head build timing.

## Usage
The sync pipeline automatically uses the IAB path for `.iab` files and MXF files detected as IAB:
```python
from sync_analyzer.dolby.iab_wrapper import IabProcessor

iab = IabProcessor()
if iab.is_available():
    iab.extract_and_render("/path/to/input.mxf", "/tmp/out.wav", sample_rate=48000, channels=2)
```

## Docker Notes
When building the FastAPI image, copy your Dolby binaries into the image:
```dockerfile
# After COPY . .
RUN if [ -f sync_analyzer/dolby/bin/iab_renderer ]; then \
        cp sync_analyzer/dolby/bin/iab_renderer /usr/local/bin/ && \
        chmod +x /usr/local/bin/iab_renderer; \
    elif [ -f sync_analyzer/dolby/bin/cmdline_atmos_conversion_tool ]; then \
        cp sync_analyzer/dolby/bin/cmdline_atmos_conversion_tool /usr/local/bin/ && \
        chmod +x /usr/local/bin/cmdline_atmos_conversion_tool; \
    else \
        echo \"IAB renderer not present - skipping\"; \
    fi
```

## Troubleshooting
- If `is_available()` is `False`, verify binary locations and execution permissions.
- If extraction succeeds but no WAV is produced, update `iab_config.json` with the correct renderer flags.
- The fallback path raises a clear error when Dolby tools are missing to avoid silent failures.
