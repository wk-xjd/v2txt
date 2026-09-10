from pathlib import Path
from types import SimpleNamespace

import pytest

from handover_transcriber.errors import TranscriptionError
from handover_transcriber.models import ChunkTranscript, RawSegment
from handover_transcriber.transcriber import FasterWhisperTranscriber


class FakeWhisperModel:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def transcribe(self, path: str, **options: object):
        self.calls.append((path, options))
        return iter(
            [
                SimpleNamespace(start=1.0, end=2.5, text=" 嗯 第一段 "),
                SimpleNamespace(start=3.0, end=4.0, text="  "),
            ]
        ), SimpleNamespace(language="zh")


def test_backend_uses_cpu_int8_and_expected_transcription_options(monkeypatch) -> None:
    monkeypatch.delenv("HF_HUB_DISABLE_XET", raising=False)
    created: list[tuple[str, dict[str, object]]] = []
    model = FakeWhisperModel()

    def factory(name: str, **options: object) -> FakeWhisperModel:
        created.append((name, options))
        return model

    backend = FasterWhisperTranscriber("small", model_factory=factory)

    result = backend.transcribe(Path("audio.wav"), language="zh", prompt="Cowork")

    assert created == [("small", {"device": "cpu", "compute_type": "int8"})]
    assert model.calls == [
        (
            "audio.wav",
            {
                "language": "zh",
                "initial_prompt": "Cowork",
                "vad_filter": True,
                "beam_size": 5,
                "condition_on_previous_text": False,
            },
        )
    ]
    assert result == ChunkTranscript("zh", [RawSegment(1.0, 2.5, "嗯 第一段")])
    assert __import__("os").environ["HF_HUB_DISABLE_XET"] == "1"


def test_backend_reports_segment_progress() -> None:
    model = FakeWhisperModel()
    progress: list[float] = []
    backend = FasterWhisperTranscriber("small", model_factory=lambda *args, **kwargs: model)

    backend.transcribe(
        Path("audio.wav"), language="zh", prompt=None, on_progress=progress.append
    )

    assert progress == [2.5, 4.0]


def test_backend_passes_none_for_auto_language_and_reuses_model() -> None:
    model = FakeWhisperModel()
    created = 0

    def factory(name: str, **options: object) -> FakeWhisperModel:
        nonlocal created
        created += 1
        return model

    backend = FasterWhisperTranscriber("base", model_factory=factory)

    backend.transcribe(Path("one.wav"), language=None, prompt=None)
    backend.transcribe(Path("two.wav"), language=None, prompt=None)

    assert created == 1
    assert model.calls[0][1]["language"] is None


def test_backend_wraps_iteration_failure() -> None:
    class BrokenModel:
        def transcribe(self, path: str, **options: object):
            def broken():
                raise RuntimeError("inference failed")
                yield

            return broken(), SimpleNamespace(language="zh")

    backend = FasterWhisperTranscriber("base", model_factory=lambda *args, **kwargs: BrokenModel())

    with pytest.raises(TranscriptionError, match="inference failed"):
        backend.transcribe(Path("audio.wav"), language="zh", prompt=None)


def test_backend_retries_temporary_model_load_failure() -> None:
    attempts = 0
    model = FakeWhisperModel()

    def flaky_factory(name: str, **options: object) -> FakeWhisperModel:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError("temporary disconnect")
        return model

    delays: list[float] = []
    backend = FasterWhisperTranscriber(
        "base", model_factory=flaky_factory, sleeper=delays.append
    )

    backend.transcribe(Path("audio.wav"), language="zh", prompt=None)

    assert attempts == 3
    assert delays == [2.0, 4.0]


def test_backend_uses_named_model_from_offline_root(tmp_path: Path, monkeypatch) -> None:
    model_dir = tmp_path / "models/small"
    model_dir.mkdir(parents=True)
    monkeypatch.setenv("HANDOVER_MODEL_DIR", str(tmp_path / "models"))
    created: list[str] = []

    def factory(name: str, **options: object) -> FakeWhisperModel:
        created.append(name)
        return FakeWhisperModel()

    FasterWhisperTranscriber("small", model_factory=factory).transcribe(
        Path("audio.wav"), language="zh", prompt=None
    )

    assert created == [str(model_dir)]


def test_backend_uses_bundled_model_when_present(tmp_path: Path, monkeypatch) -> None:
    model_dir = tmp_path / "models/small"
    model_dir.mkdir(parents=True)
    monkeypatch.delenv("HANDOVER_MODEL_DIR", raising=False)
    monkeypatch.setenv("V2TXT_BUNDLED_MODEL_DIR", str(tmp_path / "models"))
    created: list[str] = []

    def factory(name: str, **options: object) -> FakeWhisperModel:
        created.append(name)
        return FakeWhisperModel()

    FasterWhisperTranscriber("small", model_factory=factory).transcribe(
        Path("audio.wav"), language="zh", prompt=None
    )

    assert created == [str(model_dir)]


def test_backend_can_download_model_missing_from_bundle(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("HANDOVER_MODEL_DIR", raising=False)
    monkeypatch.setenv("V2TXT_BUNDLED_MODEL_DIR", str(tmp_path / "models"))
    created: list[str] = []

    def factory(name: str, **options: object) -> FakeWhisperModel:
        created.append(name)
        return FakeWhisperModel()

    FasterWhisperTranscriber("medium", model_factory=factory).transcribe(
        Path("audio.wav"), language="zh", prompt=None
    )

    assert created == ["medium"]
