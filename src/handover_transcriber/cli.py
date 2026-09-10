from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from . import __version__
from .models import TaskConfig

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console(stderr=True)


class ModelChoice(str, Enum):
    base = "base"
    small = "small"
    medium = "medium"
    large_v3 = "large-v3"


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
    console.print(f"准备转写：[bold]{config.input_path}[/bold]")
    console.print("核心转写服务将在后续任务中接入。")
