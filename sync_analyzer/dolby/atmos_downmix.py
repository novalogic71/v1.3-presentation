"""
Dolby Atmos ADM BW64 Downmix Module
===================================

Professional-quality downmix for Dolby Atmos ADM BW64 files using
ITU-R BS.775 style coefficients.

This module provides functions to downmix multichannel Atmos files
(66+ channels) to standard layouts: Stereo, 5.1, 7.1.

Usage:
    from sync_analyzer.dolby.atmos_downmix import downmix_to_stereo_file
    
    # Downmix ADM BW64 to stereo
    downmix_to_stereo_file("input_atmos.wav", "output_stereo.wav")
"""

import logging
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

try:
    import soundfile as sf
except ImportError:
    sf = None

logger = logging.getLogger(__name__)


# ============================================================================
# ITU-R BS.775-3 Downmix Coefficients
# ============================================================================

COEF_CENTER = 0.707107      # -3 dB (1/sqrt(2))
COEF_SURROUND = 0.707107    # -3 dB
COEF_REAR = 0.5             # -6 dB
COEF_HEIGHT = 0.5           # -6 dB
COEF_HEIGHT_REAR = 0.35     # ~-9 dB
COEF_LFE_STEREO = 0.0       # LFE excluded from stereo by default


# ============================================================================
# Channel Layout Definitions
# ============================================================================

# Dolby Atmos 7.1.4 Bed Channel Order (first 12 channels of ADM BW64)
ATMOS_714_BED = {
    'L': 0,      # Left
    'R': 1,      # Right
    'C': 2,      # Center
    'LFE': 3,    # Low Frequency Effects
    'Ls': 4,     # Left Surround
    'Rs': 5,     # Right Surround
    'Lrs': 6,    # Left Rear Surround (Back Left)
    'Rrs': 7,    # Right Rear Surround (Back Right)
    'Ltf': 8,    # Left Top Front (Height Front Left)
    'Rtf': 9,    # Right Top Front (Height Front Right)
    'Ltr': 10,   # Left Top Rear (Height Rear Left)
    'Rtr': 11,   # Right Top Rear (Height Rear Right)
}


# ============================================================================
# Utility Functions
# ============================================================================

def _get_channel(data: np.ndarray, idx: int) -> np.ndarray:
    """Safely get a channel, returning zeros if index out of range."""
    if idx < data.shape[1]:
        return data[:, idx]
    return np.zeros(data.shape[0], dtype=data.dtype)


def downmix_lr_bed_only(data: np.ndarray) -> np.ndarray:
    """
    Simple L+R bed channel extraction for sync detection.
    
    This produces audio that matches stereo masters better than
    the full ITU-R BS.775 downmix because the stereo master was
    likely created from the same L/R beds.
    
    Use this for sync detection against stereo files.
    Use downmix_to_stereo for proper listening-quality downmix.
    
    Args:
        data: Multichannel audio array (samples, channels)
        
    Returns:
        Mono audio array (L+R summed and normalized)
    """
    L = _get_channel(data, 0)
    R = _get_channel(data, 1)
    
    # Sum to mono
    mono = (L + R) / 2
    
    return mono


def downmix_lr_bed_stereo(data: np.ndarray) -> np.ndarray:
    """
    Extract L/R bed channels as stereo for sync detection.
    
    Args:
        data: Multichannel audio array (samples, channels)
        
    Returns:
        Stereo audio array (samples, 2)
    """
    L = _get_channel(data, 0)
    R = _get_channel(data, 1)
    
    return np.column_stack([L, R])


def _normalize_audio(audio: np.ndarray, target_peak: float = 0.95) -> Tuple[np.ndarray, float]:
    """
    Normalize audio to prevent clipping.
    
    Args:
        audio: Audio array
        target_peak: Target peak level (0.0-1.0)
        
    Returns:
        Tuple of (normalized_audio, gain_applied)
    """
    peak = np.max(np.abs(audio))
    
    if peak > 1.0:
        gain = target_peak / peak
        return audio * gain, gain
    elif peak > target_peak:
        gain = target_peak / peak
        return audio * gain, gain
    
    return audio, 1.0


# ============================================================================
# Downmix Functions
# ============================================================================

def downmix_to_stereo(data: np.ndarray, include_lfe: bool = False) -> np.ndarray:
    """
    Downmix multi-channel audio to stereo using ITU-R BS.775 coefficients.
    
    Handles: 7.1.4, 7.1.2, 7.1, 5.1, or any multi-channel layout.
    
    Args:
        data: Input audio array (samples, channels)
        include_lfe: Whether to include LFE in downmix (default: False)
        
    Returns:
        Stereo audio array (samples, 2)
    """
    n_channels = data.shape[1]
    
    # Get bed channels (first 12 for 7.1.4, or fewer for smaller layouts)
    L = _get_channel(data, 0)
    R = _get_channel(data, 1)
    C = _get_channel(data, 2)
    LFE = _get_channel(data, 3)
    Ls = _get_channel(data, 4)
    Rs = _get_channel(data, 5)
    
    # Rear surrounds (if present)
    Lrs = _get_channel(data, 6) if n_channels > 6 else np.zeros_like(L)
    Rrs = _get_channel(data, 7) if n_channels > 7 else np.zeros_like(L)
    
    # Height channels (if present - 7.1.4 or 7.1.2)
    if n_channels >= 12:  # 7.1.4
        Ltf = _get_channel(data, 8)
        Rtf = _get_channel(data, 9)
        Ltr = _get_channel(data, 10)
        Rtr = _get_channel(data, 11)
    elif n_channels >= 10:  # 7.1.2
        Ltf = _get_channel(data, 8)
        Rtf = _get_channel(data, 9)
        Ltr = np.zeros_like(L)
        Rtr = np.zeros_like(L)
    else:
        Ltf = Rtf = Ltr = Rtr = np.zeros_like(L)
    
    # LFE coefficient
    lfe_coef = 0.25 if include_lfe else 0.0
    
    # Downmix equations (ITU-R BS.775 style)
    stereo_L = (
        L + 
        COEF_CENTER * C + 
        COEF_SURROUND * Ls + 
        COEF_REAR * Lrs + 
        COEF_HEIGHT * Ltf + 
        COEF_HEIGHT_REAR * Ltr +
        lfe_coef * LFE
    )
    
    stereo_R = (
        R + 
        COEF_CENTER * C + 
        COEF_SURROUND * Rs + 
        COEF_REAR * Rrs + 
        COEF_HEIGHT * Rtf + 
        COEF_HEIGHT_REAR * Rtr +
        lfe_coef * LFE
    )
    
    return np.column_stack([stereo_L, stereo_R])


def downmix_to_51(data: np.ndarray) -> np.ndarray:
    """
    Downmix multi-channel audio to 5.1 surround.
    
    Folds rear surrounds and heights into the surround channels.
    
    Args:
        data: Input audio array (samples, channels)
        
    Returns:
        5.1 audio array (samples, 6) - L, R, C, LFE, Ls, Rs
    """
    n_channels = data.shape[1]
    
    L = _get_channel(data, 0)
    R = _get_channel(data, 1)
    C = _get_channel(data, 2)
    LFE = _get_channel(data, 3)
    Ls = _get_channel(data, 4)
    Rs = _get_channel(data, 5)
    
    # Fold rear surrounds into side surrounds
    if n_channels > 6:
        Lrs = _get_channel(data, 6)
        Rrs = _get_channel(data, 7)
        Ls = Ls + COEF_REAR * Lrs
        Rs = Rs + COEF_REAR * Rrs
    
    # Fold heights into main channels
    if n_channels >= 12:  # 7.1.4
        Ltf = _get_channel(data, 8)
        Rtf = _get_channel(data, 9)
        Ltr = _get_channel(data, 10)
        Rtr = _get_channel(data, 11)
        
        # Front heights -> L/R, Rear heights -> Ls/Rs
        L = L + COEF_HEIGHT * Ltf
        R = R + COEF_HEIGHT * Rtf
        Ls = Ls + COEF_HEIGHT_REAR * Ltr
        Rs = Rs + COEF_HEIGHT_REAR * Rtr
    elif n_channels >= 10:  # 7.1.2
        Ltm = _get_channel(data, 8)
        Rtm = _get_channel(data, 9)
        L = L + COEF_HEIGHT * Ltm
        R = R + COEF_HEIGHT * Rtm
    
    return np.column_stack([L, R, C, LFE, Ls, Rs])


def downmix_to_71(data: np.ndarray) -> np.ndarray:
    """
    Downmix multi-channel audio to 7.1 surround.
    
    Folds heights into the bed channels.
    
    Args:
        data: Input audio array (samples, channels)
        
    Returns:
        7.1 audio array (samples, 8) - L, R, C, LFE, Ls, Rs, Lrs, Rrs
    """
    n_channels = data.shape[1]
    
    L = _get_channel(data, 0)
    R = _get_channel(data, 1)
    C = _get_channel(data, 2)
    LFE = _get_channel(data, 3)
    Ls = _get_channel(data, 4)
    Rs = _get_channel(data, 5)
    Lrs = _get_channel(data, 6) if n_channels > 6 else np.zeros_like(L)
    Rrs = _get_channel(data, 7) if n_channels > 7 else np.zeros_like(L)
    
    # Fold heights into main channels
    if n_channels >= 12:  # 7.1.4
        Ltf = _get_channel(data, 8)
        Rtf = _get_channel(data, 9)
        Ltr = _get_channel(data, 10)
        Rtr = _get_channel(data, 11)
        
        L = L + COEF_HEIGHT * Ltf
        R = R + COEF_HEIGHT * Rtf
        Lrs = Lrs + COEF_HEIGHT_REAR * Ltr
        Rrs = Rrs + COEF_HEIGHT_REAR * Rtr
    elif n_channels >= 10:  # 7.1.2
        Ltm = _get_channel(data, 8)
        Rtm = _get_channel(data, 9)
        L = L + COEF_HEIGHT * Ltm
        R = R + COEF_HEIGHT * Rtm
    
    return np.column_stack([L, R, C, LFE, Ls, Rs, Lrs, Rrs])


# ============================================================================
# File-based Conversion Functions
# ============================================================================

def downmix_to_stereo_file(
    input_path: str,
    output_path: str,
    include_lfe: bool = False,
    normalize: bool = True,
    bit_depth: int = 16
) -> Optional[str]:
    """
    Downmix a multichannel WAV file to stereo using ITU-R BS.775 coefficients.
    
    This is the main entry point for the Atmos pipeline integration.
    
    Args:
        input_path: Path to input multichannel WAV file (ADM BW64, etc.)
        output_path: Path for output stereo WAV file
        include_lfe: Whether to include LFE in downmix
        normalize: Normalize output to prevent clipping
        bit_depth: Output bit depth (16, 24, or 32)
        
    Returns:
        Path to output file on success, None on failure
    """
    if sf is None:
        logger.error("soundfile not available for downmix")
        return None
    
    subtype_map = {16: 'PCM_16', 24: 'PCM_24', 32: 'FLOAT'}
    subtype = subtype_map.get(bit_depth, 'PCM_16')
    
    try:
        logger.info(f"[Downmix] Reading: {input_path}")
        data, samplerate = sf.read(input_path, always_2d=True)
        
        n_channels = data.shape[1]
        duration = data.shape[0] / samplerate
        logger.info(f"[Downmix] Input: {n_channels} channels, {samplerate} Hz, {duration:.2f}s")
        
        if n_channels < 2:
            logger.error(f"[Downmix] Input has only {n_channels} channel(s), cannot downmix")
            return None
        
        if n_channels == 2:
            logger.info("[Downmix] Input is already stereo, copying as-is")
            stereo = data
        else:
            stereo = downmix_to_stereo(data, include_lfe=include_lfe)
            logger.info(f"[Downmix] Applied ITU-R BS.775 downmix: {n_channels}ch -> 2ch")
        
        # Normalize if needed
        if normalize:
            stereo, gain = _normalize_audio(stereo)
            if gain != 1.0:
                logger.info(f"[Downmix] Normalized: {20 * np.log10(gain):.1f} dB")
        
        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Write output
        sf.write(output_path, stereo, samplerate, subtype=subtype)
        logger.info(f"[Downmix] ✅ Output: {output_path}")
        
        return output_path
        
    except Exception as e:
        logger.error(f"[Downmix] Failed: {e}")
        return None


def downmix_to_mono_file(
    input_path: str,
    output_path: str,
    include_lfe: bool = False,
    normalize: bool = True,
    bit_depth: int = 16
) -> Optional[str]:
    """
    Downmix a multichannel WAV file to mono using ITU-R BS.775 coefficients.
    
    First downmixes to stereo using professional coefficients, then sums L+R to mono.
    
    Args:
        input_path: Path to input multichannel WAV file (ADM BW64, etc.)
        output_path: Path for output mono WAV file
        include_lfe: Whether to include LFE in downmix
        normalize: Normalize output to prevent clipping
        bit_depth: Output bit depth (16, 24, or 32)
        
    Returns:
        Path to output file on success, None on failure
    """
    if sf is None:
        logger.error("soundfile not available for mono downmix")
        return None
    
    subtype_map = {16: 'PCM_16', 24: 'PCM_24', 32: 'FLOAT'}
    subtype = subtype_map.get(bit_depth, 'PCM_16')
    
    try:
        logger.info(f"[Downmix-Mono] Reading: {input_path}")
        data, samplerate = sf.read(input_path, always_2d=True)
        
        n_channels = data.shape[1]
        duration = data.shape[0] / samplerate
        logger.info(f"[Downmix-Mono] Input: {n_channels} channels, {samplerate} Hz, {duration:.2f}s")
        
        if n_channels == 1:
            logger.info("[Downmix-Mono] Input is already mono, copying as-is")
            mono = data[:, 0]
        elif n_channels == 2:
            # Simple L+R average for stereo
            mono = np.mean(data, axis=1)
            logger.info("[Downmix-Mono] Stereo to mono: (L+R)/2")
        else:
            # First downmix to stereo using professional coefficients
            stereo = downmix_to_stereo(data, include_lfe=include_lfe)
            # Then sum to mono
            mono = np.mean(stereo, axis=1)
            logger.info(f"[Downmix-Mono] Applied ITU-R BS.775 downmix: {n_channels}ch -> stereo -> mono")
        
        # Normalize if needed
        if normalize:
            mono_2d = mono.reshape(-1, 1)  # Make 2D for normalize function
            mono_2d, gain = _normalize_audio(mono_2d)
            mono = mono_2d[:, 0]
            if gain != 1.0:
                logger.info(f"[Downmix-Mono] Normalized: {20 * np.log10(gain):.1f} dB")
        
        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Write output
        sf.write(output_path, mono, samplerate, subtype=subtype)
        logger.info(f"[Downmix-Mono] ✅ Output: {output_path}")
        
        return output_path
        
    except Exception as e:
        logger.error(f"[Downmix-Mono] Failed: {e}")
        return None


def downmix_to_layout_file(
    input_path: str,
    output_path: str,
    layout: str = 'stereo',
    normalize: bool = True,
    bit_depth: int = 16
) -> Optional[str]:
    """
    Downmix a multichannel WAV file to a specified layout.
    
    Args:
        input_path: Path to input multichannel WAV file
        output_path: Path for output WAV file
        layout: Target layout - 'stereo', '5.1', or '7.1'
        normalize: Normalize output to prevent clipping
        bit_depth: Output bit depth (16, 24, or 32)
        
    Returns:
        Path to output file on success, None on failure
    """
    if sf is None:
        logger.error("soundfile not available for downmix")
        return None
    
    subtype_map = {16: 'PCM_16', 24: 'PCM_24', 32: 'FLOAT'}
    subtype = subtype_map.get(bit_depth, 'PCM_16')
    
    try:
        logger.info(f"[Downmix] Reading: {input_path}")
        data, samplerate = sf.read(input_path, always_2d=True)
        
        n_channels = data.shape[1]
        logger.info(f"[Downmix] Input: {n_channels} channels")
        
        # Select downmix function based on layout
        layout_lower = layout.lower().replace(' ', '').replace('.', '')
        
        if layout_lower in ('stereo', '20', '0+2+0'):
            output = downmix_to_stereo(data)
            layout_name = 'Stereo'
        elif layout_lower in ('51', '0+5+0'):
            output = downmix_to_51(data)
            layout_name = '5.1'
        elif layout_lower in ('71', '0+7+0'):
            output = downmix_to_71(data)
            layout_name = '7.1'
        else:
            logger.error(f"[Downmix] Unknown layout: {layout}")
            return None
        
        logger.info(f"[Downmix] Applied {layout_name} downmix: {n_channels}ch -> {output.shape[1]}ch")
        
        # Normalize if needed
        if normalize:
            output, gain = _normalize_audio(output)
            if gain != 1.0:
                logger.info(f"[Downmix] Normalized: {20 * np.log10(gain):.1f} dB")
        
        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Write output
        sf.write(output_path, output, samplerate, subtype=subtype)
        logger.info(f"[Downmix] ✅ Output: {output_path}")
        
        return output_path
        
    except Exception as e:
        logger.error(f"[Downmix] Failed: {e}")
        return None

