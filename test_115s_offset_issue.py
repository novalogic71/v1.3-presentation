#!/usr/bin/env python3
"""
Test script to investigate the 115s offset issue

Tests the specific files that reported 115.057914s offset to understand:
1. Why SmartVerifier isn't catching it
2. What correlation peaks are being found
3. Whether it's a false peak or calculation error
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Test files from user
MASTER = "/mnt/data/dubsync/WB_Proxies/E2212446_ORIGINALS_THE_YR05_17_18_WE_HAVE_NOT_LONG_TO_LOVE_T4610009_16x9_EPISODE_2_0_LTRT_640x360_23976fps_16825662.mp4"
COMPONENTS = [
    "/mnt/data/dubsync/WB_Batch_2/Upload 2/E2316733_WHV_OriginalsS05_09WeHaveNotLongToLove_hd25p_ICR16_TJF-J2K_a0.mxf",
    "/mnt/data/dubsync/WB_Batch_2/Upload 2/E2316733_WHV_OriginalsS05_09WeHaveNotLongToLove_hd25p_ICR16_TJF-J2K_a1.mxf",
    "/mnt/data/dubsync/WB_Batch_2/Upload 2/E2316733_WHV_OriginalsS05_09WeHaveNotLongToLove_hd25p_ICR16_TJF-J2K_a2.mxf",
    "/mnt/data/dubsync/WB_Batch_2/Upload 2/E2316733_WHV_OriginalsS05_09WeHaveNotLongToLove_hd25p_ICR16_TJF-J2K_a3.mxf",
]

def test_file_exists(path):
    """Check if file exists"""
    exists = os.path.exists(path)
    logger.info(f"File exists: {exists} - {Path(path).name}")
    return exists

def test_smartverifier_thresholds():
    """Test SmartVerifier thresholds"""
    logger.info("\n" + "="*60)
    logger.info("TEST 1: SmartVerifier Thresholds")
    logger.info("="*60)
    
    from sync_analyzer.core.smart_verify import SmartVerifier
    
    verifier = SmartVerifier()
    logger.info(f"Large offset threshold: {verifier.thresholds['large_offset']}s")
    logger.info(f"Verification threshold: {verifier.VERIFICATION_THRESHOLD:.0%}")
    
    # Test with 115s offset
    test_offset = 115.057914
    result = verifier.check_indicators(
        gpu_offset=test_offset,
        gpu_confidence=0.8,  # Assume high confidence
        master_duration=3600,  # Assume 1 hour
        dub_duration=3600,
    )
    
    logger.info(f"\n115s offset check:")
    logger.info(f"  Needs verification: {result.needs_verification}")
    logger.info(f"  Severity score: {result.severity_score:.0%}")
    logger.info(f"  Triggered indicators: {result.triggered_indicators}")
    logger.info(f"  Recommendation: {result.recommendation}")
    
    return result.needs_verification

def test_componentized_analysis():
    """Test componentized analysis on actual files"""
    logger.info("\n" + "="*60)
    logger.info("TEST 2: Componentized Analysis")
    logger.info("="*60)
    
    # Check files exist
    if not test_file_exists(MASTER):
        logger.error(f"Master file not found: {MASTER}")
        return None
    
    missing = [c for c in COMPONENTS if not test_file_exists(c)]
    if missing:
        logger.error(f"Missing component files: {len(missing)}")
        for m in missing:
            logger.error(f"  - {Path(m).name}")
        return None
    
    logger.info(f"All files found. Testing analysis...")
    
    try:
        from fastapi_app.app.services.componentized_service import run_componentized_analysis
        
        components = [
            {"path": c, "label": f"Component {i}", "name": Path(c).name}
            for i, c in enumerate(COMPONENTS)
        ]
        
        logger.info("Running channel_aware analysis...")
        result = run_componentized_analysis(
            master_path=MASTER,
            components=components,
            offset_mode="channel_aware",
            methods=['mfcc', 'spectral', 'onset', 'correlation'],  # Added correlation for better precision
            frame_rate=23.976,
            verbose=True
        )
        
        logger.info(f"\nAnalysis Results:")
        logger.info(f"  Offset mode: {result.get('offset_mode')}")
        logger.info(f"  Voted offset: {result.get('voted_offset_seconds')}s")
        logger.info(f"  Vote agreement: {result.get('vote_agreement', 0):.0%}")
        
        component_results = result.get('component_results', [])
        logger.info(f"\nComponent Results ({len(component_results)}):")
        for comp in component_results:
            offset = comp.get('offset_seconds', 0)
            conf = comp.get('confidence', 0)
            logger.info(f"  {comp.get('component')}: {offset:.3f}s (conf: {conf:.1%})")
        
        return result
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_direct_analysis():
    """Test direct analysis on first component"""
    logger.info("\n" + "="*60)
    logger.info("TEST 3: Direct Analysis (First Component)")
    logger.info("="*60)
    
    if not test_file_exists(MASTER) or not test_file_exists(COMPONENTS[0]):
        logger.error("Files not found")
        return None
    
    try:
        from sync_analyzer.analysis import analyze
        from pathlib import Path
        
        logger.info("Running analyze() on first component...")
        consensus, sync_results, ai_result = analyze(
            Path(MASTER),
            Path(COMPONENTS[0]),
            methods=['mfcc', 'onset', 'spectral', 'correlation']  # Added correlation for better precision
        )
        
        logger.info(f"\nDirect Analysis Results:")
        logger.info(f"  Consensus offset: {consensus.offset_seconds:.3f}s")
        logger.info(f"  Confidence: {consensus.confidence:.1%}")
        logger.info(f"  Method used: {consensus.method_used}")
        
        logger.info(f"\nMethod Results:")
        for method, result in sync_results.items():
            logger.info(f"  {method}: {result.offset_seconds:.3f}s (conf: {result.confidence:.1%})")
        
        return consensus, sync_results
        
    except Exception as e:
        logger.error(f"Direct analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_correlation_peaks():
    """Test correlation peak analysis"""
    logger.info("\n" + "="*60)
    logger.info("TEST 4: Correlation Peak Analysis")
    logger.info("="*60)
    
    if not test_file_exists(MASTER) or not test_file_exists(COMPONENTS[0]):
        logger.error("Files not found")
        return None
    
    try:
        import librosa
        import numpy as np
        import scipy.signal
        
        logger.info("Loading audio...")
        master_audio, sr = librosa.load(MASTER, sr=22050, duration=300, mono=True)
        dub_audio, _ = librosa.load(COMPONENTS[0], sr=22050, duration=300, mono=True)
        
        logger.info(f"Master: {len(master_audio)/sr:.1f}s, Dub: {len(dub_audio)/sr:.1f}s")
        
        # Extract MFCC
        logger.info("Extracting MFCC features...")
        master_mfcc = librosa.feature.mfcc(y=master_audio, sr=sr, n_mfcc=13)[1, :]  # Skip C0
        dub_mfcc = librosa.feature.mfcc(y=dub_audio, sr=sr, n_mfcc=13)[1, :]
        
        # Normalize
        master_mfcc = (master_mfcc - np.mean(master_mfcc)) / (np.std(master_mfcc) + 1e-8)
        dub_mfcc = (dub_mfcc - np.mean(dub_mfcc)) / (np.std(dub_mfcc) + 1e-8)
        
        # Cross-correlate
        logger.info("Computing cross-correlation...")
        correlation = scipy.signal.correlate(master_mfcc, dub_mfcc, mode='full')
        abs_corr = np.abs(correlation)
        
        # Find top peaks
        peak_indices = np.argsort(abs_corr)[::-1][:5]
        
        logger.info(f"\nTop 5 Correlation Peaks:")
        zero_lag_idx = len(dub_mfcc) - 1
        hop_length = 512
        sample_rate = 22050
        
        for i, peak_idx in enumerate(peak_indices):
            peak_value = abs_corr[peak_idx]
            offset_frames = peak_idx - zero_lag_idx
            offset_samples = offset_frames * hop_length
            offset_seconds = offset_samples / sample_rate
            
            logger.info(f"  Peak {i+1}: idx={peak_idx}, value={peak_value:.4f}, offset={offset_seconds:.3f}s")
        
        # Check peak prominence
        top_peak = abs_corr[peak_indices[0]]
        second_peak = abs_corr[peak_indices[1]] if len(peak_indices) > 1 else 0
        prominence_ratio = top_peak / (second_peak + 1e-8)
        
        logger.info(f"\nPeak Analysis:")
        logger.info(f"  Top peak value: {top_peak:.4f}")
        logger.info(f"  Second peak value: {second_peak:.4f}")
        logger.info(f"  Prominence ratio: {prominence_ratio:.2f}x")
        logger.info(f"  Mean correlation: {np.mean(abs_corr):.4f}")
        logger.info(f"  Std correlation: {np.std(abs_corr):.4f}")
        
        return {
            'top_peaks': [(peak_indices[i], abs_corr[peak_indices[i]]) for i in range(len(peak_indices))],
            'prominence_ratio': prominence_ratio
        }
        
    except Exception as e:
        logger.error(f"Correlation analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Run all tests"""
    logger.info("="*60)
    logger.info("Investigating 115s Offset Issue")
    logger.info("="*60)
    
    # Test 1: SmartVerifier thresholds
    test_smartverifier_thresholds()
    
    # Test 2: Componentized analysis
    comp_result = test_componentized_analysis()
    
    # Test 3: Direct analysis
    direct_result = test_direct_analysis()
    
    # Test 4: Correlation peaks
    peak_result = test_correlation_peaks()
    
    logger.info("\n" + "="*60)
    logger.info("Summary")
    logger.info("="*60)
    
    if comp_result:
        voted_offset = comp_result.get('voted_offset_seconds', 0)
        logger.info(f"Componentized voted offset: {voted_offset:.3f}s")
        if abs(voted_offset - 115.057914) < 0.1:
            logger.warning("⚠️  Found 115s offset in componentized analysis!")
    
    if direct_result:
        consensus, _ = direct_result
        logger.info(f"Direct analysis offset: {consensus.offset_seconds:.3f}s")
        if abs(consensus.offset_seconds - 115.057914) < 0.1:
            logger.warning("⚠️  Found 115s offset in direct analysis!")
    
    if peak_result:
        logger.info(f"Peak prominence ratio: {peak_result['prominence_ratio']:.2f}x")
        if peak_result['prominence_ratio'] < 2.0:
            logger.warning("⚠️  Low peak prominence - likely false peak!")

if __name__ == "__main__":
    main()
