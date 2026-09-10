from pathlib import Path

import pytest

from handover_transcriber.models import ALLOWED_MODELS, TaskConfig


def test_task_config_defaults_to_small_chinese(tmp_path: Path) -> None:
    source = tmp_path / "meeting.anything"
    source.touch()

    config = TaskConfig.create(source)

    assert config.model == "small"
    assert config.language == "zh"
    assert config.output_dir == tmp_path / "meeting_transcript"


@pytest.mark.parametrize("model", ["base", "small", "medium", "large-v3"])
def test_task_config_accepts_supported_models(tmp_path: Path, model: str) -> None:
    source = tmp_path / "meeting.mp4"
    source.touch()

    assert TaskConfig.create(source, model=model).model == model


def test_task_config_rejects_unknown_model(tmp_path: Path) -> None:
    source = tmp_path / "meeting.mp4"
    source.touch()

    with pytest.raises(ValueError, match="base, small, medium, large-v3"):
        TaskConfig.create(source, model="turbo")


def test_allowed_models_are_the_public_four() -> None:
    assert ALLOWED_MODELS == ("base", "small", "medium", "large-v3")
