from pathlib import Path

import pytest

from handover_transcriber.gui import create_config


def test_gui_config_maps_auto_language_and_default_output(tmp_path: Path) -> None:
    source = tmp_path / "交接.mp4"
    source.touch()

    config = create_config(str(source), "", "small", "auto", " 专有名词 ")

    assert config.input_path == source
    assert config.output_dir == tmp_path / "交接_transcript"
    assert config.language is None
    assert config.prompt == "专有名词"


def test_gui_config_rejects_missing_input(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="有效"):
        create_config(str(tmp_path / "missing.mp4"), "", "small", "zh", "")
