from pathlib import Path

import pytest

from handover_transcriber.checkpoint import CheckpointStore
from handover_transcriber.errors import CheckpointError
from handover_transcriber.models import AudioChunk, MediaInfo, RawSegment, TaskConfig


def make_config(tmp_path: Path, model: str = "small", force: bool = False) -> TaskConfig:
    source = tmp_path / "video.mp4"
    source.touch(exist_ok=True)
    return TaskConfig.create(source, output_dir=tmp_path / "out", model=model, force=force)


def make_chunks(tmp_path: Path) -> list[AudioChunk]:
    audio = tmp_path / "out/.work/audio"
    audio.mkdir(parents=True, exist_ok=True)
    chunks = [
        AudioChunk(0, audio / "chunk-00000.wav", 0.0, 900.0),
        AudioChunk(1, audio / "chunk-00001.wav", 900.0, 1000.0),
    ]
    for chunk in chunks:
        chunk.path.touch()
    return chunks


def test_checkpoint_resumes_completed_chunks(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    media = MediaInfo(1000.0, "mp4", "aac")
    chunks = make_chunks(tmp_path)
    store = CheckpointStore(config.output_dir)
    store.open(config, media)
    store.register_chunks(chunks)
    store.save_chunk(0, "zh", [RawSegment(1.0, 2.0, " 第一段 ")])

    resumed = CheckpointStore(config.output_dir)
    state = resumed.open(config, media)
    resumed.register_chunks(chunks)

    assert state.completed == frozenset({0})
    assert resumed.pending_chunks() == [chunks[1]]
    assert resumed.load_parts() == ([(0.0, [RawSegment(1.0, 2.0, " 第一段 ")])], "zh")
    assert not list((config.output_dir / ".work").rglob("*.tmp"))


def test_checkpoint_rejects_changed_model(tmp_path: Path) -> None:
    media = MediaInfo(10.0, "mp4", "aac")
    first = make_config(tmp_path, model="small")
    CheckpointStore(first.output_dir).open(first, media)
    changed = TaskConfig.create(first.input_path, output_dir=first.output_dir, model="medium")

    with pytest.raises(CheckpointError, match="model"):
        CheckpointStore(changed.output_dir).open(changed, media)


def test_force_preserves_unknown_files(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    media = MediaInfo(10.0, "mp4", "aac")
    store = CheckpointStore(config.output_dir)
    store.open(config, media)
    unknown = config.output_dir / "notes.txt"
    unknown.write_text("keep", encoding="utf-8")
    (config.output_dir / "transcript.json").write_text("old", encoding="utf-8")

    forced = TaskConfig.create(
        config.input_path, output_dir=config.output_dir, model="medium", force=True
    )
    CheckpointStore(forced.output_dir).open(forced, media, force=True)

    assert unknown.read_text(encoding="utf-8") == "keep"
    assert not (config.output_dir / "transcript.json").exists()


def test_force_does_not_follow_work_symlink(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    config.output_dir.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    protected = outside / "keep.txt"
    protected.write_text("keep", encoding="utf-8")
    try:
        (config.output_dir / ".work").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are unavailable on this platform")

    CheckpointStore(config.output_dir).open(
        config, MediaInfo(10.0, "mp4", "aac"), force=True
    )

    assert protected.read_text(encoding="utf-8") == "keep"
    assert (config.output_dir / ".work").is_dir()
    assert not (config.output_dir / ".work").is_symlink()


def test_cleanup_audio_keeps_saved_segments(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    media = MediaInfo(10.0, "mp4", "aac")
    chunks = make_chunks(tmp_path)[:1]
    store = CheckpointStore(config.output_dir)
    store.open(config, media)
    store.register_chunks(chunks)
    store.save_chunk(0, "zh", [RawSegment(0.0, 1.0, "内容")])

    store.cleanup_audio()

    assert not (config.output_dir / ".work/audio").exists()
    assert (config.output_dir / ".work/segments/chunk-00000.json").is_file()
