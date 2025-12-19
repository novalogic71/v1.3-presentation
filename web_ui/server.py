#!/usr/bin/env python3
"""
Backend server for Professional Audio Sync Analyzer UI
Provides file system access and sync analysis API endpoints
"""

import sys
import os
from pathlib import Path

# Ensure we import from the correct project directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
import time
import asyncio
import subprocess
from flask import Flask, jsonify, request, send_from_directory, send_file
from flask_cors import CORS
import logging
import mimetypes
import json as _json
from sync_analyzer.analysis import analyze

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration
MOUNT_PATH = "/mnt/data"


def _resolve_proxy_cache_dir() -> str:
    """Get a writable proxy cache directory, falling back to /tmp when needed."""
    preferred = Path(
        os.getenv(
            "PROXY_CACHE_DIR",
            os.path.join(os.path.dirname(__file__), "proxy_cache"),
        )
    )
    if not preferred.is_absolute():
        preferred = PROJECT_ROOT / preferred

    fallback = Path(os.getenv("PROXY_CACHE_FALLBACK", "/tmp/sync_proxy_cache"))
    candidates = [preferred]
    if fallback not in candidates:
        candidates.append(fallback)

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            test_file = candidate / ".write_test"
            test_file.write_text(str(time.time()))
            test_file.unlink(missing_ok=True)
            if candidate != preferred:
                logger.warning(f"Proxy cache not writable at {preferred}, using fallback {candidate}")
            return str(candidate.resolve())
        except Exception as e:
            logger.warning(f"Proxy cache directory not usable ({candidate}): {e}")

    raise RuntimeError("No writable proxy cache directory available")


PROXY_CACHE_DIR = _resolve_proxy_cache_dir()
ALLOWED_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".flac",
    ".m4a",
    ".aiff",
    ".ogg",
    ".mov",
    ".mp4",
    ".avi",
    ".mkv",
    ".wmv",
    ".mxf",
    ".ec3",
    ".eac3",
    ".adm",
    ".iab",
}


def is_safe_path(path):
    """Check if path is safe and within allowed directory"""
    try:
        resolved = Path(path).resolve()
        mount_resolved = Path(MOUNT_PATH).resolve()
        return str(resolved).startswith(str(mount_resolved))
    except:
        return False


def get_file_type(filepath):
    """Determine file type based on extension"""
    ext = Path(filepath).suffix.lower()
    if ext in {".wav", ".mp3", ".flac", ".m4a", ".aiff", ".ogg", ".ec3", ".eac3", ".adm", ".iab"}:
        return "audio"
    elif ext in {".mov", ".mp4", ".avi", ".mkv", ".wmv", ".mxf"}:
        return "video"
    else:
        return "file"


def _hash_for_proxy(path: str) -> str:
    import hashlib

    try:
        st = os.stat(path)
        key = f"{path}|{st.st_size}|{int(st.st_mtime)}".encode("utf-8")
    except Exception:
        key = path.encode("utf-8")
    return hashlib.sha1(key).hexdigest()


def _ensure_wav_proxy(src_path: str, role: str) -> str:
    """Create or reuse a WAV proxy for the given source. Returns absolute output path."""
    h = _hash_for_proxy(src_path)
    base = f"{h}_{role}.wav"
    out_path = os.path.join(PROXY_CACHE_DIR, base)
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return out_path

    # Check if file is Atmos format - if yes, use specialized extraction
    try:
        from sync_analyzer.core.audio_channels import is_atmos_file, extract_atmos_bed_stereo

        if is_atmos_file(src_path):
            logger.info(f"Detected Atmos file, using specialized extraction: {Path(src_path).name}")
            # Extract to temp file first for Atmos processing
            temp_atmos_path = out_path + ".atmos_temp.wav"
            extract_atmos_bed_stereo(src_path, temp_atmos_path, sample_rate=48000)
            if os.path.exists(temp_atmos_path) and os.path.getsize(temp_atmos_path) > 0:
                # No volume adjustments - transcode only
                norm_cmd = [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", temp_atmos_path,
                    "-acodec", "pcm_s16le",
                    out_path,
                ]
                logger.info(f"Transcoding Atmos proxy (role={role}): {' '.join(norm_cmd)}")
                norm_result = subprocess.run(norm_cmd, capture_output=True, text=True, timeout=300)
                # Clean up temp file
                try:
                    os.remove(temp_atmos_path)
                except Exception:
                    pass
                if norm_result.returncode == 0 and os.path.exists(out_path):
                    logger.info(f"Atmos proxy created: {out_path}")
                    return out_path
                else:
                    logger.error(f"Atmos transcode failed: {norm_result.stderr}")
                    raise RuntimeError("Atmos transcode failed")
            else:
                logger.error(f"Atmos extraction succeeded but output file missing/empty: {temp_atmos_path}")
                raise RuntimeError("Atmos extraction failed to create output")
    except ImportError as e:
        logger.warning(f"Atmos detection unavailable: {e}, falling back to ffmpeg")
    except Exception as e:
        logger.warning(f"Atmos extraction failed: {e}, falling back to ffmpeg")

    # Transcode to WAV 48k stereo for Chrome/WebAudio compatibility
    # No volume adjustments - play content as-is
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        src_path,
        "-vn",
        "-ac",
        "2",
        "-ar",
        "48000",
        "-acodec",
        "pcm_s16le",
        out_path,
    ]
    logger.info(f"Creating WAV proxy: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        logger.error(f"Proxy creation failed: {result.stderr}")
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    return out_path


def _probe_audio_layout(path: str) -> dict:
    """Minimal ffprobe helper mirroring core util for server-side repair."""
    try:
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            path,
        ]
        pr = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if pr.returncode != 0:
            return {"streams": []}
        data = _json.loads(pr.stdout)
        streams = []
        for s in data.get("streams", []):
            if s.get("codec_type") == "audio":
                streams.append(
                    {
                        "index": s.get("index"),
                        "codec_name": s.get("codec_name"),
                        "channels": int(s.get("channels") or 0),
                        "channel_layout": s.get("channel_layout") or "",
                    }
                )
        return {"streams": streams}
    except Exception:
        return {"streams": []}


def _probe_duration_seconds(path: str) -> float:
    try:
        pr = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if pr.returncode == 0:
            data = _json.loads(pr.stdout)
            return float(data.get("format", {}).get("duration") or 0.0)
    except Exception:
        pass
    return 0.0


@app.route("/api/v1/files/raw")
def api_v1_files_raw():
    """Serve a raw file from the mounted data directory (read-only).

    Mirrors the FastAPI endpoint so the browser can fetch from the same origin
    as the UI without CORS/preflight issues. Validates that the path is under
    MOUNT_PATH to avoid unsafe access.
    """
    path = request.args.get("path", type=str)
    if not path:
        return jsonify({"success": False, "error": "Missing path"}), 400
    if not is_safe_path(path):
        return jsonify({"success": False, "error": "Invalid or unsafe path"}), 400
    if not os.path.exists(path) or not os.path.isfile(path):
        return jsonify({"success": False, "error": "File not found"}), 404
    media_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    try:
        # Use send_file to stream efficiently
        return send_file(
            path,
            mimetype=media_type,
            as_attachment=False,
            download_name=os.path.basename(path),
        )
    except Exception as e:
        logger.error(f"Error serving raw file {path}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/v1/files/proxy-audio")
def api_v1_files_proxy_audio():
    """Transcode source file's audio track to a browser-friendly audio stream.

    Defaults to WAV (PCM) for maximum compatibility. Supports format query:
    - format=wav | mp4 | aac | webm | opus
    - max_duration=600 (optional, limit output to N seconds for preview, default 600 = 10 min)
    """
    path = request.args.get("path", type=str)
    fmt = (request.args.get("format", "wav") or "wav").lower()
    # Max duration for preview - default 10 minutes to avoid huge file timeouts
    max_duration = request.args.get("max_duration", type=int, default=600)
    if max_duration is None or max_duration <= 0:
        max_duration = 600  # Default 10 minutes
    if not path:
        return jsonify({"success": False, "error": "Missing path"}), 400
    if not is_safe_path(path):
        return jsonify({"success": False, "error": "Invalid or unsafe path"}), 400
    if not os.path.exists(path) or not os.path.isfile(path):
        return jsonify({"success": False, "error": "File not found"}), 404
    if fmt not in {"wav", "mp4", "webm", "opus", "aac"}:
        return jsonify({"success": False, "error": "Unsupported target format"}), 400

    # Check if file is Atmos - if yes, extract to temp WAV first
    temp_wav_path = None
    source_path = path
    try:
        from sync_analyzer.core.audio_channels import is_atmos_file, extract_atmos_bed_stereo
        import tempfile as _tempfile

        if is_atmos_file(path):
            logger.info(f"[PROXY-AUDIO] Detected Atmos file for streaming: {os.path.basename(path)}")
            # Create temp WAV for streaming
            temp_wav_path = _tempfile.mktemp(suffix=".wav", prefix="proxy_atmos_stream_")
            extract_atmos_bed_stereo(path, temp_wav_path, sample_rate=48000)
            if os.path.exists(temp_wav_path):
                source_path = temp_wav_path
                logger.info(f"[PROXY-AUDIO] Atmos proxy WAV created for streaming: {temp_wav_path}")
            else:
                logger.warning(f"[PROXY-AUDIO] Atmos extraction failed, falling back to direct ffmpeg")
    except Exception as e:
        logger.warning(f"[PROXY-AUDIO] Atmos detection/extraction failed: {e}, falling back to direct ffmpeg")

    try:
        import subprocess

        # Log the duration limit for debugging
        logger.info(f"[PROXY-AUDIO] Extracting audio with max_duration={max_duration}s from {os.path.basename(path)}")

        # No volume adjustments - play content as-is
        # Use -t to limit duration for preview (avoids timeouts on very long files)
        args = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            source_path,  # Use extracted WAV if Atmos, otherwise original path
            "-t",
            str(max_duration),  # Limit to max_duration seconds
            "-vn",
            "-ac",
            "2",
            "-ar",
            "48000",
        ]
        media_type = "audio/wav"
        if fmt == "wav":
            args += ["-f", "wav", "-acodec", "pcm_s16le", "pipe:1"]
            media_type = "audio/wav"
        elif fmt == "mp4":
            args += [
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "frag_keyframe+empty_moov",
                "-f",
                "mp4",
                "pipe:1",
            ]
            media_type = "audio/mp4"
        elif fmt == "aac":
            args += ["-c:a", "aac", "-b:a", "192k", "-f", "adts", "pipe:1"]
            media_type = "audio/aac"
        elif fmt in {"webm", "opus"}:
            args += ["-c:a", "libopus", "-b:a", "128k", "-f", "webm", "pipe:1"]
            media_type = "audio/webm"

        proc = subprocess.Popen(args, stdout=subprocess.PIPE)

        def generate():
            try:
                while True:
                    chunk = proc.stdout.read(64 * 1024)
                    if not chunk:
                        break
                    yield chunk
            finally:
                try:
                    proc.stdout.close()
                except Exception:
                    pass
                try:
                    proc.terminate()
                except Exception:
                    pass
                # Clean up temp Atmos WAV if created
                if temp_wav_path and os.path.exists(temp_wav_path):
                    try:
                        os.remove(temp_wav_path)
                        logger.info(f"[PROXY-AUDIO] Cleaned up temp Atmos WAV: {temp_wav_path}")
                    except Exception as e:
                        logger.warning(f"[PROXY-AUDIO] Failed to clean up temp WAV: {e}")

        return app.response_class(generate(), mimetype=media_type)
    except FileNotFoundError:
        return jsonify({"success": False, "error": "ffmpeg not found in PATH"}), 500
    except Exception as e:
        logger.error(f"Error proxying audio for {path}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/")
def index():
    """Serve the splash screen landing page"""
    return send_from_directory(".", "splash.html")


@app.route("/app")
def main_app():
    """Serve the main application UI"""
    return send_from_directory(".", "app.html")


@app.route("/PRESENTATION_GUIDE.md")
def presentation_guide():
    """Serve the presentation guide markdown file from parent directory"""
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return send_from_directory(parent_dir, "PRESENTATION_GUIDE.md", mimetype="text/markdown")


@app.route("/<path:filename>")
def serve_static(filename):
    """Serve static files"""
    return send_from_directory(".", filename)


@app.route("/api/files")
def list_files():
    """List files and directories in specified path"""
    path = request.args.get("path", MOUNT_PATH)

    if not is_safe_path(path):
        return jsonify({"success": False, "error": "Invalid or unsafe path"}), 400

    try:
        if not os.path.exists(path):
            return jsonify({"success": False, "error": "Path does not exist"}), 404

        if not os.path.isdir(path):
            return jsonify({"success": False, "error": "Path is not a directory"}), 400

        files = []
        for item in os.listdir(path):
            item_path = os.path.join(path, item)

            try:
                if os.path.isdir(item_path):
                    files.append({"name": item, "type": "directory", "path": item_path})
                elif os.path.isfile(item_path):
                    ext = Path(item).suffix.lower()
                    if ext in ALLOWED_EXTENSIONS:
                        file_type = get_file_type(item)
                        file_info = {
                            "name": item,
                            "type": file_type,
                            "path": item_path,
                            "size": os.path.getsize(item_path),
                            "extension": ext,
                        }
                        files.append(file_info)

                        # Debug logging for Dunkirk files
                        if "Dunkirk" in item:
                            logger.info(
                                f"File detected: {item} | Type: {file_type} | Ext: {ext}"
                            )
            except PermissionError:
                continue  # Skip files we can't access

        return jsonify({"success": True, "path": path, "files": files})

    except PermissionError:
        return jsonify({"success": False, "error": "Permission denied"}), 403
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/analyze", methods=["POST"])
def analyze_sync():
    """Run sync analysis on selected files"""
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    master_path = data.get("master")
    dub_path = data.get("dub")
    methods = data.get("methods", ["mfcc"])

    # Validate paths
    if not master_path or not dub_path:
        return jsonify({
            'success': False,
            'error': 'Both master and dub paths required'
        }), 400
    
    if not is_safe_path(master_path) or not is_safe_path(dub_path):
        return jsonify({
            'success': False,
            'error': 'Invalid or unsafe file paths'
        }), 400
    
    if not os.path.exists(master_path) or not os.path.exists(dub_path):
        return jsonify({
            'success': False,
            'error': 'One or both files do not exist'
        }), 404
    
    try:
        # Use the unified analysis API from the codex branch
        ai_enabled = "ai" in methods
        regular_methods = [m for m in methods if m != "ai"]
        if ai_enabled and not regular_methods:
            regular_methods = ["mfcc"]

        enable_gpu = data.get("enableGpu")
        use_gpu = (enable_gpu is True) or (enable_gpu is None and ai_enabled)

        consensus, _, _ = analyze(
            Path(master_path),
            Path(dub_path),
            methods=regular_methods,
            enable_ai=ai_enabled,
            ai_model=data.get("aiModel", "wav2vec2"),
            use_gpu=use_gpu,
        )

        method_list = list(regular_methods)
        if ai_enabled:
            method_list.append("ai")

        # Coerce numpy/float32 values to native Python types for JSON serialization
        def _f(val):
            try:
                return float(val)
            except Exception:
                return None

        result_data = {
            "offset_seconds": _f(consensus.offset_seconds),
            "confidence": _f(consensus.confidence),
            "quality_score": _f(getattr(consensus, "quality_score", None)),
            "method_used": consensus.method_used,
            "analysis_methods": method_list,
            "per_channel_results": {},
            "recommendations": [],
            "technical_details": {
                "all_methods": method_list,
                "primary_method": consensus.method_used,
                "method_agreement": 1.0,
            },
        }

        logger.info(
            f"Analysis results: {result_data['method_used']} | Methods: {result_data['analysis_methods']} | Offset: {result_data['offset_seconds']:.3f}s"
        )

        return jsonify({"success": True, "result": result_data})

    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/proxy/prepare", methods=["POST"])
def prepare_proxies():
    """Pre-create Chrome/WebAudio compatible proxies for master and dub.

    Request JSON: { master: <abs_path>, dub: <abs_path> }
    Returns URLs served by this UI server: { master_url, dub_url, format }
    """
    data = request.get_json() or {}
    master_path = data.get("master")
    dub_path = data.get("dub")
    if not master_path or not dub_path:
        return jsonify({"success": False, "error": "master and dub required"}), 400
    if not is_safe_path(master_path) or not is_safe_path(dub_path):
        return jsonify({"success": False, "error": "Invalid or unsafe file paths"}), 400
    if not os.path.exists(master_path) or not os.path.exists(dub_path):
        return (
            jsonify({"success": False, "error": "One or both files do not exist"}),
            404,
        )
    try:
        m_out = _ensure_wav_proxy(master_path, "master")
        d_out = _ensure_wav_proxy(dub_path, "dub")
        m_name = os.path.basename(m_out)
        d_name = os.path.basename(d_out)
        return jsonify(
            {
                "success": True,
                "format": "wav",
                "master_url": f"/proxy/{m_name}",
                "dub_url": f"/proxy/{d_name}",
            }
        )
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Proxy creation timed out"}), 408
    except Exception as e:
        logger.error(f"prepare_proxies error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/proxy/<path:filename>")
def serve_proxy(filename):
    """Serve files from the proxy cache directory."""
    full = os.path.join(PROXY_CACHE_DIR, filename)
    if not os.path.abspath(full).startswith(PROXY_CACHE_DIR):
        return jsonify({"success": False, "error": "Invalid path"}), 400
    if not os.path.exists(full):
        return jsonify({"success": False, "error": "Not found"}), 404
    # Assume WAV for now
    return send_from_directory(PROXY_CACHE_DIR, filename, mimetype="audio/wav")


@app.route("/api/status")
def get_status():
    """Get system status"""
    return jsonify(
        {
            "success": True,
            "status": "ready",
            "mount_path": MOUNT_PATH,
            "mount_exists": os.path.exists(MOUNT_PATH),
        }
    )

@app.route("/api/repair", methods=["POST"])
def repair_sync():
    """Repair sync issues in audio/video file"""
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    file_path = data.get("file_path")
    offset_seconds = data.get("offset_seconds")
    preserve_quality = data.get("preserve_quality", True)
    create_backup = data.get("create_backup", True)
    output_dir = data.get("output_dir", "./repaired_sync_files/")
    repair_mode = data.get("repair_mode", "auto")

    # Validate inputs
    if not file_path or offset_seconds is None:
        return (
            jsonify({"success": False, "error": "File path and offset required"}),
            400,
        )

    if not is_safe_path(file_path):
        return jsonify({"success": False, "error": "Invalid or unsafe file path"}), 400

    if not os.path.exists(file_path):
        return jsonify({"success": False, "error": "File does not exist"}), 404

    try:
        # Create output directory - make it absolute from the project root
        if not Path(output_dir).is_absolute():
            # Make relative paths relative to the main project directory, not sync_ui
            output_path = (
                Path("/mnt/data/amcmurray/Sync_dub/Sync_dub_final") / output_dir
            )
        else:
            output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Generate output filename
        input_file = Path(file_path)
        timestamp = int(time.time())
        output_filename = f"{input_file.stem}_repaired_{offset_seconds:.3f}s_{timestamp}{input_file.suffix}"
        output_file_path = output_path / output_filename

        # Create backup if requested
        backup_file_path = None
        if create_backup:
            backup_filename = f"{input_file.stem}_backup_{timestamp}{input_file.suffix}"
            backup_file_path = output_path / backup_filename
            import shutil

            shutil.copy2(file_path, backup_file_path)
            logger.info(f"Backup created: {backup_file_path}")

        # Build FFmpeg command for sync repair
        # Use -itsoffset before the input it applies to
        cmd = [
            "ffmpeg",
            "-i",
            file_path,  # First input (video)
            "-itsoffset",
            str(offset_seconds),
            "-i",
            file_path,  # Second input (audio with offset)
            "-c:v",
            "copy",  # Copy video stream
            "-c:a",
            "copy",  # Copy audio stream
            "-map",
            "0:v:0",  # Use video from first input
            "-map",
            "1:a:0",  # Use audio from second input (with offset)
            "-y",  # Overwrite output
            str(output_file_path),
        ]

        # Quality preservation is already handled above with -c:v copy -c:a copy

        logger.info(f"Running repair command: {' '.join(cmd)}")

        # Execute repair
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
            cwd="/mnt/data/amcmurray/Sync_dub/Sync_dub_final",
        )
        logger.info(f"FFmpeg completed with return code: {result.returncode}")
        if result.stdout:
            logger.info(f"FFmpeg stdout: {result.stdout[:500]}...")  # First 500 chars
        if result.stderr:
            logger.info(f"FFmpeg stderr: {result.stderr[:500]}...")  # First 500 chars

        if result.returncode != 0:
            logger.error(f"FFmpeg repair failed with return code {result.returncode}")
            logger.error(f"FFmpeg stderr: {result.stderr}")
            logger.error(f"FFmpeg stdout: {result.stdout}")

            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"FFmpeg repair failed: {result.stderr}",
                        "details": {
                            "command": " ".join(cmd),
                            "return_code": result.returncode,
                            "stderr": result.stderr,
                            "stdout": result.stdout,
                        },
                    }
                ),
                500,
            )

        # Verify output file was created
        logger.info(f"Checking if output file exists: {output_file_path}")
        logger.info(f"Output file absolute path: {output_file_path.absolute()}")
        logger.info(f"File exists check: {output_file_path.exists()}")

        if not output_file_path.exists():
            logger.error(f"Output file was not created at: {output_file_path}")
            return (
                jsonify({"success": False, "error": "Output file was not created"}),
                500,
            )

        # Get file size for verification
        output_size = output_file_path.stat().st_size
        logger.info(
            f"Repair completed successfully. Output file: {output_file_path}, Size: {output_size}"
        )

        return jsonify(
            {
                "success": True,
                "output_file": str(output_file_path),
                "applied_offset": offset_seconds,
                "backup_created": create_backup,
                "backup_file": str(backup_file_path) if backup_file_path else None,
                "output_size": output_size,
                "repair_mode": repair_mode,
            }
        )

    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Repair operation timed out"}), 408
    except Exception as e:
        logger.error(f"Repair error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/repair/per-channel", methods=["POST"])
def repair_per_channel():
    """Apply per-channel offsets using FFmpeg, preserving video."""
    try:
        data = request.get_json() or {}
        file_path = data.get("file_path")
        per_channel = data.get("per_channel_results") or {}
        output_path = data.get("output_path")
        keep_duration = bool(data.get("keep_duration", True))

        if (
            not file_path
            or not is_safe_path(file_path)
            or not os.path.exists(file_path)
        ):
            return (
                jsonify({"success": False, "error": "Invalid or missing file_path"}),
                400,
            )
        if not isinstance(per_channel, dict) or not per_channel:
            return (
                jsonify({"success": False, "error": "per_channel_results is required"}),
                400,
            )
        if not output_path:
            p = Path(file_path)
            output_path = str(p.with_name(p.stem + "_perch_repaired" + p.suffix))

        info = _probe_audio_layout(file_path)
        streams = [s for s in info.get("streams", [])]
        if not streams:
            return jsonify({"success": False, "error": "No audio streams found"}), 400

        orig_dur = _probe_duration_seconds(file_path)

        def _get_offset(role: str):
            v = per_channel.get(role)
            if isinstance(v, dict) and "offset_seconds" in v:
                try:
                    return float(v["offset_seconds"])
                except Exception:
                    return None
            return None

        fc_parts = []
        map_parts = []

        mc = next((s for s in streams if int(s.get("channels") or 0) > 1), None)
        if mc:
            si = streams.index(mc)
            ch = int(mc.get("channels") or 0)
            labels = []
            for ci in range(ch):
                src_label = f"c{ci}"
                out_label = f"ch{ci}"
                fc_parts.append(f"[0:a:{si}]pan=mono|c0={src_label}[{out_label}]")
                role_candidates = [
                    {0: "FL", 1: "FR", 2: "FC", 3: "LFE", 4: "SL", 5: "SR"}.get(
                        ci, f"c{ci}"
                    ),
                    f"c{ci}",
                ]
                osec = None
                for rn in role_candidates:
                    osec = _get_offset(rn)
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
            merged = "aout"
            fc_parts.append(
                "".join(f"[{l}]" for l in labels)
                + f"amerge=inputs={len(labels)}[{merged}]"
            )
            if keep_duration and orig_dur > 0:
                fc_parts.append(
                    f"[{merged}]apad=whole_dur=1,atrim=duration={orig_dur}[aout]"
                )
            else:
                if merged != "aout":
                    fc_parts.append(f"[{merged}]anull[aout]")
            args = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                file_path,
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
                output_path,
            ]
        else:
            for ai, _s in enumerate(streams):
                in_ref = f"[0:a:{ai}]"
                out_lbl = f"o{ai}"
                osec = _get_offset(f"S{ai}")
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
                    file_path,
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
                + [output_path]
            )

        logger.info(f"Per-channel repair command: {' '.join(args)}")
        result = subprocess.run(args, capture_output=True, text=True, timeout=1800)
        if result.returncode != 0:
            logger.error(f"Per-channel repair failed: {result.stderr}")
            return jsonify({"success": False, "error": result.stderr}), 500
        size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
        return jsonify(
            {
                "success": True,
                "output_file": output_path,
                "output_size": size,
                "keep_duration": keep_duration,
            }
        )
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Per-channel repair timed out"}), 408
    except Exception as e:
        logger.error(f"Per-channel repair error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/logs")
def get_logs():
    """Get recent log entries (placeholder for real logging)"""
    return jsonify(
        {
            "success": True,
            "logs": [
                {
                    "timestamp": "22:30:15",
                    "level": "info",
                    "message": "Server started successfully",
                },
                {
                    "timestamp": "22:30:15",
                    "level": "info",
                    "message": f"File system mounted: {MOUNT_PATH}",
                },
            ],
        }
    )


if __name__ == "__main__":
    if not os.path.exists(MOUNT_PATH):
        logger.warning(f"Mount path {MOUNT_PATH} does not exist")

    logger.info("Starting Professional Audio Sync Analyzer UI Server...")
    logger.info(f"Serving files from: {MOUNT_PATH}")

    # Run the server
    app.run(host="0.0.0.0", port=3002, debug=True, threaded=True)
