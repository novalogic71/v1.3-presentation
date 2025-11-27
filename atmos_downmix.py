#!/usr/bin/env python3
"""
Dolby Atmos ADM BW64 Downmix Tool
=================================

Downmixes Dolby Atmos ADM BW64 WAV files (66+ channels) to standard layouts:
- Stereo (0+2+0)
- 5.1 Surround (0+5+0)
- 7.1 Surround (0+7+0)

Uses ITU-R BS.775 style coefficients for professional-quality fold-down.

Usage:
    python atmos_downmix.py input.wav output.wav --layout stereo
    python atmos_downmix.py input.wav output.wav --layout 5.1
    python atmos_downmix.py input.wav output.wav --layout 7.1

Author: Sync Analyzer Project
"""

import argparse
import sys
from pathlib import Path
from typing import Tuple, Optional
import numpy as np

try:
    import soundfile as sf
except ImportError:
    print("Error: soundfile not installed. Run: pip install soundfile")
    sys.exit(1)


# ============================================================================
# ITU-R BS.775-3 Downmix Coefficients
# ============================================================================

# Standard downmix coefficients
COEF_CENTER = 0.707107  # -3 dB (1/sqrt(2))
COEF_SURROUND = 0.707107  # -3 dB
COEF_REAR = 0.5  # -6 dB
COEF_HEIGHT = 0.5  # -6 dB
COEF_HEIGHT_REAR = 0.35  # ~-9 dB
COEF_LFE = 0.0  # LFE typically excluded from stereo (or 0.25 if included)


# ============================================================================
# Channel Layout Definitions
# ============================================================================

# Dolby Atmos 7.1.4 Bed Channel Order (first 12 channels of ADM BW64)
# This is the standard layout for Dolby Atmos ADM exports
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

# Alternative: 7.1.2 Bed (10 channels)
ATMOS_712_BED = {
    'L': 0, 'R': 1, 'C': 2, 'LFE': 3,
    'Ls': 4, 'Rs': 5, 'Lrs': 6, 'Rrs': 7,
    'Ltm': 8,    # Left Top Middle
    'Rtm': 9,    # Right Top Middle
}

# Standard 7.1 (8 channels)
LAYOUT_71 = {
    'L': 0, 'R': 1, 'C': 2, 'LFE': 3,
    'Ls': 4, 'Rs': 5, 'Lrs': 6, 'Rrs': 7,
}

# Standard 5.1 (6 channels)
LAYOUT_51 = {
    'L': 0, 'R': 1, 'C': 2, 'LFE': 3,
    'Ls': 4, 'Rs': 5,
}


# ============================================================================
# Downmix Functions
# ============================================================================

def get_channel(data: np.ndarray, idx: int) -> np.ndarray:
    """Safely get a channel, returning zeros if index out of range."""
    if idx < data.shape[1]:
        return data[:, idx]
    return np.zeros(data.shape[0])


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
    L = get_channel(data, 0)
    R = get_channel(data, 1)
    C = get_channel(data, 2)
    LFE = get_channel(data, 3)
    Ls = get_channel(data, 4)
    Rs = get_channel(data, 5)
    
    # Rear surrounds (if present)
    Lrs = get_channel(data, 6) if n_channels > 6 else np.zeros_like(L)
    Rrs = get_channel(data, 7) if n_channels > 7 else np.zeros_like(L)
    
    # Height channels (if present - 7.1.4 or 7.1.2)
    if n_channels >= 12:  # 7.1.4
        Ltf = get_channel(data, 8)
        Rtf = get_channel(data, 9)
        Ltr = get_channel(data, 10)
        Rtr = get_channel(data, 11)
    elif n_channels >= 10:  # 7.1.2
        Ltf = get_channel(data, 8)
        Rtf = get_channel(data, 9)
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
    
    L = get_channel(data, 0)
    R = get_channel(data, 1)
    C = get_channel(data, 2)
    LFE = get_channel(data, 3)
    Ls = get_channel(data, 4)
    Rs = get_channel(data, 5)
    
    # Fold rear surrounds into side surrounds
    if n_channels > 6:
        Lrs = get_channel(data, 6)
        Rrs = get_channel(data, 7)
        Ls = Ls + COEF_REAR * Lrs
        Rs = Rs + COEF_REAR * Rrs
    
    # Fold heights into main channels
    if n_channels >= 12:  # 7.1.4
        Ltf = get_channel(data, 8)
        Rtf = get_channel(data, 9)
        Ltr = get_channel(data, 10)
        Rtr = get_channel(data, 11)
        
        # Front heights -> L/R, Rear heights -> Ls/Rs
        L = L + COEF_HEIGHT * Ltf
        R = R + COEF_HEIGHT * Rtf
        Ls = Ls + COEF_HEIGHT_REAR * Ltr
        Rs = Rs + COEF_HEIGHT_REAR * Rtr
    elif n_channels >= 10:  # 7.1.2
        Ltm = get_channel(data, 8)
        Rtm = get_channel(data, 9)
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
    
    L = get_channel(data, 0)
    R = get_channel(data, 1)
    C = get_channel(data, 2)
    LFE = get_channel(data, 3)
    Ls = get_channel(data, 4)
    Rs = get_channel(data, 5)
    Lrs = get_channel(data, 6) if n_channels > 6 else np.zeros_like(L)
    Rrs = get_channel(data, 7) if n_channels > 7 else np.zeros_like(L)
    
    # Fold heights into main channels
    if n_channels >= 12:  # 7.1.4
        Ltf = get_channel(data, 8)
        Rtf = get_channel(data, 9)
        Ltr = get_channel(data, 10)
        Rtr = get_channel(data, 11)
        
        L = L + COEF_HEIGHT * Ltf
        R = R + COEF_HEIGHT * Rtf
        Lrs = Lrs + COEF_HEIGHT_REAR * Ltr
        Rrs = Rrs + COEF_HEIGHT_REAR * Rtr
    elif n_channels >= 10:  # 7.1.2
        Ltm = get_channel(data, 8)
        Rtm = get_channel(data, 9)
        L = L + COEF_HEIGHT * Ltm
        R = R + COEF_HEIGHT * Rtm
    
    return np.column_stack([L, R, C, LFE, Ls, Rs, Lrs, Rrs])


def normalize_audio(audio: np.ndarray, target_peak: float = 0.95) -> Tuple[np.ndarray, float]:
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
# Main Conversion Function
# ============================================================================

def convert_atmos(
    input_path: str,
    output_path: str,
    layout: str = 'stereo',
    include_lfe_in_stereo: bool = False,
    normalize: bool = True,
    bit_depth: int = 24
) -> dict:
    """
    Convert a Dolby Atmos ADM BW64 file to a standard layout.
    
    Args:
        input_path: Path to input ADM BW64 WAV file
        output_path: Path for output WAV file
        layout: Target layout - 'stereo', '5.1', or '7.1'
        include_lfe_in_stereo: Include LFE in stereo downmix
        normalize: Normalize output to prevent clipping
        bit_depth: Output bit depth (16, 24, or 32)
        
    Returns:
        Dict with conversion info (input_channels, output_channels, duration, etc.)
    """
    # Map bit depth to soundfile subtype
    subtype_map = {16: 'PCM_16', 24: 'PCM_24', 32: 'FLOAT'}
    subtype = subtype_map.get(bit_depth, 'PCM_24')
    
    # Read input file
    print(f"Reading: {input_path}")
    data, samplerate = sf.read(input_path)
    
    input_channels = data.shape[1]
    duration = data.shape[0] / samplerate
    
    print(f"  Input: {input_channels} channels, {samplerate} Hz, {duration:.2f}s")
    
    # Perform downmix based on target layout
    layout_lower = layout.lower().replace(' ', '').replace('.', '')
    
    if layout_lower in ('stereo', '20', '0+2+0'):
        output = downmix_to_stereo(data, include_lfe=include_lfe_in_stereo)
        layout_name = 'Stereo (0+2+0)'
    elif layout_lower in ('51', '0+5+0', '51surround'):
        output = downmix_to_51(data)
        layout_name = '5.1 Surround (0+5+0)'
    elif layout_lower in ('71', '0+7+0', '71surround'):
        output = downmix_to_71(data)
        layout_name = '7.1 Surround (0+7+0)'
    else:
        raise ValueError(f"Unknown layout: {layout}. Use 'stereo', '5.1', or '7.1'")
    
    output_channels = output.shape[1]
    print(f"  Output: {output_channels} channels ({layout_name})")
    
    # Normalize if needed
    gain_applied = 1.0
    if normalize:
        output, gain_applied = normalize_audio(output)
        if gain_applied != 1.0:
            print(f"  Normalized: {20 * np.log10(gain_applied):.1f} dB gain")
    
    # Write output
    print(f"Writing: {output_path}")
    sf.write(output_path, output, samplerate, subtype=subtype)
    
    # Get output file size
    output_size = Path(output_path).stat().st_size / (1024 * 1024)
    print(f"  Size: {output_size:.1f} MB")
    
    return {
        'input_path': input_path,
        'output_path': output_path,
        'input_channels': input_channels,
        'output_channels': output_channels,
        'layout': layout_name,
        'samplerate': samplerate,
        'duration': duration,
        'bit_depth': bit_depth,
        'gain_applied_db': 20 * np.log10(gain_applied) if gain_applied != 1.0 else 0,
        'output_size_mb': output_size,
    }


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Dolby Atmos ADM BW64 Downmix Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.wav output_stereo.wav --layout stereo
  %(prog)s input.wav output_51.wav --layout 5.1
  %(prog)s input.wav output_71.wav --layout 7.1
  %(prog)s input.wav output.wav --layout stereo --lfe --bit-depth 16

Layouts:
  stereo, 0+2+0  - 2 channels (L, R)
  5.1, 0+5+0     - 6 channels (L, R, C, LFE, Ls, Rs)
  7.1, 0+7+0     - 8 channels (L, R, C, LFE, Ls, Rs, Lrs, Rrs)
        """
    )
    
    parser.add_argument('input', help='Input ADM BW64 WAV file')
    parser.add_argument('output', help='Output WAV file')
    parser.add_argument(
        '-l', '--layout',
        default='stereo',
        choices=['stereo', '0+2+0', '5.1', '0+5+0', '7.1', '0+7+0'],
        help='Target layout (default: stereo)'
    )
    parser.add_argument(
        '--lfe',
        action='store_true',
        help='Include LFE in stereo downmix (default: exclude)'
    )
    parser.add_argument(
        '--no-normalize',
        action='store_true',
        help='Disable output normalization'
    )
    parser.add_argument(
        '-b', '--bit-depth',
        type=int,
        default=24,
        choices=[16, 24, 32],
        help='Output bit depth (default: 24)'
    )
    
    args = parser.parse_args()
    
    # Check input file exists
    if not Path(args.input).exists():
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)
    
    # Create output directory if needed
    output_dir = Path(args.output).parent
    if output_dir and not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        result = convert_atmos(
            input_path=args.input,
            output_path=args.output,
            layout=args.layout,
            include_lfe_in_stereo=args.lfe,
            normalize=not args.no_normalize,
            bit_depth=args.bit_depth
        )
        
        print(f"\n✅ Success!")
        print(f"   {result['input_channels']}ch → {result['output_channels']}ch ({result['layout']})")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

