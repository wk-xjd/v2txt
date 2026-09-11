from __future__ import annotations

from pathlib import Path
from typing import Callable

from .checkpoint import CheckpointStore
from .errors import InputError
from .media import MediaTools
from .models import ProgressEvent, TaskConfig
from .outputs import normalize_segments, write_outputs
from .transcriber import FasterWhisperTranscriber, Transcriber

ProgressCallback = Callable[[ProgressEvent], None]
TranscriberFactory = Callable[[str], Transcriber]


class TranscriptionService:
    def __init__(
        self,
        media: MediaTools | None = None,
        transcriber_factory: TranscriberFactory | None = None,
    ) -> None:
        self.media = media or MediaTools()
        self.transcriber_factory = transcriber_factory or (
            lambda model: FasterWhisperTranscriber(model)
        )
        self._transcribers: dict[str, Transcriber] = {}

    def _transcriber_for(self, model: str) -> Transcriber:
        if model not in self._transcribers:
            self._transcribers[model] = self.transcriber_factory(model)
        return self._transcribers[model]

    @staticmethod
    def _emit(
        callback: ProgressCallback | None,
        stage: str,
        completed: float,
        total: float,
        message: str,
    ) -> None:
        if callback:
            callback(ProgressEvent(stage, completed, total, message))

    def run(
        self,
        config: TaskConfig,
        on_progress: ProgressCallback | None = None,
    ) -> Path:
        if not config.input_path.is_file():
            raise InputError("输入路径必须是可读取的普通文件")
        self._emit(on_progress, "probe", 0.0, 0.0, "正在读取媒体信息")
        media_info = self.media.probe(config.input_path)
        store = CheckpointStore(config.output_dir)
        state = store.open(config, media_info)

        if state.all_complete:
            chunks = store.stored_chunks()
        else:
            self._emit(
                on_progress,
                "extract",
                0.0,
                media_info.duration_seconds,
                "正在提取并分块音频",
            )
            chunks = self.media.create_chunks(
                config.input_path,
                store.work_dir / "audio",
                media_info.duration_seconds,
            )
        store.register_chunks(chunks)

        pending = store.pending_chunks()
        if pending:
            backend = self._transcriber_for(config.model)
            for chunk in pending:
                self._emit(
                    on_progress,
                    "transcribe",
                    chunk.start,
                    media_info.duration_seconds,
                    f"正在转写音频块 {chunk.index + 1}/{len(chunks)}",
                )
                transcript = backend.transcribe(
                    chunk.path,
                    language=config.language,
                    prompt=config.prompt,
                    on_progress=lambda seconds, chunk=chunk: self._emit(
                        on_progress,
                        "transcribe",
                        min(chunk.start + seconds, media_info.duration_seconds),
                        media_info.duration_seconds,
                        f"正在转写音频块 {chunk.index + 1}/{len(chunks)}",
                    ),
                )
                store.save_chunk(
                    chunk.index,
                    transcript.detected_language,
                    transcript.segments,
                )

        parts, detected_language = store.load_parts()
        segments = normalize_segments(parts, media_info.duration_seconds)
        self._emit(
            on_progress,
            "write",
            media_info.duration_seconds,
            media_info.duration_seconds,
            "正在生成输出文件",
        )
        write_outputs(
            config.output_dir,
            source_name=config.input_path.name,
            duration=media_info.duration_seconds,
            model=config.model,
            language_requested=config.language or "auto",
            language_detected=detected_language,
            segments=segments,
        )
        store.cleanup_audio()
        self._emit(
            on_progress,
            "complete",
            media_info.duration_seconds,
            media_info.duration_seconds,
            "转写完成",
        )
        return config.output_dir
