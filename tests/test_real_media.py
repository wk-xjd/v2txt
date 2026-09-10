import json
import os
from pathlib import Path

import pytest

from handover_transcriber.models import TaskConfig
from handover_transcriber.service import TranscriptionService


pytestmark = pytest.mark.skipif(
    os.getenv("HANDOVER_RUN_REAL_MEDIA") != "1",
    reason="set HANDOVER_RUN_REAL_MEDIA=1 to download a model and run real media",
)


def test_real_video_transcribes_with_valid_timeline(tmp_path: Path) -> None:
    source = Path("testvideo/test.mp4").resolve()
    assert source.is_file()
    config = TaskConfig.create(source, output_dir=tmp_path / "real", model="base")

    output = TranscriptionService().run(config)

    payload = json.loads((output / "transcript.json").read_text(encoding="utf-8"))
    assert abs(payload["source"]["duration_seconds"] - 280.269) <= 1.0
    segments = payload["segments"]
    assert segments
    assert all(
        0 <= current["start"] <= current["end"] <= 281.269
        for current in segments
    )
    assert [segment["start"] for segment in segments] == sorted(
        segment["start"] for segment in segments
    )
    assert (output / "transcript.srt").stat().st_size > 0
    assert (output / "timeline.md").stat().st_size > 0
