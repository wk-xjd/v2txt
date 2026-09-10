from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Sequence

from .errors import OutputError
from .models import RawSegment, Segment


def _milliseconds(seconds: float) -> int:
    return max(0, int(seconds * 1000 + 0.5))


def format_srt_time(seconds: float) -> str:
    total_ms = _milliseconds(seconds)
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_clock(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3_600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def normalize_segments(
    parts: Iterable[tuple[float, Sequence[RawSegment]]], duration: float
) -> list[Segment]:
    limit = max(0.0, duration + 1.0)
    normalized: list[tuple[float, float, str]] = []
    for offset, raw_segments in parts:
        for raw in raw_segments:
            text = raw.text.strip()
            if not text:
                continue
            start = min(limit, max(0.0, offset + raw.start))
            end = min(limit, max(start, offset + raw.end))
            normalized.append((start, end, text))
    normalized.sort(key=lambda item: (item[0], item[1]))
    return [Segment(index, start, end, text) for index, (start, end, text) in enumerate(normalized)]


def render_srt(segments: Sequence[Segment]) -> str:
    blocks = [
        f"{segment.id + 1}\n{format_srt_time(segment.start)} --> {format_srt_time(segment.end)}\n{segment.text}"
        for segment in segments
    ]
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def _timeline_groups(segments: Sequence[Segment]) -> list[list[Segment]]:
    groups: list[list[Segment]] = []
    for segment in segments:
        if not groups:
            groups.append([segment])
            continue
        current = groups[-1]
        if segment.start - current[-1].end > 15 or segment.end - current[0].start > 60:
            groups.append([segment])
        else:
            current.append(segment)
    return groups


def render_timeline(
    source_name: str,
    duration: float,
    model: str,
    language: str,
    segments: Sequence[Segment],
) -> str:
    title = Path(source_name).stem
    lines = [
        f"# {title} 时间线转写",
        "",
        f"- 来源：`{source_name}`",
        f"- 时长：{format_clock(duration)}",
        f"- 模型：`{model}`",
        f"- 语言：`{language}`",
    ]
    for group in _timeline_groups(segments):
        lines.extend(
            [
                "",
                f"## {format_clock(group[0].start)} - {format_clock(group[-1].end)}",
                "",
                " ".join(segment.text for segment in group),
            ]
        )
    return "\n".join(lines) + "\n"


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise OutputError(f"无法写入输出文件 {path}: {exc}") from exc


def write_outputs(
    output_dir: Path,
    *,
    source_name: str,
    duration: float,
    model: str,
    language_requested: str,
    language_detected: str | None,
    segments: Sequence[Segment],
) -> None:
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OutputError(f"无法创建输出目录 {output_dir}: {exc}") from exc

    payload = {
        "schema_version": 1,
        "source": {"file_name": source_name, "duration_seconds": duration},
        "transcription": {
            "model": model,
            "language_requested": language_requested,
            "language_detected": language_detected,
            "device": "cpu",
            "compute_type": "int8",
        },
        "segments": [asdict(segment) for segment in segments],
    }
    _atomic_write(
        output_dir / "transcript.json",
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )
    _atomic_write(output_dir / "transcript.srt", render_srt(segments))
    _atomic_write(
        output_dir / "timeline.md",
        render_timeline(
            source_name,
            duration,
            model,
            language_detected or language_requested,
            segments,
        ),
    )
