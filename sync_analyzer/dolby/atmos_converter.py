"""
Dolby Atmos to MP4 Converter

Converts standalone Dolby Atmos audio files (EC3, EAC3, ADM WAV, IAB)
to MP4 format with black video for compatibility with video-based
sync analysis pipelines.

Workflow:
1. Detect Atmos format (EC3/EAC3/ADM WAV)
2. Extract metadata (duration, bed config, sample rate)
3. Generate black video matching audio duration
4. Mux audio and video into MP4 container
5. Preserve Atmos metadata in MP4 atoms
"""

import logging
import math
import os
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from .atmos_metadata import extract_atmos_metadata, is_atmos_codec
from .video_generator import generate_black_video_with_audio

logger = logging.getLogger(__name__)


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[-1]
    return tag


def _cartesian_to_spherical(x: float, y: float, z: float) -> Tuple[float, float, float]:
    radius = math.sqrt(x * x + y * y + z * z)
    azimuth = math.degrees(math.atan2(y, x)) if radius else 0.0
    horizontal = math.hypot(x, y)
    elevation = math.degrees(math.atan2(z, horizontal)) if radius else 0.0
    return azimuth, elevation, radius


def _sanitize_axml_metadata(axml_bytes: bytes) -> Tuple[bytes, bool]:
    try:
        root = ET.fromstring(axml_bytes)
    except ET.ParseError as exc:
        raise ValueError(f"Failed to parse ADM AXML metadata: {exc}") from exc

    changed = False
    namespace_prefix = ""
    if root.tag.startswith("{"):
        namespace_prefix = root.tag.split("}", 1)[0] + "}"

    # Remove unsupported ADM sub-elements
    for parent in list(root.iter()):
        for child in list(parent):
            if _local_name(child.tag) in {"objectDivergence", "jumpPosition"}:
                parent.remove(child)
                changed = True

    # Convert cartesian object positions to spherical so renderer does not need divergence
    for channel in root.iter():
        if _local_name(channel.tag) != "audioChannelFormat":
            continue
        if channel.attrib.get("typeDefinition") != "Objects":
            continue
        for block in list(channel):
            if _local_name(block.tag) != "audioBlockFormat":
                continue
            cartesian_elem = None
            positions = {}
            for elem in list(block):
                local = _local_name(elem.tag)
                if local == "cartesian":
                    cartesian_elem = elem
                elif local == "position":
                    coord = (elem.attrib.get("coordinate") or "").upper()
                    positions[coord] = elem
            if not any(coord in positions for coord in ("X", "Y", "Z")):
                continue
            try:
                x_val = float((positions.get("X").text if positions.get("X") is not None else 0.0))
                y_val = float((positions.get("Y").text if positions.get("Y") is not None else 0.0))
                z_val = float((positions.get("Z").text if positions.get("Z") is not None else 0.0))
            except (TypeError, ValueError):
                continue
            az, el, dist = _cartesian_to_spherical(x_val, y_val, z_val)

            # Remove cartesian coordinates
            for coord in ["X", "Y", "Z"]:
                node = positions.get(coord)
                if node is not None:
                    block.remove(node)

            insert_index = len(list(block))
            if cartesian_elem is not None:
                insert_index = list(block).index(cartesian_elem)
                block.remove(cartesian_elem)

            template_tag = None
            if cartesian_elem is not None:
                template_tag = cartesian_elem.tag
            else:
                for elem in block:
                    if _local_name(elem.tag) == "position":
                        template_tag = elem.tag
                        break
            pos_tag = "position"
            if template_tag and "}" in template_tag:
                namespace = template_tag.split("}", 1)[0] + "}"
                pos_tag = f"{namespace}position"
            elif namespace_prefix:
                pos_tag = f"{namespace_prefix}position"

            def _make_position(coord: str, value: float) -> ET.Element:
                elem = ET.Element(pos_tag)
                elem.set("coordinate", coord)
                elem.text = f"{value:.10f}"
                return elem

            new_nodes = [
                _make_position("azimuth", az),
                _make_position("elevation", el),
                _make_position("distance", dist)
            ]
            for offset, node in enumerate(new_nodes):
                block.insert(insert_index + offset, node)
            changed = True

    # Drop any remaining cartesian markers so BS.2127 renderer sees spherical coords only
    for block in root.iter():
        if _local_name(block.tag) != "audioBlockFormat":
            continue
        removed_any = False
        for elem in list(block):
            if _local_name(elem.tag) == "cartesian":
                block.remove(elem)
                removed_any = True
        if removed_any:
            changed = True

    # Remove any residual cartesian axis positions
    for block in root.iter():
        if _local_name(block.tag) != "audioBlockFormat":
            continue
        cleaned = False
        for elem in list(block):
            if _local_name(elem.tag) == "position":
                coord = (elem.attrib.get("coordinate") or "").upper()
                if coord in {"X", "Y", "Z"}:
                    block.remove(elem)
                    cleaned = True
        if cleaned:
            changed = True

    # Ensure every block has at least one spherical position entry
    for block in root.iter():
        if _local_name(block.tag) != "audioBlockFormat":
            continue
        if any(_local_name(elem.tag) == "position" for elem in block):
            continue
        for coord, value in (("azimuth", 0.0), ("elevation", 0.0), ("distance", 1.0)):
            tag = f"{namespace_prefix}position" if namespace_prefix else "position"
            elem = ET.Element(tag)
            elem.set("coordinate", coord)
            elem.text = f"{value:.10f}"
            block.append(elem)
        changed = True

    if not changed:
        return axml_bytes, False

    if namespace_prefix:
        ET.register_namespace("", namespace_prefix.strip("{}"))
    sanitized = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return sanitized, True


def _extract_axml_chunk(adm_path: Path) -> Optional[bytes]:
    with adm_path.open("rb") as handle:
        header = handle.read(12)
        if len(header) < 12 or header[:4] != b"RIFF" or header[8:12] != b"WAVE":
            return None
        while True:
            chunk_header = handle.read(8)
            if not chunk_header:
                break
            chunk_id = chunk_header[:4]
            chunk_size = int.from_bytes(chunk_header[4:], "little")
            if chunk_id == b"data":
                skip = chunk_size + (chunk_size % 2)
                handle.seek(skip, os.SEEK_CUR)
                continue
            chunk_data = handle.read(chunk_size)
            if chunk_size % 2:
                handle.read(1)
            if chunk_id == b"axml":
                return chunk_data
    return None


def _rewrite_bw64_with_new_axml(
    src_path: Path,
    dest_path: Path,
    axml_bytes: bytes,
    drop_dbmd: bool = True
) -> None:
    buffer_size = 4 * 1024 * 1024
    with src_path.open("rb") as src, dest_path.open("wb") as dst:
        riff_header = src.read(12)
        if len(riff_header) < 12 or riff_header[:4] != b"RIFF" or riff_header[8:12] != b"WAVE":
            raise ValueError("Input file is not a valid BW64/RIFF file")
        dst.write(b"RIFF")
        dst.write(b"\x00\x00\x00\x00")  # placeholder
        dst.write(b"WAVE")

        replaced_axml = False
        while True:
            chunk_header = src.read(8)
            if not chunk_header:
                break
            if len(chunk_header) < 8:
                raise IOError("Unexpected end of file while reading chunk header")
            chunk_id = chunk_header[:4]
            chunk_size = int.from_bytes(chunk_header[4:], "little")
            if chunk_id == b"data":
                dst.write(chunk_id)
                dst.write(chunk_size.to_bytes(4, "little"))
                remaining = chunk_size
                while remaining > 0:
                    piece = src.read(min(buffer_size, remaining))
                    if not piece:
                        raise IOError("Unexpected end of data chunk")
                    dst.write(piece)
                    remaining -= len(piece)
                if chunk_size % 2:
                    pad_byte = src.read(1) or b"\x00"
                    dst.write(pad_byte)
                continue

            chunk_data = src.read(chunk_size)
            if len(chunk_data) < chunk_size:
                raise IOError("Unexpected end of chunk data")
            pad_byte = b""
            if chunk_size % 2:
                pad_byte = src.read(1)

            if chunk_id == b"axml":
                chunk_data = axml_bytes
                chunk_size = len(chunk_data)
                pad_byte = b"\x00" if chunk_size % 2 else b""
                replaced_axml = True
            elif drop_dbmd and chunk_id == b"dbmd":
                continue

            dst.write(chunk_id)
            dst.write(chunk_size.to_bytes(4, "little"))
            dst.write(chunk_data)
            if chunk_size % 2:
                dst.write(pad_byte or b"\x00")

        if not replaced_axml:
            raise ValueError("Failed to locate axml chunk while rewriting BW64 file")

        final_size = dst.tell() - 8
        dst.seek(4)
        dst.write(final_size.to_bytes(4, "little"))


def _sanitize_adm_for_ebu(adm_path: Path) -> Optional[Path]:
    try:
        axml_chunk = _extract_axml_chunk(adm_path)
        if not axml_chunk:
            logger.debug("ADM file has no axml chunk; skipping sanitization for %s", adm_path)
            return None
        sanitized_axml, changed = _sanitize_axml_metadata(axml_chunk)
        if not changed:
            return None
        fd, temp_path = tempfile.mkstemp(suffix=".wav", prefix="adm_sanitized_")
        os.close(fd)
        temp_path_obj = Path(temp_path)
        _rewrite_bw64_with_new_axml(adm_path, temp_path_obj, sanitized_axml, drop_dbmd=True)
        logger.info("Sanitized ADM metadata (removed ObjectDivergence/cartesian) -> %s", temp_path_obj)
        return temp_path_obj
    except Exception as exc:
        logger.warning("Failed to sanitize ADM metadata for %s: %s", adm_path, exc)
        return None


def is_atmos_file(file_path: str) -> bool:
    """
    Check if file is a Dolby Atmos audio file

    Supported formats:
    - .ec3, .eac3 (E-AC-3 bitstreams)
    - .adm (ADM BWF WAV)
    - .iab (IAB - Immersive Audio Bitstream)
    - .mxf (MXF containers with Atmos/IAB)
    - .wav with Atmos codec
    - .mp4, .mov with Atmos audio

    Args:
        file_path: Path to audio file

    Returns:
        True if file is Atmos, False otherwise
    """
    try:
        file_path = Path(file_path)

        # Check extension first (but NOT .mxf - must probe for IAB)
        ext = file_path.suffix.lower()
        if ext in ['.ec3', '.eac3', '.adm', '.iab']:
            return True

        # For .mxf and other extensions, probe with ffprobe
        # NOTE: .mxf files are only Atmos if they contain IAB (detected via ffprobe metadata)
        #       Regular MXF with PCM audio should be handled by FFmpeg directly.
        metadata = extract_atmos_metadata(str(file_path))
        if metadata:
            # Check if it's ADM WAV or IAB (NOT is_mxf alone!)
            if metadata.is_adm_wav or metadata.is_iab:
                return True
            # Also check codec (for EC3/EAC3 in MP4/MOV containers)
            return is_atmos_codec(metadata.codec)

        return False

    except Exception as e:
        logger.debug(f"Atmos detection failed for {file_path}: {e}")
        return False


def convert_atmos_to_mp4(
    atmos_path: str,
    output_path: Optional[str] = None,
    fps: float = 24.0,
    resolution: str = "1920x1080",
    preserve_original: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Convert Atmos audio file to MP4 with black video

    Args:
        atmos_path: Path to Atmos audio file
        output_path: Output MP4 path (auto-generated if None)
        fps: Video frame rate (default: 24.0)
        resolution: Video resolution (default: 1920x1080)
        preserve_original: Whether to preserve original Atmos file

    Returns:
        Dictionary with conversion results:
        {
            "mp4_path": str,
            "metadata": AtmosMetadata,
            "original_path": str (if preserved)
        }
        Returns None if conversion fails
    """
    try:
        atmos_path = Path(atmos_path).resolve()
        if not atmos_path.exists():
            logger.error(f"Atmos file not found: {atmos_path}")
            return None

        # Verify it's an Atmos file
        if not is_atmos_file(str(atmos_path)):
            logger.error(f"File is not a recognized Atmos format: {atmos_path}")
            return None

        # Extract metadata
        logger.info(f"Converting Atmos file to MP4: {atmos_path.name}")
        metadata = extract_atmos_metadata(str(atmos_path))
        if not metadata:
            logger.error(f"Failed to extract Atmos metadata from {atmos_path}")
            return None

        logger.info(f"Atmos metadata: {metadata.bed_configuration}, "
                   f"{metadata.codec}, {metadata.sample_rate}Hz, "
                   f"Duration: {metadata.duration:.2f}s")

        # Determine conversion strategy based on file type
        ext = atmos_path.suffix.lower()

        audio_only = False
        if metadata.is_iab:
            mp4_path = _convert_iab_to_mp4(str(atmos_path), output_path, fps, resolution)
        elif ext in ['.ec3', '.eac3']:
            mp4_path = _convert_ec3_to_mp4(str(atmos_path), output_path, fps, resolution)
        elif ext == '.mxf':
            result = _convert_mxf_to_mp4(str(atmos_path), output_path, fps, resolution)
            if result is None:
                mp4_path = None
            else:
                mp4_path, audio_only = result
        elif ext == '.adm' or (ext == '.wav' and metadata.is_adm_wav):
            mp4_path = _convert_adm_wav_to_mp4(str(atmos_path), output_path, fps, resolution)
        elif ext in ['.mp4', '.mov']:
            mp4_path = _add_black_video_to_mp4(str(atmos_path), output_path, fps, resolution)
        elif ext == '.wav':
            mp4_path = _convert_wav_to_mp4(str(atmos_path), output_path, fps, resolution)
        else:
            logger.error(f"Unsupported Atmos file format: {ext}")
            return None

        if not mp4_path:
            logger.error(f"Failed to convert {atmos_path} to MP4")
            return None

        # Optionally preserve original file
        original_path = None
        if preserve_original:
            original_path = str(atmos_path)
            logger.info(f"Original Atmos file preserved: {original_path}")

        logger.info(f"Atmos conversion complete: {mp4_path}")

        return {
            "mp4_path": mp4_path,
            "metadata": metadata,
            "original_path": original_path,
            "audio_only": audio_only,
        }

    except Exception as e:
        logger.error(f"Failed to convert Atmos file {atmos_path}: {e}")
        return None


def _convert_ec3_to_mp4(
    ec3_path: str,
    output_path: Optional[str],
    fps: float,
    resolution: str
) -> Optional[str]:
    """
    Convert EC3/EAC3 bitstream to MP4 with black video

    Strategy: Use FFmpeg to directly mux EC3 into MP4 with generated black video

    Args:
        ec3_path: Path to EC3/EAC3 file
        output_path: Output MP4 path
        fps: Video frame rate
        resolution: Video resolution

    Returns:
        Path to MP4 file or None
    """
    try:
        if output_path is None:
            output_path = tempfile.mktemp(suffix=".mp4", prefix="atmos_ec3_")

        logger.info(f"Converting EC3 to MP4: {ec3_path}")

        # Use video_generator to create MP4 with black video and EC3 audio
        # EC3 audio will be copied without re-encoding to preserve Atmos metadata
        mp4_path = generate_black_video_with_audio(
            ec3_path,
            output_path,
            fps=fps,
            resolution=resolution,
            audio_codec="copy"  # Preserve EC3 bitstream
        )

        return mp4_path

    except Exception as e:
        logger.error(f"EC3 to MP4 conversion failed: {e}")
        return None


def _convert_adm_wav_to_mp4(
    adm_path: str,
    output_path: Optional[str],
    fps: float,
    resolution: str
) -> Optional[str]:
    """
    Convert ADM BWF WAV to MP4 with black video

    ADM WAV files contain PCM audio with ADM metadata in BWF chunks.
    We'll downmix the bed channels to stereo, then encode to AAC for MP4.

    Args:
        adm_path: Path to ADM WAV file
        output_path: Output MP4 path
        fps: Video frame rate
        resolution: Video resolution

    Returns:
        Path to MP4 file or None
    """
    cleanup_paths = []
    try:
        if output_path is None:
            output_path = tempfile.mktemp(suffix=".mp4", prefix="atmos_adm_")

        logger.info(f"Converting ADM WAV to MP4: {adm_path}")

        # Step 1: Downmix multichannel ADM WAV to stereo
        # ADM files can have 72+ channels, FFmpeg can't encode these directly to EAC3
        # We extract the bed (typically first 8-16 channels) and downmix to stereo
        
        temp_stereo = tempfile.mktemp(suffix=".wav", prefix="adm_stereo_")
        
        logger.info("Rendering ADM BWF WAV using EBU ADM Toolbox...")
        config_path = Path(__file__).parent / "adm_render_config.json"
        if not config_path.exists():
            logger.error(f"ADM render config not found: {config_path}")
            return None

        adm_input_path = Path(adm_path)
        sanitized_adm = _sanitize_adm_for_ebu(adm_input_path)
        if sanitized_adm:
            cleanup_paths.append(sanitized_adm)
            adm_input_path = sanitized_adm

        eat_process_bin = Path(__file__).parent / "bin" / "eat-process"
        if not eat_process_bin.exists():
            logger.error(f"eat-process binary not found: {eat_process_bin}")
            logger.warning("Falling back to simple channel extraction...")
            eat_cmd = ["false"]
        else:
            eat_cmd = [
                str(eat_process_bin),
                str(config_path),
                "-o", "input.path", str(adm_input_path),
                "-o", "output.path", temp_stereo
            ]

        logger.info(f"Running EBU ADM Toolbox: {' '.join(eat_cmd)}")
        result = subprocess.run(eat_cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0 or not Path(temp_stereo).exists():
            logger.error(f"EBU ADM Toolbox rendering failed: {result.stderr}")
            logger.warning("Falling back to full-channel mixdown...")
            
            # Fallback: Use ITU-R BS.775 professional downmix via atmos_downmix module
            try:
                from .atmos_downmix import downmix_to_stereo_file
                result = downmix_to_stereo_file(
                    adm_path,
                    temp_stereo,
                    include_lfe=False,
                    normalize=True,
                    bit_depth=16
                )
                if result is None:
                    logger.error("Professional downmix fallback failed")
                    return None
                logger.info("Fallback ITU-R BS.775 downmix to stereo completed")
            except Exception as e:
                logger.error(f"Fallback professional downmix failed: {e}")
                return None
        else:
            logger.info(f"✅ ADM rendered to stereo: {temp_stereo}")
            logger.debug(f"eat-process output: {result.stdout}")
        
        # Step 2: Encode stereo WAV to EC-3
        temp_ec3 = tempfile.mktemp(suffix=".ec3", prefix="adm_ec3_")
        logger.info(f"Encoding stereo WAV to EC-3...")
        
        ec3_cmd = [
            "ffmpeg",
            "-i", temp_stereo,
            "-c:a", "eac3",
            "-b:a", "192k",
            "-y",
            temp_ec3
        ]
        
        result = subprocess.run(ec3_cmd, capture_output=True, text=True)
        if result.returncode != 0 or not Path(temp_ec3).exists():
            logger.error(f"Failed to encode EC-3: {result.stderr}")
            return None
        
        logger.info(f"EC-3 created: {temp_ec3}")
        
        # Step 3: Use dlb_mp4base mp4muxer to create MP4
        temp_mp4_audio_only = tempfile.mktemp(suffix=".mp4", prefix="atmos_audio_")
        logger.info(f"Creating MP4 with dlb_mp4base mp4muxer...")
        
        mp4muxer_cmd = [
            "mp4muxer",
            "-i", temp_ec3,
            "-o", temp_mp4_audio_only,
            "--mpeg4-comp-brand", "mp42,iso6,isom,msdh,dby1",
            "--overwrite"
        ]
        
        result = subprocess.run(mp4muxer_cmd, capture_output=True, text=True)
        if result.returncode != 0 or not Path(temp_mp4_audio_only).exists():
            logger.error(f"mp4muxer failed: {result.stderr}")
            return None
        
        logger.info(f"MP4 (audio-only) created: {temp_mp4_audio_only}")
        
        # Step 4: Add black video track
        logger.info(f"Adding black video track...")
        
        # Get audio duration
        duration_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                       "-of", "default=noprint_wrappers=1:nokey=1", temp_mp4_audio_only]
        duration_result = subprocess.run(duration_cmd, capture_output=True, text=True)
        duration = float(duration_result.stdout.strip())
        
        width, height = resolution.split('x')
        
        video_cmd = [
            "ffmpeg",
            "-f", "lavfi",
            "-i", f"color=black:{width}x{height}:d={duration}:r={fps}",
            "-i", temp_mp4_audio_only,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-c:a", "copy",
            "-shortest",
            "-y",
            output_path
        ]
        
        result = subprocess.run(video_cmd, capture_output=True, text=True)
        if result.returncode != 0 or not Path(output_path).exists():
            logger.error(f"Failed to add black video: {result.stderr}")
            return None
        
        logger.info(f"✅ Final MP4 created: {output_path}")
        
        # Clean up temp files
        for temp_file in [temp_stereo, temp_ec3, temp_mp4_audio_only]:
            try:
                Path(temp_file).unlink()
            except:
                pass

        return output_path

    except Exception as e:
        logger.error(f"ADM WAV to MP4 conversion failed: {e}")
        return None
    finally:
        for temp_path in cleanup_paths:
            try:
                Path(temp_path).unlink()
            except Exception:
                pass


def _has_video_stream(file_path: str) -> bool:
    """Return True if file has at least one video stream."""
    try:
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-select_streams",
            "v",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            file_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return bool(result.stdout.strip())
    except Exception:
        return False


def _convert_iab_to_mp4(
    iab_path: str,
    output_path: Optional[str],
    fps: float,
    resolution: str
) -> Optional[str]:
    """
    Convert IAB (Immersive Audio Bitstream) to MP4 with black video

    IAB is SMPTE ST 2098-2 object-based audio format.
    FFmpeg may have limited IAB support, so this uses best-effort conversion.

    Args:
        iab_path: Path to IAB file
        output_path: Output MP4 path
        fps: Video frame rate
        resolution: Video resolution

    Returns:
        Path to MP4 file or None
    """
    temp_stereo_wav: Optional[str] = None
    try:
        if output_path is None:
            output_path = tempfile.mktemp(suffix=".mp4", prefix="atmos_iab_")

        logger.info(f"Converting IAB to MP4: {iab_path}")

        from .iab_wrapper import IabProcessor

        iab_processor = IabProcessor()
        if not iab_processor.is_available():
            logger.warning("IAB tools not available, using fallback conversion path")
            return _convert_iab_fallback(iab_path, output_path, fps, resolution)

        # Extract and render to stereo WAV first to avoid FFmpeg IAB issues
        temp_stereo_wav = tempfile.mktemp(suffix=".wav", prefix="iab_rendered_")
        rendered_path = iab_processor.extract_and_render(
            iab_path,
            temp_stereo_wav,
            sample_rate=48000,
            channels=2,
        )

        if not rendered_path or not os.path.exists(temp_stereo_wav):
            logger.error("IAB render failed; falling back to FFmpeg path")
            return _convert_iab_fallback(iab_path, output_path, fps, resolution)

        mp4_path = generate_black_video_with_audio(
            temp_stereo_wav,
            output_path,
            fps=fps,
            resolution=resolution,
            audio_codec="aac"
        )

        return mp4_path

    except Exception as e:
        logger.error(f"IAB to MP4 conversion failed: {e}")
        return None
    finally:
        if temp_stereo_wav:
            try:
                Path(temp_stereo_wav).unlink()
            except Exception:
                pass


def _convert_iab_fallback(
    iab_path: str,
    output_path: Optional[str],
    fps: float,
    resolution: str
) -> Optional[str]:
    message = (
        "IAB decoding requires a Dolby renderer (e.g., cmdline_atmos_conversion_tool). "
        "Install the tool and place the binary in sync_analyzer/dolby/bin. "
        f"Source file: {iab_path}"
    )
    logger.error(message)
    raise RuntimeError(message)


def _convert_mxf_to_mp4(
    mxf_path: str,
    output_path: Optional[str],
    fps: float,
    resolution: str
) -> Optional[Tuple[str, bool]]:
    """
    Convert MXF container to MP4

    MXF may already have video; extract audio and add black video if needed.

    Args:
        mxf_path: Path to MXF file
        output_path: Output MP4 path
        fps: Video frame rate
        resolution: Video resolution

    Returns:
        Path to MP4 file or None
    """
    try:
        if output_path is None:
            output_path = tempfile.mktemp(suffix=".mp4", prefix="atmos_mxf_")

        logger.info(f"Converting MXF to MP4: {mxf_path}")

        # Detect if MXF already has video; if audio-only, extract to WAV and return
        if not _has_video_stream(mxf_path):
            target_wav_path = Path(output_path).with_suffix(".wav") if output_path else Path(tempfile.mktemp(suffix=".wav", prefix="atmos_mxf_audio_only_"))
            target_wav_path.parent.mkdir(parents=True, exist_ok=True)
            wav_cmd = [
                "ffmpeg",
                "-i", mxf_path,
                "-vn",
                "-ac", "2",
                "-ar", "48000",
                "-c:a", "pcm_s16le",
                "-y",
                str(target_wav_path),
            ]
            wav_result = subprocess.run(wav_cmd, capture_output=True, text=True)
            if wav_result.returncode != 0 or not target_wav_path.exists():
                logger.error(f"Audio-only MXF WAV extraction failed: {wav_result.stderr}")
                return None
            logger.info(f"Extracted audio-only MXF to WAV: {target_wav_path}")
            return str(target_wav_path), True

        # Extract audio from MXF (with video)
        temp_audio = tempfile.mktemp(suffix=".audio.m4a")

        # Extract audio track (preserve codec if possible)
        extract_cmd = [
            "ffmpeg",
            "-i", mxf_path,
            "-vn",  # No video
            "-c:a", "copy",  # Try to copy audio codec
            "-y",
            temp_audio
        ]

        result = subprocess.run(extract_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning("Failed to copy audio codec, re-encoding to AAC")
            # Fallback: re-encode to AAC (preserve -y position)
            extract_cmd = [
                "ffmpeg",
                "-i", mxf_path,
                "-vn",
                "-c:a", "aac",
                "-y",
                temp_audio
            ]
            try:
                subprocess.run(extract_cmd, capture_output=True, text=True, check=True)
                audio_codec = "copy"
            except subprocess.CalledProcessError as exc:
                logger.error(f"MXF audio re-encode failed: {exc.stderr}")
                # Final fallback: extract to WAV so we can still mux
                temp_wav = tempfile.mktemp(suffix=".wav", prefix="atmos_mxf_audio_")
                wav_cmd = [
                    "ffmpeg",
                    "-i", mxf_path,
                    "-vn",
                    "-ac", "2",
                    "-ar", "48000",
                    "-c:a", "pcm_s16le",
                    "-y",
                    temp_wav,
                ]
                wav_result = subprocess.run(wav_cmd, capture_output=True, text=True)
                if wav_result.returncode != 0:
                    logger.error(f"MXF WAV extraction failed: {wav_result.stderr}")
                    return None
                temp_audio = temp_wav
                audio_codec = "aac"

        # Generate MP4 with black video and extracted audio
        mp4_path = generate_black_video_with_audio(
            temp_audio,
            output_path,
            fps=fps,
            resolution=resolution,
            audio_codec=audio_codec
        )

        # Clean up temp audio
        Path(temp_audio).unlink(missing_ok=True)

        return mp4_path, False

    except Exception as e:
        logger.error(f"MXF to MP4 conversion failed: {e}")
        return None


def _convert_wav_to_mp4(
    wav_path: str,
    output_path: Optional[str],
    fps: float,
    resolution: str
) -> Optional[str]:
    """
    Convert standard WAV to MP4 with black video

    Args:
        wav_path: Path to WAV file
        output_path: Output MP4 path
        fps: Video frame rate
        resolution: Video resolution

    Returns:
        Path to MP4 file or None
    """
    try:
        if output_path is None:
            output_path = tempfile.mktemp(suffix=".mp4", prefix="atmos_wav_")

        logger.info(f"Converting WAV to MP4: {wav_path}")

        # Encode to AAC for compatibility
        mp4_path = generate_black_video_with_audio(
            wav_path,
            output_path,
            fps=fps,
            resolution=resolution,
            audio_codec="aac"
        )

        return mp4_path

    except Exception as e:
        logger.error(f"WAV to MP4 conversion failed: {e}")
        return None


def _add_black_video_to_mp4(
    input_mp4: str,
    output_path: Optional[str],
    fps: float,
    resolution: str
) -> Optional[str]:
    """
    Add black video to existing MP4 with Atmos audio

    If MP4 already has video, replace it with black video.
    If MP4 only has audio, add black video.

    Args:
        input_mp4: Path to input MP4 file
        output_path: Output MP4 path
        fps: Video frame rate
        resolution: Video resolution

    Returns:
        Path to MP4 file or None
    """
    try:
        if output_path is None:
            output_path = tempfile.mktemp(suffix=".mp4", prefix="atmos_mp4_")

        logger.info(f"Adding black video to MP4: {input_mp4}")

        # Extract audio from input MP4
        temp_audio = tempfile.mktemp(suffix=".audio.m4a")

        # Extract audio track
        extract_cmd = [
            "ffmpeg",
            "-i", input_mp4,
            "-vn",  # No video
            "-c:a", "copy",  # Copy audio codec
            "-y",
            temp_audio
        ]

        subprocess.run(extract_cmd, capture_output=True, text=True, check=True)

        # Generate MP4 with black video and extracted audio
        mp4_path = generate_black_video_with_audio(
            temp_audio,
            output_path,
            fps=fps,
            resolution=resolution,
            audio_codec="copy"
        )

        # Clean up temp audio
        Path(temp_audio).unlink(missing_ok=True)

        return mp4_path

    except Exception as e:
        logger.error(f"Failed to add black video to MP4: {e}")
        return None


def extract_atmos_audio(mp4_path: str, output_path: Optional[str] = None) -> Optional[str]:
    """
    Extract Atmos audio from MP4 file

    Args:
        mp4_path: Path to MP4 with Atmos audio
        output_path: Output audio file path (auto-generated if None)

    Returns:
        Path to extracted audio file or None
    """
    try:
        mp4_path = Path(mp4_path).resolve()
        if not mp4_path.exists():
            logger.error(f"MP4 file not found: {mp4_path}")
            return None

        # Determine output format based on codec
        metadata = extract_atmos_metadata(str(mp4_path))
        if not metadata:
            logger.error(f"Failed to extract metadata from {mp4_path}")
            return None

        # Create output path
        if output_path is None:
            if metadata.codec in ['eac3', 'ec3']:
                output_path = tempfile.mktemp(suffix=".ec3", prefix="atmos_audio_")
            else:
                output_path = tempfile.mktemp(suffix=".m4a", prefix="atmos_audio_")

        logger.info(f"Extracting Atmos audio from {mp4_path.name}")

        # Extract audio using ffmpeg
        cmd = [
            "ffmpeg",
            "-i", str(mp4_path),
            "-vn",  # No video
            "-c:a", "copy",  # Copy audio codec
            "-y",
            output_path
        ]

        subprocess.run(cmd, capture_output=True, text=True, check=True)

        if not Path(output_path).exists():
            logger.error("Audio extraction completed but file not found")
            return None

        logger.info(f"Atmos audio extracted: {output_path}")
        return output_path

    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg failed to extract audio: {e.stderr}")
        return None
    except Exception as e:
        logger.error(f"Failed to extract Atmos audio: {e}")
        return None


if __name__ == "__main__":
    # Test Atmos conversion
    import sys

    if len(sys.argv) < 2:
        print("Usage: python atmos_converter.py <atmos_file> [output_mp4]")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO)

    atmos_file = sys.argv[1]
    output_mp4 = sys.argv[2] if len(sys.argv) > 2 else None

    result = convert_atmos_to_mp4(atmos_file, output_mp4)

    if result:
        print("\n" + "="*60)
        print("Atmos Conversion Success")
        print("="*60)
        print(f"MP4 Path: {result['mp4_path']}")
        print(f"Bed Config: {result['metadata'].bed_configuration}")
        print(f"Sample Rate: {result['metadata'].sample_rate}Hz")
        print(f"Duration: {result['metadata'].duration:.2f}s")
        if result['original_path']:
            print(f"Original: {result['original_path']}")
        print("="*60)
    else:
        print(f"\nFailed to convert {atmos_file}")
        sys.exit(1)
