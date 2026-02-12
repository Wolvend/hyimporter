from __future__ import annotations

from pathlib import Path

from hyimporter.config import PathsConfig


def test_paths_config_honors_direct_env_overrides(monkeypatch):
    monkeypatch.setenv("HYIMPORTER_INPUT_ROOT", "/tmp/hyimporter/input_override")
    monkeypatch.setenv("HYIMPORTER_OUTPUT_ROOT", "/tmp/hyimporter/out_override")
    monkeypatch.delenv("HYIMPORTER_BASE_DIR", raising=False)

    p = PathsConfig()
    assert Path(p.input_root) == Path("/tmp/hyimporter/input_override")
    assert Path(p.output_root) == Path("/tmp/hyimporter/out_override")


def test_paths_config_uses_base_dir_override(monkeypatch):
    monkeypatch.delenv("HYIMPORTER_INPUT_ROOT", raising=False)
    monkeypatch.delenv("HYIMPORTER_OUTPUT_ROOT", raising=False)
    monkeypatch.setenv("HYIMPORTER_BASE_DIR", "/tmp/hyimporter_base")

    p = PathsConfig()
    assert Path(p.input_root) == Path("/tmp/hyimporter_base/input")
    assert Path(p.output_root) == Path("/tmp/hyimporter_base/out")
