import pytest

from sync_analyzer.core.audio_channels import _layout_roles


def test_layout_roles_stereo():
    roles = _layout_roles("stereo", 2)
    assert roles == ["FL", "FR"]


def test_layout_roles_51():
    roles = _layout_roles("5.1", 6)
    assert roles == ["FL", "FR", "FC", "LFE", "SL", "SR"]


def test_layout_roles_unknown_fallback():
    roles = _layout_roles("weird-layout", 3)
    assert roles == ["c0", "c1", "c2"]

