from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn, TimeRemainingColumn

from . import __version__
from .errors import HandoverError
from .models import TaskConfig
from .service import TranscriptionService

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console(stderr=True)


class ModelChoice(str, Enum):
    base = "base"
    small = "small"
    medium = "medium"
    large_v3 = "large-v3"


def build_service() -> TranscriptionService:
    return TranscriptionService()


class CliProgress:
    def __init__(self) -> None:
        self._last_stage: str | None = None
        self._progress: Progress | None = None
        self._task_id = None

    def __enter__(self) -> CliProgress:
        if console.is_terminal:
            self._progress = Progress(
                TextColumn("{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeRemainingColumn(),
                console=console,
            )
            self._progress.start()
            self._task_id = self._progress.add_task("正在准备", total=100.0)
        return self

    def __exit__(self, *args: object) -> None:
        if self._progress:
            self._progress.stop()

    def update(self, event) -> None:
        if self._progress is not None and self._task_id is not None:
            percent = (
                100.0 * event.completed_seconds / event.total_seconds
                if event.total_seconds > 0
                else 0.0
            )
            self._progress.update(
                self._task_id,
                completed=min(percent, 100.0),
                description=event.message,
            )
        elif event.stage != self._last_stage:
            typer.echo(event.message)
        self._last_stage = event.stage


def build_config(
    input_path: Path,
    *,
    output: Path | None = None,
    model: str = "small",
    language: str = "zh",
    prompt: str | None = None,
    force: bool = False,
) -> TaskConfig:
    if not input_path.is_file():
        raise typer.BadParameter("输入路径必须是可读取的普通文件")
    return TaskConfig.create(
        input_path,
        output_dir=output,
        model=model,
        language=None if language == "auto" else language,
        prompt=prompt,
        force=force,
    )


def version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.command()
def transcribe(
    input_path: Annotated[Path, typer.Argument(metavar="INPUT")],
    model: Annotated[ModelChoice, typer.Option("--model", help="Whisper 模型")] = ModelChoice.small,
    language: Annotated[str, typer.Option("--language", help="语言代码或 auto")] = "zh",
    prompt: Annotated[str | None, typer.Option("--prompt", help="技术词提示")] = None,
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
    force: Annotated[bool, typer.Option("--force")] = False,
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=version_callback, is_eager=True),
    ] = None,
) -> None:
    """把视频或音频转为带时间戳的文本。"""
    del version
    config = build_config(
        input_path,
        output=output,
        model=model.value,
        language=language,
        prompt=prompt,
        force=force,
    )
    if config.model == "large-v3":
        typer.echo("提示：large-v3 在 CPU 上可能非常慢。", err=True)
    try:
        with CliProgress() as progress:
            result = build_service().run(config, on_progress=progress.update)
    except HandoverError as exc:
        typer.echo(f"错误：{exc}", err=True)
        raise typer.Exit(exc.exit_code) from exc
    except KeyboardInterrupt as exc:
        typer.echo("任务已中断；可以使用相同命令继续。", err=True)
        raise typer.Exit(130) from exc
    except Exception as exc:
        typer.echo(f"意外错误：{exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"输出目录：{result}")
