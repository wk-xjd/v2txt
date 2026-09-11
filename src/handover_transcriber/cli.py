from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated, Sequence

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
        self._prefix = ""

    def set_prefix(self, prefix: str) -> None:
        self._prefix = prefix
        self._last_stage = None

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
        message = f"{self._prefix}{event.message}"
        if self._progress is not None and self._task_id is not None:
            percent = (
                100.0 * event.completed_seconds / event.total_seconds
                if event.total_seconds > 0
                else 0.0
            )
            self._progress.update(
                self._task_id,
                completed=min(percent, 100.0),
                description=message,
            )
        elif event.stage != self._last_stage:
            typer.echo(message)
        self._last_stage = event.stage


def build_configs(
    input_paths: Sequence[Path],
    *,
    output: Path | None = None,
    model: str = "small",
    language: str = "zh",
    prompt: str | None = None,
    force: bool = False,
) -> list[TaskConfig]:
    multiple = len(input_paths) > 1
    configs: list[TaskConfig] = []
    for input_path in input_paths:
        if not input_path.is_file():
            raise typer.BadParameter("输入路径必须是可读取的普通文件")
        output_dir = output
        if output is not None and multiple:
            output_dir = output / f"{input_path.stem}_transcript"
        configs.append(
            TaskConfig.create(
                input_path,
                output_dir=output_dir,
                model=model,
                language=None if language == "auto" else language,
                prompt=prompt,
                force=force,
            )
        )
    return configs


def version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.command()
def transcribe(
    input_paths: Annotated[
        list[Path], typer.Argument(metavar="INPUT", help="一个或多个视频/音频文件")
    ],
    model: Annotated[ModelChoice, typer.Option("--model", help="Whisper 模型")] = ModelChoice.small,
    language: Annotated[str, typer.Option("--language", help="语言代码或 auto")] = "zh",
    prompt: Annotated[str | None, typer.Option("--prompt", help="技术词提示")] = None,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="单个文件时为输出目录；多个文件时为父目录")
    ] = None,
    force: Annotated[bool, typer.Option("--force")] = False,
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=version_callback, is_eager=True),
    ] = None,
) -> None:
    """把一个或多个视频/音频转为带时间戳的文本。"""
    del version
    configs = build_configs(
        input_paths,
        output=output,
        model=model.value,
        language=language,
        prompt=prompt,
        force=force,
    )
    if any(config.model == "large-v3" for config in configs):
        typer.echo("提示：large-v3 在 CPU 上可能非常慢。", err=True)
    multiple = len(configs) > 1
    completed: list[Path] = []
    failures: list[tuple[TaskConfig, HandoverError]] = []
    try:
        with CliProgress() as progress:
            service = build_service()
            for index, config in enumerate(configs, 1):
                if multiple:
                    progress.set_prefix(f"[{index}/{len(configs)}] {config.input_path.name}：")
                try:
                    output_dir = service.run(config, on_progress=progress.update)
                except HandoverError as exc:
                    failures.append((config, exc))
                    name = f"{config.input_path.name}：" if multiple else ""
                    typer.echo(f"错误：{name}{exc}", err=True)
                    continue
                completed.append(output_dir)
    except KeyboardInterrupt as exc:
        typer.echo("任务已中断；可以使用相同命令继续。", err=True)
        raise typer.Exit(130) from exc
    except Exception as exc:
        typer.echo(f"意外错误：{exc}", err=True)
        raise typer.Exit(1) from exc
    for output_dir in completed:
        typer.echo(f"输出目录：{output_dir}")
    if multiple:
        typer.echo(f"批量完成：{len(completed)}/{len(configs)} 个文件")
    if failures:
        raise typer.Exit(failures[0][1].exit_code)
