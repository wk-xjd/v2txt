from __future__ import annotations

import queue
import threading
from pathlib import Path
from typing import Any, Sequence

from .errors import HandoverError
from .models import ALLOWED_MODELS, ProgressEvent, TaskConfig
from .service import TranscriptionService


def create_configs(
    input_texts: Sequence[str],
    output_text: str,
    model: str,
    language: str,
    prompt: str,
) -> list[TaskConfig]:
    multiple = len(input_texts) > 1
    base_output = Path(output_text).expanduser() if output_text.strip() else None
    configs: list[TaskConfig] = []
    for input_text in input_texts:
        input_path = Path(input_text).expanduser()
        if not input_path.is_file():
            raise ValueError("请选择有效的视频或音频文件")
        output = None
        if base_output is not None:
            output = base_output / f"{input_path.stem}_transcript" if multiple else base_output
        configs.append(
            TaskConfig.create(
                input_path,
                output_dir=output,
                model=model,
                language=None if language.strip().lower() == "auto" else language.strip() or "zh",
                prompt=prompt.strip() or None,
            )
        )
    return configs


def run_gui() -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title("v2txt - 视频转文字")
    root.geometry("880x470")
    root.minsize(800, 430)

    input_var = tk.StringVar()
    output_var = tk.StringVar()
    model_var = tk.StringVar(value="small")
    language_var = tk.StringVar(value="zh")
    status_var = tk.StringVar(value="选择视频或音频，然后点击开始转写")
    progress_var = tk.DoubleVar(value=0.0)
    messages: queue.Queue[tuple[str, Any]] = queue.Queue()
    selected_inputs: list[str] = []
    prefix = {"text": ""}

    frame = ttk.Frame(root, padding=18)
    frame.pack(fill="both", expand=True)
    frame.columnconfigure(1, weight=1)

    def choose_input() -> None:
        selected = filedialog.askopenfilenames(
            title="选择一个或多个视频或音频",
            filetypes=[
                ("常见媒体", "*.mp4 *.mov *.mkv *.webm *.avi *.mp3 *.m4a *.wav *.flac *.ogg"),
                ("所有文件", "*.*"),
            ],
        )
        paths = [selected] if isinstance(selected, str) else list(selected)
        paths = [path for path in paths if path]
        if not paths:
            return
        selected_inputs.clear()
        selected_inputs.extend(paths)
        if len(paths) == 1:
            input_var.set(paths[0])
            output_var.set(str(Path(paths[0]).with_name(f"{Path(paths[0]).stem}_transcript")))
            status_var.set("已选择 1 个文件，然后点击开始转写")
        else:
            input_var.set(f"{len(paths)} 个文件（{Path(paths[0]).name} 等）")
            output_var.set("")
            status_var.set(
                f"已选择 {len(paths)} 个文件，将分别输出到各自视频旁的 <名称>_transcript 目录"
            )

    def choose_output() -> None:
        selected = filedialog.askdirectory(title="选择输出目录")
        if selected:
            output_var.set(selected)

    ttk.Label(frame, text="输入文件").grid(row=0, column=0, sticky="w", pady=6)
    input_entry = ttk.Entry(frame, textvariable=input_var)
    input_entry.grid(row=0, column=1, sticky="ew", padx=8)
    input_entry.bind("<KeyRelease>", lambda _event: selected_inputs.clear())
    ttk.Button(frame, text="选择…", command=choose_input).grid(row=0, column=2)

    ttk.Label(frame, text="输出目录").grid(row=1, column=0, sticky="w", pady=6)
    ttk.Entry(frame, textvariable=output_var).grid(row=1, column=1, sticky="ew", padx=8)
    ttk.Button(frame, text="选择…", command=choose_output).grid(row=1, column=2)

    options = ttk.Frame(frame)
    options.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(12, 6))
    ttk.Label(options, text="模型").pack(side="left")
    ttk.Combobox(
        options,
        textvariable=model_var,
        values=ALLOWED_MODELS,
        state="readonly",
        width=12,
    ).pack(side="left", padx=(8, 28))
    ttk.Label(options, text="base/small/medium 已内置").pack(side="left", padx=(0, 28))
    ttk.Label(options, text="语言").pack(side="left")
    ttk.Entry(options, textvariable=language_var, width=10).pack(side="left", padx=8)
    ttk.Label(options, text="（中文填 zh，自动识别填 auto）").pack(side="left")

    ttk.Label(frame, text="术语提示（可选）").grid(row=3, column=0, columnspan=3, sticky="w", pady=(12, 4))
    prompt_box = tk.Text(frame, height=5, wrap="word")
    prompt_box.grid(row=4, column=0, columnspan=3, sticky="nsew")
    frame.rowconfigure(4, weight=1)

    progress = ttk.Progressbar(frame, variable=progress_var, maximum=100.0)
    progress.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(18, 6))
    ttk.Label(frame, textvariable=status_var).grid(row=6, column=0, columnspan=3, sticky="w")

    def worker(configs: list[TaskConfig]) -> None:
        try:
            service = TranscriptionService()
            completed: list[tuple[TaskConfig, Path]] = []
            failed: list[tuple[TaskConfig, str]] = []
            for index, config in enumerate(configs, 1):
                messages.put(("file", (index, len(configs), config.input_path.name)))
                try:
                    output = service.run(
                        config, on_progress=lambda event: messages.put(("progress", event))
                    )
                except (HandoverError, ValueError) as exc:
                    failed.append((config, str(exc)))
                    continue
                completed.append((config, output))
            messages.put(("done", (completed, failed)))
        except Exception as exc:
            messages.put(("error", f"意外错误：{exc}"))

    def start() -> None:
        try:
            configs = create_configs(
                list(selected_inputs) or [input_var.get().strip()],
                output_var.get(),
                model_var.get(),
                language_var.get(),
                prompt_box.get("1.0", "end"),
            )
        except ValueError as exc:
            messagebox.showerror("无法开始", str(exc))
            return
        start_button.configure(state="disabled")
        progress_var.set(0.0)
        status_var.set("正在准备…")
        threading.Thread(target=worker, args=(configs,), daemon=True).start()

    def poll_messages() -> None:
        try:
            while True:
                kind, payload = messages.get_nowait()
                if kind == "file":
                    index, total, name = payload
                    progress_var.set(0.0)
                    prefix["text"] = f"[{index}/{total}] {name}：" if total > 1 else ""
                elif kind == "progress":
                    event: ProgressEvent = payload
                    if event.total_seconds > 0:
                        progress_var.set(100.0 * event.completed_seconds / event.total_seconds)
                    status_var.set(prefix["text"] + event.message)
                elif kind == "done":
                    completed, failed = payload
                    progress_var.set(100.0)
                    prefix["text"] = ""
                    start_button.configure(state="normal")
                    if failed:
                        status_var.set(f"完成 {len(completed)} 个，失败 {len(failed)} 个")
                        detail = "\n".join(
                            f"{config.input_path.name}：{message}" for config, message in failed
                        )
                        messagebox.showwarning(
                            "部分完成", f"成功 {len(completed)} 个，失败 {len(failed)} 个：\n\n{detail}"
                        )
                    elif len(completed) == 1:
                        status_var.set(f"完成：{completed[0][1]}")
                        messagebox.showinfo("转写完成", f"输出目录：\n{completed[0][1]}")
                    else:
                        status_var.set(f"完成 {len(completed)} 个文件")
                        detail = "\n".join(str(output) for _, output in completed)
                        messagebox.showinfo("转写完成", f"{len(completed)} 个输出目录：\n{detail}")
                elif kind == "error":
                    status_var.set("转写失败，可修正后重试")
                    prefix["text"] = ""
                    start_button.configure(state="normal")
                    messagebox.showerror("转写失败", payload)
        except queue.Empty:
            pass
        root.after(120, poll_messages)

    start_button = ttk.Button(frame, text="开始转写", command=start)
    start_button.grid(row=7, column=0, columnspan=3, pady=(18, 0))
    root.after(120, poll_messages)
    root.mainloop()
