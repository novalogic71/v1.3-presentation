import os
from pathlib import Path

from sync_analyzer.dolby.iab_wrapper import IabProcessor


def _make_stub(path: Path) -> None:
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)


def test_iab_processor_detects_stub_binaries(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _make_stub(bin_dir / "iab_renderer")

    original_path = os.environ.get("PATH", "")
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{original_path}")

    processor = IabProcessor()
    assert processor.is_available()


def test_extract_and_render_short_circuits_without_mxf(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _make_stub(bin_dir / "iab_renderer")

    original_path = os.environ.get("PATH", "")
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{original_path}")

    processor = IabProcessor()
    calls = []

    output_wav = tmp_path / "out.wav"
    input_iab = tmp_path / "input.iab"
    input_iab.write_bytes(b"iab")

    def _fake_run(cmd, description):
        calls.append(description)
        if "render" in description.lower():
            output_wav.write_bytes(b"pcm")
        return True

    monkeypatch.setattr(processor, "_run_command", _fake_run)

    result = processor.extract_and_render(
        str(input_iab),
        str(output_wav),
        sample_rate=48000,
        channels=1,
    )

    assert result == str(output_wav)
    assert output_wav.exists()
    assert calls == ["IAB render"]


def test_iab_processor_detects_conversion_tool_home(tmp_path, monkeypatch):
    import sync_analyzer.dolby.iab_wrapper as iab_wrapper

    empty_bin = tmp_path / "bin_empty"
    empty_bin.mkdir()
    monkeypatch.setattr(iab_wrapper, "DEFAULT_BIN_DIR", empty_bin)

    tool_home = tmp_path / "dolby-atmos-conversion-tool"
    bin_dir = tool_home / "bin"
    bin_dir.mkdir(parents=True)
    stub = bin_dir / "cmdline_atmos_conversion_tool"
    _make_stub(stub)

    monkeypatch.setenv("ATMOS_CONVERSION_TOOL_HOME", str(tool_home))

    processor = IabProcessor()

    assert processor.is_available()
    assert Path(processor.iab_renderer_path).resolve() == stub.resolve()


def test_is_atmos_file_fallback_handles_iab(monkeypatch, tmp_path):
    from sync_analyzer.core import audio_channels
    import sync_analyzer.dolby.atmos_metadata as atmos_metadata

    dummy = tmp_path / "clip.iab"
    dummy.write_bytes(b"iab")

    monkeypatch.setattr(atmos_metadata, "extract_atmos_metadata", lambda path: None)

    def _fail_ffprobe(_: str):
        raise RuntimeError("ffprobe boom")

    monkeypatch.setattr(audio_channels, "_run_ffprobe_json", _fail_ffprobe)

    assert audio_channels.is_atmos_file(str(dummy))
