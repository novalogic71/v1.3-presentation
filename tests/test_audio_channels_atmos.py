import os
from pathlib import Path

import sync_analyzer.core.audio_channels as audio_channels


def test_mxf_triggers_conversion_path(monkeypatch, tmp_path):
    dummy_mxf = tmp_path / "clip.mxf"
    dummy_mxf.write_bytes(b"mxf")
    output_wav = tmp_path / "out.wav"

    created_mp4 = tmp_path / "converted.mp4"
    created_mp4.write_bytes(b"mp4")

    def _fake_convert(atmos_path, output_path=None, **kwargs):
        target = output_path or created_mp4
        Path(target).write_bytes(b"mp4")
        return {"mp4_path": str(target), "metadata": None, "original_path": str(atmos_path)}

    def _fake_run(cmd, capture_output=True, text=True, timeout=600):
        # Last argument is output WAV in this call site
        Path(cmd[-1]).write_bytes(b"wav")
        return type("Proc", (), {"returncode": 0, "stderr": ""})

    import sync_analyzer.dolby.atmos_converter as atmos_converter

    monkeypatch.setattr(atmos_converter, "convert_atmos_to_mp4", _fake_convert)
    monkeypatch.setattr(audio_channels.subprocess, "run", _fake_run)

    result = audio_channels.extract_atmos_bed_mono(str(dummy_mxf), str(output_wav), sample_rate=48000)

    assert result == str(output_wav)
    assert output_wav.exists()
    assert os.path.getsize(output_wav) > 0


def test_iab_converts_to_adm_then_runs_pipeline(monkeypatch, tmp_path):
    dummy_iab = tmp_path / "clip.iab"
    dummy_iab.write_bytes(b"iab")
    output_wav = tmp_path / "out.wav"

    class DummyIabProcessor:
        def __init__(self, *_):
            self.calls = []

        def is_available(self):
            return True

        def convert_to_adm_wav(self, iab_path, output_wav, trim_duration=None, sample_rate=48000):
            Path(output_wav).write_bytes(b"adm")
            return True

    dummy_processor = DummyIabProcessor()

    import sync_analyzer.dolby.atmos_converter as atmos_converter

    def _fake_convert(atmos_path, output_path=None, **kwargs):
        target = output_path or tmp_path / "converted.mp4"
        Path(target).write_bytes(b"mp4")
        return {"mp4_path": str(target), "metadata": None, "original_path": str(atmos_path)}

    def _fake_run(cmd, capture_output=True, text=True, timeout=600):
        Path(cmd[-1]).write_bytes(b"wav")
        return type("Proc", (), {"returncode": 0, "stderr": ""})

    import sys
    import types

    dummy_iab_module = types.SimpleNamespace(IabProcessor=lambda *_, **__: dummy_processor)
    monkeypatch.setitem(sys.modules, "sync_analyzer.dolby.iab_wrapper", dummy_iab_module)
    monkeypatch.setattr(atmos_converter, "convert_atmos_to_mp4", _fake_convert)
    monkeypatch.setattr(audio_channels.subprocess, "run", _fake_run)
    monkeypatch.setattr(audio_channels, "_run_ffprobe_json", lambda path: {"streams": []})

    result = audio_channels.extract_atmos_bed_mono(str(dummy_iab), str(output_wav), sample_rate=48000)

    assert result == str(output_wav)
    assert output_wav.exists()
    assert os.path.getsize(output_wav) > 0


def test_audio_only_mxf_extracts_when_copy_and_aac_fail(monkeypatch, tmp_path):
    dummy_mxf = tmp_path / "clip.mxf"
    dummy_mxf.write_bytes(b"mxf")

    import subprocess
    import sync_analyzer.dolby.atmos_converter as converter

    # Track calls to simulate failures then success
    calls = {"run": 0}

    def fake_run(cmd, capture_output=True, text=True, check=False):
        calls["run"] += 1
        proc = type("Proc", (), {})()
        # 1st call (copy) fails
        if calls["run"] == 1:
            proc.returncode = 1
            proc.stderr = "copy failed"
            if check:
                raise subprocess.CalledProcessError(1, cmd, output="", stderr="copy failed")
            return proc
        # 2nd call (aac) fails via CalledProcessError
        if calls["run"] == 2:
            raise subprocess.CalledProcessError(1, cmd, output="", stderr="aac failed")
        # 3rd call (wav) succeeds
        proc.returncode = 0
        proc.stderr = ""
        # Write wav output for the mux step
        Path(cmd[-1]).write_bytes(b"wav")
        return proc

    def fake_generate(audio_path, output_path, fps, resolution, audio_codec):
        Path(output_path).write_bytes(b"mp4")
        return output_path

    monkeypatch.setattr(converter.subprocess, "run", fake_run)
    monkeypatch.setattr(converter, "generate_black_video_with_audio", fake_generate)
    monkeypatch.setattr(converter, "_has_video_stream", lambda _: True)

    result = converter._convert_mxf_to_mp4(str(dummy_mxf), str(tmp_path / "out.mp4"), fps=24.0, resolution="1920x1080")

    assert result
    path, audio_only = result
    assert audio_only is False
    assert Path(path).exists()
