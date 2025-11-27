#!/usr/bin/env python3
"""
Quick diagnostic script to test single file analysis
"""
import sys
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

try:
    from sync_analyzer.core.audio_sync_detector import ProfessionalSyncDetector
    logger.info("✓ Successfully imported ProfessionalSyncDetector")
except Exception as e:
    logger.error(f"✗ Failed to import ProfessionalSyncDetector: {e}")
    sys.exit(1)

def test_detector_initialization():
    """Test that detector can be initialized"""
    try:
        detector = ProfessionalSyncDetector(sample_rate=22050)
        logger.info(f"✓ Detector initialized successfully")
        logger.info(f"  - Sample rate: {detector.sample_rate}")
        logger.info(f"  - GPU available: {detector.use_gpu}")
        return detector
    except Exception as e:
        logger.error(f"✗ Failed to initialize detector: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_load_audio(detector, test_file_path):
    """Test loading an audio file"""
    if not Path(test_file_path).exists():
        logger.warning(f"⚠ Test file not found: {test_file_path}")
        return False

    try:
        logger.info(f"Testing load_and_preprocess_audio with: {test_file_path}")
        audio, sr = detector.load_and_preprocess_audio(Path(test_file_path))
        logger.info(f"✓ Audio loaded successfully")
        logger.info(f"  - Duration: {len(audio)/sr:.2f}s")
        logger.info(f"  - Sample rate: {sr}")
        logger.info(f"  - Shape: {audio.shape}")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to load audio: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Single File Analysis Diagnostic Test")
    logger.info("=" * 60)

    # Test 1: Initialize detector
    detector = test_detector_initialization()
    if not detector:
        sys.exit(1)

    # Test 2: Try to load an audio file if provided
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
        success = test_load_audio(detector, test_file)
        sys.exit(0 if success else 1)
    else:
        logger.info("\n✓ Basic initialization tests passed")
        logger.info("\nTo test audio loading, run:")
        logger.info(f"  python {sys.argv[0]} <path_to_audio_file>")
        sys.exit(0)
