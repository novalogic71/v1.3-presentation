#!/usr/bin/env python3
"""
Test script to verify Atmos file detection
Run this to test if your ADM WAV file is being detected correctly
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from sync_analyzer.core.audio_channels import is_atmos_file
from sync_analyzer.dolby.atmos_metadata import extract_atmos_metadata

def test_atmos_detection(file_path):
    """Test Atmos file detection"""
    print("="*80)
    print(f"Testing Atmos detection for: {file_path}")
    print("="*80)

    # Test 1: Extract metadata
    print("\n[1] Extracting Atmos metadata...")
    try:
        metadata = extract_atmos_metadata(file_path)
        if metadata:
            print(f"✅ Metadata extracted successfully!")
            print(f"   Codec: {metadata.codec}")
            print(f"   Channels: {metadata.channels}")
            print(f"   Bed config: {metadata.bed_configuration}")
            print(f"   Sample rate: {metadata.sample_rate}")
            print(f"   is_adm_wav: {metadata.is_adm_wav}")
            print(f"   is_iab: {metadata.is_iab}")
            print(f"   is_mxf: {metadata.is_mxf}")
        else:
            print(f"❌ Failed to extract metadata (returned None)")
    except Exception as e:
        print(f"❌ Exception during metadata extraction: {e}")
        import traceback
        traceback.print_exc()

    # Test 2: Check if detected as Atmos
    print("\n[2] Checking is_atmos_file()...")
    try:
        is_atmos = is_atmos_file(file_path)
        if is_atmos:
            print(f"✅ File IS detected as Atmos!")
        else:
            print(f"❌ File is NOT detected as Atmos")
    except Exception as e:
        print(f"❌ Exception during Atmos detection: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*80)
    print("Test complete!")
    print("="*80)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_atmos_detection.py <path_to_adm_wav_file>")
        print("\nExample:")
        print("  python test_atmos_detection.py uploads/WonderWoman_Trailer.wav")
        sys.exit(1)

    file_path = sys.argv[1]
    if not Path(file_path).exists():
        print(f"❌ Error: File not found: {file_path}")
        sys.exit(1)

    test_atmos_detection(file_path)
