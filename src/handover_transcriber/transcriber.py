from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Protocol

from .errors import TranscriptionError
from .models import ChunkTranscript, RawSegment


class Transcriber(Protocol):
    def transcribe(
        self, path: Path, *, language: str | None, prompt: str | None
    ) -> ChunkTranscript: ...


class FasterWhisperTranscriber:
    def __init__(
        self,
        model_name: str,
        *,
        model_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.model_name = model_name
        self._model_factory = model_factory
        self._model: Any | None = None

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            if self._model_factory is None:
                from faster_whisper import WhisperModel

                factory: Callable[..., Any] = WhisperModel
            else:
                factory = self._model_factory
            self._model = factory(self.model_name, device="cpu", compute_type="int8")
            return self._model
        except Exception as exc:
            raise TranscriptionError(f"模型 {self.model_name} 加载失败：{exc}") from exc

    def transcribe(
        self,
        path: Path,
        *,
        language: str | None,
        prompt: str | None,
    ) -> ChunkTranscript:
        model = self._load_model()
        try:
            segments, info = model.transcribe(
                str(path),
                language=language,
                initial_prompt=prompt,
                vad_filter=True,
                beam_size=5,
                condition_on_previous_text=True,
            )
            normalized = [
                RawSegment(float(segment.start), float(segment.end), text)
                for segment in segments
                if (text := str(segment.text).strip())
            ]
            detected_language = getattr(info, "language", None)
        except Exception as exc:
            raise TranscriptionError(f"音频块 {path.name} 转写失败：{exc}") from exc
        return ChunkTranscript(detected_language, normalized)
