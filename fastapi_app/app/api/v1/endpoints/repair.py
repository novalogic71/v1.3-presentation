#!/usr/bin/env python3
"""
Repair endpoints for applying sync offsets to audio with FFmpeg.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class PerChannelRepairRequest(BaseModel):
    file_path: str = Field(..., description="Absolute path to dub file under mount")
    per_channel_results: Dict[str, Dict] = Field(..., description="Per-channel offsets: { role: {offset_seconds: float} }")
    output_path: Optional[str] = Field(None, description="Absolute output path; if omitted, writes next to source")
    keep_duration: bool = Field(default=True, description="Pad/trim to keep original duration")


def _is_safe_path(path: str) -> bool:
    try:
        return str(Path(path).resolve()).startswith(str(Path(settings.MOUNT_PATH).resolve()))
    except Exception:
        return False


@router.post("/repair/per-channel")
async def repair_per_channel(req: PerChannelRepairRequest):
    """Apply per-channel offsets to the input dub file using FFmpeg.

    Supports both multichannel streams and multi-mono MOVs. Video is copied; audio re-encoded to PCM 48k.
    """
    try:
        src = req.file_path
        if not _is_safe_path(src) or not os.path.exists(src) or not os.path.isfile(src):
            raise HTTPException(status_code=400, detail="Invalid or missing file_path")

        out_path = req.output_path
        if not out_path:
            p = Path(src)
            out_path = str(p.with_name(p.stem + "_perch_repaired" + p.suffix))

        # Build filter graph similarly to CLI util
        from sync_analyzer.core.audio_channels import probe_audio_layout
        import subprocess

        layout = probe_audio_layout(src)
        audio_streams = [s for s in layout.get('streams', [])]
        if not audio_streams:
            raise HTTPException(status_code=400, detail="No audio streams found")

        # Original duration
        def _probe_dur(p: str) -> float:
            pr = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', p], capture_output=True, text=True)
            if pr.returncode == 0:
                try:
                    data = json.loads(pr.stdout)
                    return float(data.get('format', {}).get('duration') or 0.0)
                except Exception:
                    return 0.0
            return 0.0

        orig_dur = _probe_dur(src)

        def _get_offset(role: str):
            v = req.per_channel_results.get(role)
            if isinstance(v, dict) and 'offset_seconds' in v:
                return float(v['offset_seconds'])
            return None

        fc_parts = []
        map_parts = []

        mc = next((s for s in audio_streams if int(s.get('channels') or 0) > 1), None)
        if mc:
            si = audio_streams.index(mc)
            ch = int(mc.get('channels') or 0)
            labels = []
            for ci in range(ch):
                src_label = f"c{ci}"
                out_label = f"ch{ci}"
                fc_parts.append(f"[0:a:{si}]pan=mono|c0={src_label}[{out_label}]")
                role_candidates = [
                    {0: 'FL', 1: 'FR', 2: 'FC', 3: 'LFE', 4: 'SL', 5: 'SR'}.get(ci, f"c{ci}"),
                    f"c{ci}",
                ]
                osec = None
                for rname in role_candidates:
                    osec = _get_offset(rname)
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
                    fc_parts.append(f"[{in_lbl}]atrim=start={sec},asetpts=PTS-STARTPTS[{out_lbl2}]")
                labels.append(out_lbl2)
            merged_label = 'aout'
            fc_parts.append("".join(f"[{l}]" for l in labels) + f"amerge=inputs={len(labels)}[{merged_label}]")
            if req.keep_duration and orig_dur > 0:
                fc_parts.append(f"[{merged_label}]apad=whole_dur=1,atrim=duration={orig_dur}[aout]")
            else:
                if merged_label != 'aout':
                    fc_parts.append(f"[{merged_label}]anull[aout]")
            args = [
                'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                '-i', src,
                '-filter_complex', ';'.join(fc_parts),
                '-map', '0:v:0', '-map', '[aout]',
                '-c:v', 'copy',
                '-c:a', 'pcm_s16le', '-ar', '48000', '-ac', str(len(labels)),
                out_path
            ]
        else:
            for ai, _s in enumerate(audio_streams):
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
                    fc_parts.append(f"{in_ref}atrim=start={sec},asetpts=PTS-STARTPTS[{out_lbl}]")
                if req.keep_duration and orig_dur > 0:
                    pad_lbl = f"{out_lbl}p"
                    fc_parts.append(f"[{out_lbl}]apad=whole_dur=1,atrim=duration={orig_dur}[{pad_lbl}]")
                    map_parts += ['-map', f'[{pad_lbl}]']
                else:
                    map_parts += ['-map', f'[{out_lbl}]']
            args = [
                'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                '-i', src,
                '-filter_complex', ';'.join(fc_parts),
                '-map', '0:v:0',
                '-c:v', 'copy',
                '-c:a', 'pcm_s16le', '-ar', '48000',
            ] + map_parts + [out_path]

        logger.info(f"Running per-channel repair: {' '.join(args)}")
        proc = subprocess.run(args, capture_output=True, text=True, timeout=1800)
        if proc.returncode != 0:
            raise HTTPException(status_code=500, detail=proc.stderr.strip() or 'ffmpeg failed')

        size = os.path.getsize(out_path) if os.path.exists(out_path) else 0
        return JSONResponse({
            'success': True,
            'output_file': out_path,
            'output_size': size,
            'keep_duration': req.keep_duration
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Per-channel repair error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

