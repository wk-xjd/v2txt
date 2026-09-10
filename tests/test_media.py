import json
import subprocess
import sys
from pathlib import Path

import pytest

from handover_transcriber.errors import MediaError
from handover_transcriber.media import MediaTools
from handover_transcriber.models import AudioChunk, MediaInfo


class RecordingRunner:
    def __init__(self, result: subprocess.CompletedProcess[str]) -> None:
        self.result = result
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        return self.result


def test_probe_uses_content_not_extension_and_preserves_path(tmp_path: Path) -> None:
    source = tmp_path / "有 空格.wrong"
    source.touch()
    response = {
        "format": {"duration": "280.269", "format_name": "mov,mp4"},
        "streams": [
            {"index": 0, "codec_type": "video", "codec_name": "h264"},
            {"index": 1, "codec_type": "audio", "codec_name": "aac"},
        ],
    }
    runner = RecordingRunner(subprocess.CompletedProcess([], 0, json.dumps(response), ""))
    tools = MediaTools(runner=runner, locator=lambda name: f"/tools/{name}")

    info = tools.probe(source)

    assert info == MediaInfo(280.269, "mov,mp4", "aac")
    assert runner.commands[0][-1] == str(source)
    assert runner.commands[0][0] == "/tools/ffprobe"


def test_probe_rejects_media_without_audio(tmp_path: Path) -> None:
    source = tmp_path / "silent.mp4"
    source.touch()
    payload = {"format": {"duration": "2", "format_name": "mp4"}, "streams": []}
    tools = MediaTools(
        runner=RecordingRunner(subprocess.CompletedProcess([], 0, json.dumps(payload), "")),
        locator=lambda name: name,
    )

    with pytest.raises(MediaError, match="音频流"):
        tools.probe(source)


def test_probe_reports_missing_ffprobe() -> None:
    tools = MediaTools(locator=lambda _: None)

    with pytest.raises(MediaError, match="ffmpeg"):
        tools.probe(Path("video.mp4"))


def test_probe_finds_ffprobe_bundled_by_pyinstaller(tmp_path: Path, monkeypatch) -> None:
    bundled = tmp_path / "ffprobe"
    bundled.touch()
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    payload = {
        "format": {"duration": "1", "format_name": "mp4"},
        "streams": [{"index": 0, "codec_type": "audio", "codec_name": "aac"}],
    }
    runner = RecordingRunner(subprocess.CompletedProcess([], 0, json.dumps(payload), ""))
    tools = MediaTools(runner=runner, locator=lambda _: None)

    tools.probe(Path("video.mp4"))

    assert runner.commands[0][0] == str(bundled)


def test_create_chunks_returns_timeline_metadata(tmp_path: Path) -> None:
    source = tmp_path / "video.mp4"
    source.touch()

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        pattern = Path(command[-1])
        pattern.with_name("chunk-00000.wav").touch()
        pattern.with_name("chunk-00001.wav").touch()
        return subprocess.CompletedProcess(command, 0, "", "")

    tools = MediaTools(runner=run, locator=lambda name: name)

    chunks = tools.create_chunks(source, tmp_path / "audio", duration=1000.0)

    assert chunks == [
        AudioChunk(0, tmp_path / "audio/chunk-00000.wav", 0.0, 900.0),
        AudioChunk(1, tmp_path / "audio/chunk-00001.wav", 900.0, 1000.0),
    ]


def test_ffmpeg_failure_includes_short_diagnostic(tmp_path: Path) -> None:
    source = tmp_path / "broken.mp4"
    source.touch()
    runner = RecordingRunner(subprocess.CompletedProcess([], 1, "", "Unknown decoder"))
    tools = MediaTools(runner=runner, locator=lambda name: name)

    with pytest.raises(MediaError, match="Unknown decoder"):
        tools.create_chunks(source, tmp_path / "audio", duration=1.0)
