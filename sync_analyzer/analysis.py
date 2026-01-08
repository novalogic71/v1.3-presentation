from pathlib import Path
from typing import List, Optional, Tuple

from .core.audio_sync_detector import ProfessionalSyncDetector
from .ai.embedding_sync_detector import AISyncDetector, EmbeddingConfig


def analyze(
    master: Path,
    dub: Path,
    methods: Optional[List[str]] = None,
    enable_ai: bool = False,
    ai_model: str = "wav2vec2",
    use_gpu: bool = False,
) -> Tuple[object, dict, Optional[object]]:
    """Run sync analysis and return consensus result.

    Parameters
    ----------
    master, dub:
        Paths to the master and dub audio files.
    methods:
        List of analysis methods. ``['mfcc']`` by default. Use ``['all']`` to
        enable all available methods.
    enable_ai:
        Whether to run the AI-based sync detector.
    ai_model:
        Name of the AI model to use when ``enable_ai`` is True.
    use_gpu:
        Enable GPU acceleration when available.

    Returns
    -------
    tuple
        ``(consensus_result, sync_results, ai_result)`` where ``ai_result`` may
        be ``None`` when AI detection is disabled.
    """

    methods = methods or ["mfcc"]
    if "all" in methods:
        methods = ["mfcc", "onset", "spectral"]

    detector = ProfessionalSyncDetector(use_gpu=use_gpu)
    sync_results = detector.analyze_sync(master, dub, methods)
    # Pass requested methods to consensus so it respects user's selection
    consensus = detector.get_consensus_result(sync_results, requested_methods=methods)

    ai_result = None
    if enable_ai:
        config = EmbeddingConfig(
            model_name=ai_model,
            sample_rate=16000,
            use_gpu=use_gpu,
        )
        ai_detector = AISyncDetector(config)
        master_audio, _ = detector.load_and_preprocess_audio(master)
        dub_audio, _ = detector.load_and_preprocess_audio(dub)
        ai_result = ai_detector.detect_sync(master_audio, dub_audio, 16000)

    return consensus, sync_results, ai_result
