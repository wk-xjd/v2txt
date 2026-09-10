from __future__ import annotations

import multiprocessing
import os
import sys
from pathlib import Path
from typing import Sequence


def configure_bundled_resources(executable: Path | None = None) -> None:
    """Prefer models shipped beside the packaged executable."""
    executable = executable or Path(sys.executable)
    model_root = executable.resolve().parent / "models"
    if model_root.is_dir():
        os.environ["V2TXT_BUNDLED_MODEL_DIR"] = str(model_root)


def main(argv: Sequence[str] | None = None) -> None:
    # PyInstaller's extended freeze_support handles resource-tracker/worker
    # command lines before they can be mistaken for v2txt CLI arguments.
    multiprocessing.freeze_support()
    configure_bundled_resources()
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        from .gui import run_gui

        run_gui()
        return

    from .cli import app

    app(args=args, prog_name="v2txt")
