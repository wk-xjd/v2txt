from pathlib import Path

import pytest

from handover_transcriber.gui import create_configs


def test_gui_config_maps_auto_language_and_default_output(tmp_path: Path) -> None:
    source = tmp_path / "交接.mp4"
    source.touch()

    configs = create_configs([str(source)], "", "small", "auto", " 专有名词 ")

    config = configs[0]
    assert config.input_path == source
    assert config.output_dir == tmp_path / "交接_transcript"
    assert config.language is None
    assert config.prompt == "专有名词"


def test_gui_config_rejects_missing_input(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="有效"):
        create_configs([str(tmp_path / "missing.mp4")], "", "small", "zh", "")


def test_gui_configs_default_output_next_to_each_input(tmp_path: Path) -> None:
    first = tmp_path / "一.mp4"
    second = tmp_path / "二.mp4"
    first.touch()
    second.touch()

    configs = create_configs([str(first), str(second)], "", "small", "zh", "")

    assert [config.output_dir for config in configs] == [
        tmp_path / "一_transcript",
        tmp_path / "二_transcript",
    ]


def test_gui_configs_share_parent_output_for_batch(tmp_path: Path) -> None:
    first = tmp_path / "一.mp4"
    second = tmp_path / "二.mp4"
    first.touch()
    second.touch()

    configs = create_configs(
        [str(first), str(second)], str(tmp_path / "out"), "small", "zh", ""
    )

    assert [config.output_dir for config in configs] == [
        tmp_path / "out" / "一_transcript",
        tmp_path / "out" / "二_transcript",
    ]
