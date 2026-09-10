from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

from .errors import CheckpointError
from .models import AudioChunk, MediaInfo, RawSegment, TaskConfig


@dataclass(frozen=True)
class ResumeState:
    completed: frozenset[int]
    chunk_count: int

    @property
    def all_complete(self) -> bool:
        return self.chunk_count > 0 and len(self.completed) == self.chunk_count


class CheckpointStore:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.work_dir = output_dir / ".work"
        self.manifest_path = self.work_dir / "manifest.json"
        self._manifest: dict[str, Any] | None = None
        self._chunks: list[AudioChunk] = []

    def _fingerprint(self, config: TaskConfig, media: MediaInfo) -> dict[str, Any]:
        try:
            stat = config.input_path.stat()
        except OSError as exc:
            raise CheckpointError(f"无法读取输入文件信息：{exc}") from exc
        return {
            "input_path": str(config.input_path.resolve()),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "duration": media.duration_seconds,
            "model": config.model,
            "language": config.language or "auto",
            "prompt": config.prompt,
            "audio": {"sample_rate": 16000, "channels": 1, "format": "pcm_s16le"},
            "chunk_seconds": 900,
        }

    def _atomic_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise CheckpointError(f"无法保存检查点 {path}: {exc}") from exc

    def _reset_owned(self) -> None:
        try:
            if self.work_dir.is_symlink():
                self.work_dir.unlink()
            elif self.work_dir.exists():
                shutil.rmtree(self.work_dir)
            for name in ("transcript.json", "transcript.srt", "timeline.md"):
                path = self.output_dir / name
                if path.is_symlink() or path.is_file():
                    path.unlink()
        except OSError as exc:
            raise CheckpointError(f"无法清理旧任务状态：{exc}") from exc

    def open(
        self,
        config: TaskConfig,
        media: MediaInfo,
        force: bool | None = None,
    ) -> ResumeState:
        force = config.force if force is None else force
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CheckpointError(f"无法创建输出目录：{exc}") from exc
        if force:
            self._reset_owned()
        if self.work_dir.is_symlink():
            raise CheckpointError("工作目录不能是符号链接；请使用 --force 重建")

        fingerprint = self._fingerprint(config, media)
        if self.manifest_path.is_file():
            try:
                manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise CheckpointError("检查点清单损坏；请使用 --force 重新开始") from exc
            if manifest.get("schema_version") != 1:
                raise CheckpointError("检查点版本不兼容；请使用 --force 重新开始")
            previous = manifest.get("fingerprint", {})
            conflicts = [key for key, value in fingerprint.items() if previous.get(key) != value]
            if conflicts:
                raise CheckpointError(f"输出目录属于不同任务，冲突字段：{', '.join(conflicts)}")
            self._manifest = manifest
        else:
            self._manifest = {
                "schema_version": 1,
                "fingerprint": fingerprint,
                "chunks": [],
                "completed": [],
            }
            self._atomic_json(self.manifest_path, self._manifest)
        return ResumeState(
            frozenset(int(value) for value in self._manifest["completed"]),
            len(self._manifest.get("chunks", [])),
        )

    def _require_open(self) -> dict[str, Any]:
        if self._manifest is None:
            raise RuntimeError("checkpoint store is not open")
        return self._manifest

    def register_chunks(self, chunks: Sequence[AudioChunk]) -> None:
        manifest = self._require_open()
        self._chunks = list(chunks)
        descriptors = [
            {"index": chunk.index, "file": chunk.path.name, "start": chunk.start, "end": chunk.end}
            for chunk in chunks
        ]
        existing = manifest.get("chunks", [])
        if existing and existing != descriptors:
            raise CheckpointError("音频分块清单与检查点不一致；请使用 --force 重建")
        manifest["chunks"] = descriptors
        self._atomic_json(self.manifest_path, manifest)

    def pending_chunks(self) -> list[AudioChunk]:
        manifest = self._require_open()
        completed = {int(value) for value in manifest["completed"]}
        return [chunk for chunk in self._chunks if chunk.index not in completed]

    def stored_chunks(self) -> list[AudioChunk]:
        manifest = self._require_open()
        return [
            AudioChunk(
                index=int(item["index"]),
                path=self.work_dir / "audio" / str(item["file"]),
                start=float(item["start"]),
                end=float(item["end"]),
            )
            for item in manifest.get("chunks", [])
        ]

    def save_chunk(
        self,
        index: int,
        detected_language: str | None,
        segments: Sequence[RawSegment],
    ) -> None:
        manifest = self._require_open()
        payload = {
            "chunk_index": index,
            "detected_language": detected_language,
            "segments": [asdict(segment) for segment in segments],
        }
        path = self.work_dir / "segments" / f"chunk-{index:05d}.json"
        self._atomic_json(path, payload)
        completed = {int(value) for value in manifest["completed"]}
        completed.add(index)
        manifest["completed"] = sorted(completed)
        self._atomic_json(self.manifest_path, manifest)

    def load_parts(self) -> tuple[list[tuple[float, list[RawSegment]]], str | None]:
        manifest = self._require_open()
        chunk_starts = {int(chunk["index"]): float(chunk["start"]) for chunk in manifest["chunks"]}
        parts: list[tuple[float, list[RawSegment]]] = []
        detected_language: str | None = None
        for index in sorted(int(value) for value in manifest["completed"]):
            path = self.work_dir / "segments" / f"chunk-{index:05d}.json"
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                segments = [RawSegment(**item) for item in payload["segments"]]
            except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
                raise CheckpointError(f"分块检查点损坏：{path.name}") from exc
            detected_language = detected_language or payload.get("detected_language")
            parts.append((chunk_starts[index], segments))
        return parts, detected_language

    def cleanup_audio(self) -> None:
        audio_dir = self.work_dir / "audio"
        try:
            if audio_dir.is_symlink():
                audio_dir.unlink()
            elif audio_dir.exists():
                shutil.rmtree(audio_dir)
        except OSError as exc:
            raise CheckpointError(f"无法清理临时音频：{exc}") from exc
