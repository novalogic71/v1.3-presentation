#!/bin/bash
# EBU EAR Renderer - Mixdown ADM BW64 files to various speaker layouts
#
# Usage:
#   ./ear_render.sh <input_adm.wav> <output.wav> <layout>
#
# Layouts:
#   0+2+0  - Stereo (2 channels)
#   0+5+0  - 5.1 Surround (6 channels)
#   0+7+0  - 7.1 Surround (8 channels)
#   2+5+0  - 5.1.2 (8 channels)
#   4+5+0  - 5.1.4 (10 channels)
#   4+5+1  - 5.1.4+1 (11 channels)
#   3+7+0  - 7.0.3 (10 channels)
#   4+7+0  - 7.1.4 (12 channels)
#   4+9+0  - 9.1.4 (14 channels)
#   9+10+3 - 22.2 (24 channels)
#
# Examples:
#   # Render ADM to 5.1:
#   ./ear_render.sh input_adm.wav output_5_1.wav 0+5+0
#
#   # Render ADM to stereo:
#   ./ear_render.sh input_adm.wav output_stereo.wav 0+2+0
#
#   # Render ADM to 7.1.4 (Atmos home):
#   ./ear_render.sh input_adm.wav output_714.wav 4+7+0

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check arguments
if [ "$#" -lt 3 ]; then
    echo -e "${YELLOW}EBU EAR Renderer - ADM BW64 Mixdown Tool${NC}"
    echo ""
    echo "Usage: $0 <input_adm.wav> <output.wav> <layout>"
    echo ""
    echo "Layouts:"
    echo "  0+2+0  - Stereo (2 channels)"
    echo "  0+5+0  - 5.1 Surround (6 channels)"
    echo "  0+7+0  - 7.1 Surround (8 channels)"
    echo "  2+5+0  - 5.1.2 (8 channels)"
    echo "  4+5+0  - 5.1.4 (10 channels)"
    echo "  4+7+0  - 7.1.4 (12 channels)"
    echo "  9+10+3 - 22.2 (24 channels)"
    echo ""
    echo "Examples:"
    echo "  $0 /path/to/adm_input.wav /path/to/stereo_output.wav 0+2+0"
    echo "  $0 /path/to/adm_input.wav /path/to/5.1_output.wav 0+5+0"
    exit 1
fi

INPUT_FILE="$1"
OUTPUT_FILE="$2"
LAYOUT="$3"

# Validate input file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo -e "${RED}Error: Input file not found: $INPUT_FILE${NC}"
    exit 1
fi

# Get absolute paths
INPUT_ABS=$(realpath "$INPUT_FILE")
OUTPUT_DIR=$(dirname "$(realpath -m "$OUTPUT_FILE")")
OUTPUT_NAME=$(basename "$OUTPUT_FILE")

# Create output directory if needed
mkdir -p "$OUTPUT_DIR"

echo -e "${GREEN}=== EBU EAR Renderer ===${NC}"
echo -e "Input:  ${INPUT_ABS}"
echo -e "Output: ${OUTPUT_DIR}/${OUTPUT_NAME}"
echo -e "Layout: ${LAYOUT}"
echo ""

# Run the renderer via Docker
echo -e "${YELLOW}Rendering...${NC}"
docker run --rm \
    -v "$(dirname "$INPUT_ABS"):/input:ro" \
    -v "${OUTPUT_DIR}:/output" \
    ebu-ear:latest \
    -s "$LAYOUT" \
    --enable-block-duration-fix \
    "/input/$(basename "$INPUT_ABS")" \
    "/output/${OUTPUT_NAME}"

# Check result
if [ -f "${OUTPUT_DIR}/${OUTPUT_NAME}" ]; then
    echo ""
    echo -e "${GREEN}✓ Success!${NC}"
    echo -e "Output file: ${OUTPUT_DIR}/${OUTPUT_NAME}"
    
    # Show file info if ffprobe is available
    if command -v ffprobe &> /dev/null; then
        echo ""
        echo "File info:"
        ffprobe -hide_banner -i "${OUTPUT_DIR}/${OUTPUT_NAME}" 2>&1 | grep -E "Stream|Duration" || true
    fi
else
    echo -e "${RED}✗ Rendering failed${NC}"
    exit 1
fi

