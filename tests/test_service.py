import json
from pathlib import Path

import pytest

from handover_transcriber.errors import InputError, TranscriptionError
from handover_transcriber.models import (
    AudioChunk,
    ChunkTranscript,
    MediaInfo,
    ProgressEvent,
    RawSegment,
    TaskConfig,
)
from handover_transcriber.service import TranscriptionService


class FakeMedia:
    def __init__(self, duration: float = 1000.0) -> None:
        self.duration = duration
        self.created = 0

    def probe(self, path: Path) -> MediaInfo:
        return MediaInfo(self.duration, "mp4", "aac")

    def create_chunks(self, path: Path, audio_dir: Path, duration: float) -> list[AudioChunk]:
        self.created += 1
        audio_dir.mkdir(parents=True, exist_ok=True)
        chunks = [
            AudioChunk(0, audio_dir / "chunk-00000.wav", 0.0, min(900.0, duration)),
            AudioChunk(1, audio_dir / "chunk-00001.wav", 900.0, duration),
        ]
        for chunk in chunks:
            chunk.path.touch()
        return chunks


class FakeTranscriber:
    def __init__(self, fail_index: int | None = None) -> None:
        self.fail_index = fail_index
        self.seen: list[int] = []

    def transcribe(
        self, path: Path, *, language: str | None, prompt: str | None, on_progress=None
    ) -> ChunkTranscript:
        index = int(path.stem.rsplit("-", 1)[1])
        self.seen.append(index)
        if index == self.fail_index:
            raise TranscriptionError("planned failure")
        if on_progress:
            on_progress(2.0)
        return ChunkTranscript("zh", [RawSegment(1.0, 2.0, f"第{index}段")])


def make_config(tmp_path: Path) -> TaskConfig:
    source = tmp_path / "video.unknown"
    source.touch()
    return TaskConfig.create(source, output_dir=tmp_path / "out")


def test_service_runs_pipeline_and_offsets_chunk_timestamps(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    events: list[ProgressEvent] = []
    backend = FakeTranscriber()
    service = TranscriptionService(FakeMedia(), lambda _: backend)

    output = service.run(config, on_progress=events.append)

    payload = json.loads((output / "transcript.json").read_text(encoding="utf-8"))
    assert [(item["start"], item["text"]) for item in payload["segments"]] == [
        (1.0, "第0段"),
        (901.0, "第1段"),
    ]
    assert events[-1].stage == "complete"
    assert any(event.stage == "transcribe" and event.completed_seconds == 902.0 for event in events)
    assert not (output / ".work/audio").exists()


def test_service_resume_skips_committed_chunk(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    media = FakeMedia()
    failing = FakeTranscriber(fail_index=1)

    with pytest.raises(TranscriptionError, match="planned failure"):
        TranscriptionService(media, lambda _: failing).run(config)

    resumed = FakeTranscriber()
    TranscriptionService(media, lambda _: resumed).run(config)

    assert failing.seen == [0, 1]
    assert resumed.seen == [1]


def test_completed_service_run_regenerates_outputs_without_audio(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    media = FakeMedia()
    TranscriptionService(media, lambda _: FakeTranscriber()).run(config)
    (config.output_dir / "timeline.md").unlink()
    backend = FakeTranscriber()

    TranscriptionService(media, lambda _: backend).run(config)

    assert backend.seen == []
    assert media.created == 1
    assert (config.output_dir / "timeline.md").is_file()


def test_service_rejects_missing_input_before_media_probe(tmp_path: Path) -> None:
    config = TaskConfig.create(tmp_path / "missing.mp4", output_dir=tmp_path / "out")

    with pytest.raises(InputError, match="普通文件"):
        TranscriptionService(FakeMedia(), lambda _: FakeTranscriber()).run(config)


def test_service_reuses_transcriber_across_runs(tmp_path: Path) -> None:
    created: list[str] = []

    def factory(model: str) -> FakeTranscriber:
        created.append(model)
        return FakeTranscriber()

    service = TranscriptionService(FakeMedia(), factory)
    for name in ("one", "two"):
        source = tmp_path / f"{name}.mp4"
        source.touch()
        config = TaskConfig.create(source, output_dir=tmp_path / f"{name}_out")
        service.run(config)

    assert created == ["small"]
