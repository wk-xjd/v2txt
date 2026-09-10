from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

from .errors import MediaError
from .models import AudioChunk, MediaInfo

Runner = Callable[..., subprocess.CompletedProcess[str]]
Locator = Callable[[str], str | None]


class MediaTools:
    def __init__(
        self,
        *,
        runner: Runner = subprocess.run,
        locator: Locator = shutil.which,
    ) -> None:
        self._runner = runner
        self._locator = locator

    def _program(self, name: str) -> str:
        path = self._locator(name)
        if path:
            return path
        install = (
            "winget install Gyan.FFmpeg"
            if sys.platform == "win32"
            else "brew install ffmpeg"
        )
        raise MediaError(f"未找到 {name}。请先安装 ffmpeg：{install}")

    def _execute(self, command: list[str], action: str) -> subprocess.CompletedProcess[str]:
        try:
            result = self._runner(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except OSError as exc:
            raise MediaError(f"{action}失败：{exc}") from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "未知错误").strip()[-2000:]
            raise MediaError(f"{action}失败：{detail}")
        return result

    def probe(self, input_path: Path) -> MediaInfo:
        command = [
            self._program("ffprobe"),
            "-v",
            "error",
            "-show_entries",
            "format=duration,format_name:stream=index,codec_type,codec_name",
            "-of",
            "json",
            str(input_path),
        ]
        result = self._execute(command, "媒体探测")
        try:
            payload = json.loads(result.stdout)
            duration = float(payload["format"]["duration"])
            format_name = str(payload["format"]["format_name"])
            audio_stream = next(
                stream for stream in payload.get("streams", []) if stream.get("codec_type") == "audio"
            )
            audio_codec = str(audio_stream["codec_name"])
        except StopIteration as exc:
            raise MediaError("媒体中没有可用的音频流") from exc
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise MediaError("ffprobe 返回了无法解析的媒体信息") from exc
        if duration <= 0:
            raise MediaError("媒体时长必须大于零")
        return MediaInfo(duration, format_name, audio_codec)

    def create_chunks(
        self, input_path: Path, audio_dir: Path, duration: float
    ) -> list[AudioChunk]:
        try:
            audio_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise MediaError(f"无法创建临时音频目录：{exc}") from exc
        pattern = audio_dir / "chunk-%05d.wav"
        command = [
            self._program("ffmpeg"),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(input_path),
            "-map",
            "0:a:0",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            "-f",
            "segment",
            "-segment_time",
            "900",
            "-reset_timestamps",
            "1",
            str(pattern),
        ]
        self._execute(command, "音频解码或分块")
        paths = sorted(audio_dir.glob("chunk-[0-9][0-9][0-9][0-9][0-9].wav"))
        if not paths:
            raise MediaError("ffmpeg 未生成任何音频块")
        return [
            AudioChunk(
                index=index,
                path=path,
                start=index * 900.0,
                end=min(duration, (index + 1) * 900.0),
            )
            for index, path in enumerate(paths)
        ]
