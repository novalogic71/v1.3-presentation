#!/usr/bin/env python3
"""
Compare Single File Analysis vs Batch Analysis Results
To diagnose offset calculation discrepancies
"""
import sys
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_professional_detector(master_path, dub_path):
    """Test using ProfessionalSyncDetector (single file analysis)"""
    logger.info("=" * 80)
    logger.info("TESTING: ProfessionalSyncDetector (Single File Analysis Path)")
    logger.info("=" * 80)

    try:
        from sync_analyzer.core.audio_sync_detector import ProfessionalSyncDetector

        detector = ProfessionalSyncDetector(sample_rate=22050, window_size_seconds=30.0)
        logger.info(f"✓ Initialized ProfessionalSyncDetector (SR={detector.sample_rate})")

        results = detector.analyze_sync(
            Path(master_path),
            Path(dub_path),
            methods=['mfcc', 'onset', 'spectral']
        )

        logger.info(f"✓ Analysis complete, {len(results)} methods")
        logger.info("")
        logger.info("Results by method:")
        for method, result in results.items():
            logger.info(f"  {method.upper():12s}: {result.offset_seconds:+8.3f}s ({result.confidence:.2f} confidence)")

        # Get consensus
        consensus = detector.get_consensus_result(results)
        logger.info("")
        logger.info(f"CONSENSUS: {consensus.offset_seconds:+8.3f}s ({consensus.confidence:.2f} confidence)")
        logger.info(f"Method: {consensus.method_used}")

        return consensus.offset_seconds, results

    except Exception as e:
        logger.error(f"✗ ProfessionalSyncDetector failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def test_optimized_detector(master_path, dub_path):
    """Test using OptimizedLargeFileDetector (batch analysis)"""
    logger.info("")
    logger.info("=" * 80)
    logger.info("TESTING: OptimizedLargeFileDetector (Batch Analysis Path)")
    logger.info("=" * 80)

    try:
        from sync_analyzer.core.optimized_large_file_detector import OptimizedLargeFileDetector

        detector = OptimizedLargeFileDetector(gpu_enabled=True, chunk_size=30.0)
        logger.info(f"✓ Initialized OptimizedLargeFileDetector (SR={detector.sample_rate})")

        result = detector.analyze_sync_chunked(master_path, dub_path)

        offset = result.get('offset_seconds', 0.0)
        confidence = result.get('confidence', 0.0)
        chunks_analyzed = result.get('chunks_analyzed', 0)

        logger.info(f"✓ Analysis complete")
        logger.info("")
        logger.info(f"RESULT: {offset:+8.3f}s ({confidence:.2f} confidence)")
        logger.info(f"Chunks analyzed: {chunks_analyzed}")
        logger.info(f"Sync status: {result.get('sync_status', 'N/A')}")

        return offset, result

    except Exception as e:
        logger.error(f"✗ OptimizedLargeFileDetector failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def main():
    if len(sys.argv) != 3:
        print("Usage: python test_single_vs_batch.py <master_file> <dub_file>")
        print()
        print("Example:")
        print("  python test_single_vs_batch.py \\")
        print("    /mnt/data/amcmurray/_insync_master_files/DunkirkEC_InsideTheCockpit_ProRes.mov \\")
        print("    /mnt/data/amcmurray/_outofsync_master_files/DunkirkEC_InsideTheCockpit_ProRes_15sec.mov")
        sys.exit(1)

    master_path = sys.argv[1]
    dub_path = sys.argv[2]

    logger.info(f"Master: {master_path}")
    logger.info(f"Dub:    {dub_path}")
    logger.info("")

    # Test both detectors
    single_offset, single_results = test_professional_detector(master_path, dub_path)
    batch_offset, batch_result = test_optimized_detector(master_path, dub_path)

    # Compare results
    logger.info("")
    logger.info("=" * 80)
    logger.info("COMPARISON")
    logger.info("=" * 80)

    if single_offset is not None and batch_offset is not None:
        logger.info(f"Single File Analysis: {single_offset:+8.3f}s")
        logger.info(f"Batch Analysis:       {batch_offset:+8.3f}s")
        logger.info(f"Difference:           {abs(single_offset - batch_offset):8.3f}s")

        if abs(single_offset - batch_offset) > 0.5:
            logger.warning("⚠️  SIGNIFICANT DISCREPANCY DETECTED!")
            logger.warning("   Single and batch analysis disagree by more than 0.5 seconds")
        else:
            logger.info("✓ Results are consistent")
    else:
        logger.error("✗ Could not compare - one or both tests failed")

if __name__ == "__main__":
    main()
