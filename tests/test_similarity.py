import numpy as np
import pytest

from sync_analyzer.core.optimized_large_file_detector import (
    OptimizedLargeFileDetector,
)


def test_compute_chunk_similarity_weighted_average():
    d = OptimizedLargeFileDetector(gpu_enabled=False)

    # Create small deterministic features
    f1 = {
        "mfcc": np.array([[1.0, 2.0, 3.0]]),
        "rms": np.array([[0.1, 0.2, 0.3]]),
        "onsets": np.array([0.1, 0.2, 0.4]),
    }
    f2 = {
        "mfcc": np.array([[1.0, 2.0, 3.0]]),  # identical -> corr ~= 1
        "rms": np.array([[0.1, 0.2, 0.3]]),   # identical -> corr ~= 1
        "onsets": np.array([0.1, 0.2, 0.4]),  # same count -> 1/(1+0)=1
    }

    sims = d.compute_chunk_similarity(f1, f2)
    # Weighted overall with weights: mfcc 0.6, onsets 0.25, rms 0.15 -> should be ~1
    assert "overall" in sims
    assert sims["overall"] == pytest.approx(1.0, rel=1e-5, abs=1e-5)


def test_compute_chunk_similarity_missing_features_returns_zero():
    d = OptimizedLargeFileDetector(gpu_enabled=False)
    sims = d.compute_chunk_similarity({}, {})
    assert sims == {"overall": 0.0}
