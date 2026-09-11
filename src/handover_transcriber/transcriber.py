from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Callable, Protocol

from .errors import TranscriptionError
from .models import ChunkTranscript, RawSegment

SIMPLIFIED_CHINESE_HINT = "以下是普通话的句子。"

_simplified_converter: Any | None = None


def initial_prompt_for(language: str | None, prompt: str | None) -> str | None:
    if language != "zh":
        return prompt
    if prompt and SIMPLIFIED_CHINESE_HINT in prompt:
        return prompt
    return SIMPLIFIED_CHINESE_HINT + (prompt or "")


def to_simplified(text: str) -> str:
    global _simplified_converter
    if _simplified_converter is None:
        from opencc import OpenCC

        _simplified_converter = OpenCC("t2s")
    return _simplified_converter.convert(text)


class Transcriber(Protocol):
    def transcribe(
        self,
        path: Path,
        *,
        language: str | None,
        prompt: str | None,
        on_progress: Callable[[float], None] | None = None,
    ) -> ChunkTranscript: ...


class FasterWhisperTranscriber:
    def __init__(
        self,
        model_name: str,
        *,
        model_factory: Callable[..., Any] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.model_name = model_name
        self._model_factory = model_factory
        self._sleeper = sleeper
        self._model: Any | None = None

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
        if self._model_factory is None:
            try:
                from faster_whisper import WhisperModel
            except Exception as exc:
                raise TranscriptionError(f"faster-whisper 加载失败：{exc}") from exc

            factory: Callable[..., Any] = WhisperModel
        else:
            factory = self._model_factory
        model_source = self.model_name
        offline_root = os.environ.get("HANDOVER_MODEL_DIR")
        if offline_root:
            candidate = Path(offline_root).expanduser() / self.model_name
            if not candidate.is_dir():
                raise TranscriptionError(f"离线模型目录不存在：{candidate}")
            model_source = str(candidate)
        else:
            bundled_root = os.environ.get("V2TXT_BUNDLED_MODEL_DIR")
            if bundled_root:
                candidate = Path(bundled_root) / self.model_name
                if candidate.is_dir():
                    model_source = str(candidate)
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                self._model = factory(model_source, device="cpu", compute_type="int8")
                return self._model
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    self._sleeper(float(2 ** (attempt + 1)))
        assert last_error is not None
        raise TranscriptionError(f"模型 {self.model_name} 加载失败：{last_error}") from last_error

    def transcribe(
        self,
        path: Path,
        *,
        language: str | None,
        prompt: str | None,
        on_progress: Callable[[float], None] | None = None,
    ) -> ChunkTranscript:
        model = self._load_model()
        try:
            segments, info = model.transcribe(
                str(path),
                language=language,
                initial_prompt=initial_prompt_for(language, prompt),
                vad_filter=True,
                beam_size=5,
                condition_on_previous_text=False,
            )
            normalized = []
            detected_language = getattr(info, "language", None)
            simplify = (detected_language or language) == "zh"
            for segment in segments:
                end = float(segment.end)
                if on_progress:
                    on_progress(end)
                text = str(segment.text).strip()
                if text and simplify:
                    text = to_simplified(text)
                if text:
                    normalized.append(RawSegment(float(segment.start), end, text))
        except Exception as exc:
            raise TranscriptionError(f"音频块 {path.name} 转写失败：{exc}") from exc
        return ChunkTranscript(detected_language, normalized)
