#!/usr/bin/env python3
"""
Professional Audio Sync CLI Tool
================================

Command-line interface for the Professional Master-Dub Audio Sync Analyzer.
Provides comprehensive sync detection between master and dubbed audio tracks
using both traditional signal processing and AI-based methods.

Author: AI Audio Engineer
Version: 1.0.0
"""

import argparse
import sys
import logging
from pathlib import Path
from typing import Optional, List

# Import our sync detection modules
try:
    from ..analysis import analyze
    from ..core.audio_channels import probe_audio_layout  # used in repair
except ImportError:  # pragma: no cover - fallback for direct execution
    sys.path.append(str(Path(__file__).parent.parent))
    from analysis import analyze
    from core.audio_channels import probe_audio_layout  # used in repair


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Professional Audio Sync Analyzer - Master vs Dub Sync Detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s master.wav dub.wav
  %(prog)s master.wav dub.wav --methods mfcc onset
  %(prog)s master.wav dub.wav --ai-model wav2vec2 --output-dir ./reports
  %(prog)s master.wav dub.wav --verbose --generate-plots
        """,
    )

    # Required arguments
    parser.add_argument("master", type=Path, help="Path to master audio file")
    parser.add_argument("dub", type=Path, help="Path to dub audio file")

    # Analysis methods
    parser.add_argument(
        "--methods",
        nargs="+",
        choices=["mfcc", "onset", "spectral", "all"],
        default=["all"],
        help="Sync detection methods to use (default: all)",
    )

    # AI options
    parser.add_argument(
        "--enable-ai", action="store_true", help="Enable AI-based sync detection"
    )
    parser.add_argument(
        "--ai-model",
        choices=["wav2vec2", "yamnet", "spectral"],
        default="wav2vec2",
        help="AI model to use for embedding extraction",
    )

    # Audio processing parameters
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=22050,
        help="Target sample rate for analysis (default: 22050)",
    )
    parser.add_argument(
        "--window-size",
        type=float,
        default=30.0,
        help="Analysis window size in seconds (default: 30.0)",
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.7,
        help="Confidence threshold for reliable detection (default: 0.7)",
    )

    # Output options
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./sync_reports"),
        help="Output directory for reports (default: ./sync_reports)",
    )
    parser.add_argument(
        "--no-visualization",
        action="store_true",
        help="Skip generating visualization plots",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Only generate JSON report (no text/plots)",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress console output except errors"
    )

    # Advanced options
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument(
        "--gpu", action="store_true", help="Use GPU acceleration if available"
    )
    # Progress/UI options
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Show a console progress bar during analysis",
    )
    # Multi-channel handling
    parser.add_argument(
        "--channel-strategy",
        choices=["mono_downmix", "per_channel"],
        default="mono_downmix",
        help="How to handle multi-channel audio (default: mono_downmix)",
    )
    parser.add_argument(
        "--target-channels",
        nargs="*",
        default=None,
        help="Subset of channel roles to analyze when using per_channel (e.g., FL FR FC)",
    )
    parser.add_argument(
        "--per-channel-repair-out",
        type=Path,
        default=None,
        help="If set, writes a per-channel time-aligned repaired dub preserving video (-c:v copy)",
    )
    parser.add_argument(
        "--keep-duration",
        action="store_true",
        help="Pad/trim per-channel outputs to keep original dub duration during repair",
    )

    return parser.parse_args()


def validate_inputs(args: argparse.Namespace) -> bool:
    """Validate input arguments and files."""
    if not args.master.exists():
        print(f"❌ Error: Master file not found: {args.master}")
        return False

    if not args.dub.exists():
        print(f"❌ Error: Dub file not found: {args.dub}")
        return False

    # Check file extensions
    audio_extensions = {".wav", ".mp3", ".flac", ".m4a", ".aiff", ".ogg"}
    if args.master.suffix.lower() not in audio_extensions:
        print(f"⚠️  Warning: Master file has unusual extension: {args.master.suffix}")

    if args.dub.suffix.lower() not in audio_extensions:
        print(f"⚠️  Warning: Dub file has unusual extension: {args.dub.suffix}")

    # Validate parameters
    if args.sample_rate < 8000 or args.sample_rate > 96000:
        print(
            f"❌ Error: Sample rate must be between 8000-96000 Hz, got {args.sample_rate}"
        )
        return False

    if args.window_size < 1.0 or args.window_size > 300.0:
        print(
            f"❌ Error: Window size must be between 1-300 seconds, got {args.window_size}"
        )
        return False

    if args.confidence_threshold < 0.0 or args.confidence_threshold > 1.0:
        print(
            f"❌ Error: Confidence threshold must be between 0-1, got {args.confidence_threshold}"
        )
        return False

    return True


def _repair_per_channel(
    dub_input: Path,
    output_path: Path,
    per_channel_results: dict,
    keep_duration: bool = False,
):
    """Apply per-channel delays/advances to the dub input using ffmpeg.

    Strategy:
    - If input has a multichannel audio stream (>1 ch): isolate each channel with pan,
      apply adelay (for positive offsets) or atrim (for negative), then amerge.
    - Else (multi-mono): apply per-stream adelay/atrim and map them as separate audio streams.
    Video is copied. Audio encoded as PCM 16-bit 48kHz for safety.
    """
    import subprocess

    layout = probe_audio_layout(str(dub_input))

    # Probe original duration (format duration)
    def _probe_duration_seconds(p: Path) -> float:
        import subprocess, json as _json

        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            str(p),
        ]
        pr = subprocess.run(cmd, capture_output=True, text=True)
        if pr.returncode == 0:
            try:
                data = _json.loads(pr.stdout)
                return float(data.get("format", {}).get("duration") or 0.0)
            except Exception:
                return 0.0
        return 0.0

    orig_dur = _probe_duration_seconds(dub_input)
    audio_streams = [s for s in layout.get("streams", [])]
    if not audio_streams:
        raise RuntimeError("No audio streams found in dub input")

    fc_parts = []
    map_parts = []

    def get_offset(role: str):
        v = per_channel_results.get(role)
        if isinstance(v, dict) and "offset_seconds" in v:
            return float(v["offset_seconds"])
        return None

    mc = next((s for s in audio_streams if int(s.get("channels") or 0) > 1), None)
    if mc:
        si = audio_streams.index(mc)
        ch = int(mc.get("channels") or 0)
        labels = []
        for ci in range(ch):
            src_label = f"c{ci}"
            out_label = f"ch{ci}"
            fc_parts.append(f"[0:a:{si}]pan=mono|c0={src_label}[{out_label}]")
            # Offset lookup names
            role_candidates = [
                {0: "FL", 1: "FR", 2: "FC", 3: "LFE", 4: "SL", 5: "SR"}.get(
                    ci, f"c{ci}"
                ),
                f"c{ci}",
            ]
            osec = None
            for rname in role_candidates:
                osec = get_offset(rname)
                if osec is not None:
                    break
            in_lbl = out_label
            out_lbl2 = f"{out_label}d"
            if osec is None or abs(osec) < 1e-6:
                fc_parts.append(f"[{in_lbl}]anull[{out_lbl2}]")
            elif osec > 0:
                ms = int(round(osec * 1000))
                fc_parts.append(f"[{in_lbl}]adelay={ms}|{ms}[{out_lbl2}]")
            else:
                sec = abs(osec)
                fc_parts.append(
                    f"[{in_lbl}]atrim=start={sec},asetpts=PTS-STARTPTS[{out_lbl2}]"
                )
            labels.append(out_lbl2)
        inputs_n = len(labels)
        merged_label = "aout"
        fc_parts.append(
            "".join(f"[{l}]" for l in labels)
            + f"amerge=inputs={inputs_n}[{merged_label}]"
        )
        if keep_duration and orig_dur > 0:
            # pad then trim to original duration
            fc_parts.append(
                f"[{merged_label}]apad=whole_dur=1,atrim=duration={orig_dur}[aout]"
            )
        else:
            # leave as-is
            if merged_label != "aout":
                fc_parts.append(f"[{merged_label}]anull[aout]")
        args = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(dub_input),
            "-filter_complex",
            ";".join(fc_parts),
            "-map",
            "0:v:0",
            "-map",
            "[aout]",
            "-c:v",
            "copy",
            "-c:a",
            "pcm_s16le",
            "-ar",
            "48000",
            "-ac",
            str(len(labels)),
            str(output_path),
        ]
    else:
        for ai, _s in enumerate(audio_streams):
            in_ref = f"[0:a:{ai}]"
            out_lbl = f"o{ai}"
            osec = get_offset(f"S{ai}")
            if osec is None or abs(osec) < 1e-6:
                fc_parts.append(f"{in_ref}anull[{out_lbl}]")
            elif osec > 0:
                ms = int(round(osec * 1000))
                fc_parts.append(f"{in_ref}adelay={ms}|{ms}[{out_lbl}]")
            else:
                sec = abs(osec)
                fc_parts.append(
                    f"{in_ref}atrim=start={sec},asetpts=PTS-STARTPTS[{out_lbl}]"
                )
            # Keep duration per stream if requested
            if keep_duration and orig_dur > 0:
                pad_lbl = f"{out_lbl}p"
                fc_parts.append(
                    f"[{out_lbl}]apad=whole_dur=1,atrim=duration={orig_dur}[{pad_lbl}]"
                )
                map_parts += ["-map", f"[{pad_lbl}]"]
            else:
                map_parts += ["-map", f"[{out_lbl}]"]
        args = (
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(dub_input),
                "-filter_complex",
                ";".join(fc_parts),
                "-map",
                "0:v:0",
                "-c:v",
                "copy",
                "-c:a",
                "pcm_s16le",
                "-ar",
                "48000",
            ]
            + map_parts
            + [str(output_path)]
        )

    proc = subprocess.run(args, capture_output=True, text=True, timeout=1800)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "ffmpeg per-channel repair failed")


def print_header():
    """Print application header."""
    print("=" * 80)
    print("🎵 PROFESSIONAL AUDIO SYNC ANALYZER v1.0")
    print("   Master vs Dub Synchronization Detection Tool")
    print("=" * 80)


def print_file_info(master_path: Path, dub_path: Path):
    """Print information about input files."""
    print(f"\n📁 INPUT FILES:")
    print(f"   Master: {master_path.name}")
    print(f"   Dub:    {dub_path.name}")


def format_methods_list(methods: List[str]) -> List[str]:
    """Format methods list, expanding 'all' to available methods."""
    if "all" in methods:
        return ["mfcc", "onset", "spectral"]
    return methods


def print_analysis_summary(consensus_result, methods_used: List[str], ai_enabled: bool):
    """Print analysis summary to console."""
    print(f"\n🔍 ANALYSIS COMPLETE")
    print(f"   Methods Used: {', '.join(methods_used)}")
    if ai_enabled:
        print(f"   AI Enhancement: ✅ Enabled")

    offset_ms = consensus_result.offset_seconds * 1000
    print(f"\n📊 SYNC ANALYSIS RESULTS:")
    print(
        f"   Detected Offset: {consensus_result.offset_seconds:.3f} seconds ({offset_ms:.1f} ms)"
    )
    print(f"   Analysis Method: {consensus_result.method_used}")
    print(f"   Confidence:     {consensus_result.confidence:.2f}")
    print(f"   Quality Score:  {consensus_result.quality_score:.2f}")

    # Provide immediate assessment
    print(f"\n🎯 QUICK ASSESSMENT:")
    abs_offset_ms = abs(offset_ms)
    if abs_offset_ms < 10:
        print(f"   ✅ EXCELLENT - Within broadcast standards (<10ms)")
    elif abs_offset_ms < 40:
        print(f"   ✅ GOOD - Acceptable for most applications (10-40ms)")
    elif abs_offset_ms < 100:
        print(f"   ⚠️  CAUTION - May be noticeable (40-100ms)")
    else:
        print(f"   ❌ CRITICAL - Correction required (>100ms)")

    if consensus_result.confidence < 0.6:
        print(f"   🔬 LOW CONFIDENCE - Manual verification recommended")


def main():
    """Main CLI application."""
    args = parse_arguments()

    # Setup logging
    setup_logging(args.verbose)

    if not args.quiet:
        print_header()
        print_file_info(args.master, args.dub)

    # Validate inputs
    if not validate_inputs(args):
        sys.exit(1)

    try:
        methods = format_methods_list(args.methods)
        consensus_result, _, _ = analyze(
            args.master,
            args.dub,
            methods=methods,
            enable_ai=args.enable_ai,
            ai_model=args.ai_model,
            use_gpu=bool(args.gpu),
        )

        if not args.quiet:
            print_analysis_summary(consensus_result, methods, args.enable_ai)

        if args.per_channel_repair_out:
            print("⚠️  Per-channel repair requires full CLI implementation")

        if consensus_result.confidence < 0.5:
            sys.exit(2)
        sys.exit(0)

    except KeyboardInterrupt:
        print(f"\n⚠️  Analysis interrupted by user.")
        sys.exit(130)

    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
