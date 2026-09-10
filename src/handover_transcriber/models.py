from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence, cast

ModelName = Literal["base", "small", "medium", "large-v3"]
ALLOWED_MODELS: tuple[ModelName, ...] = ("base", "small", "medium", "large-v3")


@dataclass(frozen=True)
class TaskConfig:
    input_path: Path
    output_dir: Path
    model: ModelName = "small"
    language: str | None = "zh"
    prompt: str | None = None
    force: bool = False

    @classmethod
    def create(
        cls,
        input_path: Path,
        *,
        output_dir: Path | None = None,
        model: str = "small",
        language: str | None = "zh",
        prompt: str | None = None,
        force: bool = False,
    ) -> TaskConfig:
        if model not in ALLOWED_MODELS:
            allowed = ", ".join(ALLOWED_MODELS)
            raise ValueError(f"model must be one of: {allowed}")
        target = output_dir or input_path.with_name(f"{input_path.stem}_transcript")
        return cls(
            input_path=input_path,
            output_dir=target,
            model=cast(ModelName, model),
            language=language,
            prompt=prompt or None,
            force=force,
        )


@dataclass(frozen=True)
class MediaInfo:
    duration_seconds: float
    format_name: str
    audio_codec: str


@dataclass(frozen=True)
class AudioChunk:
    index: int
    path: Path
    start: float
    end: float


@dataclass(frozen=True)
class RawSegment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class Segment:
    id: int
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class ChunkTranscript:
    detected_language: str | None
    segments: Sequence[RawSegment]


@dataclass(frozen=True)
class ProgressEvent:
    stage: str
    completed_seconds: float
    total_seconds: float
    message: str
