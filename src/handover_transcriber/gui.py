from __future__ import annotations

import queue
import threading
from pathlib import Path
from typing import Any

from .errors import HandoverError
from .models import ALLOWED_MODELS, ProgressEvent, TaskConfig
from .service import TranscriptionService


def create_config(
    input_text: str,
    output_text: str,
    model: str,
    language: str,
    prompt: str,
) -> TaskConfig:
    input_path = Path(input_text).expanduser()
    if not input_path.is_file():
        raise ValueError("请选择有效的视频或音频文件")
    output = Path(output_text).expanduser() if output_text.strip() else None
    return TaskConfig.create(
        input_path,
        output_dir=output,
        model=model,
        language=None if language.strip().lower() == "auto" else language.strip() or "zh",
        prompt=prompt.strip() or None,
    )


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

    frame = ttk.Frame(root, padding=18)
    frame.pack(fill="both", expand=True)
    frame.columnconfigure(1, weight=1)

    def choose_input() -> None:
        selected = filedialog.askopenfilename(
            title="选择视频或音频",
            filetypes=[
                ("常见媒体", "*.mp4 *.mov *.mkv *.webm *.avi *.mp3 *.m4a *.wav *.flac *.ogg"),
                ("所有文件", "*.*"),
            ],
        )
        if selected:
            input_var.set(selected)
            output_var.set(str(Path(selected).with_name(f"{Path(selected).stem}_transcript")))

    def choose_output() -> None:
        selected = filedialog.askdirectory(title="选择输出目录")
        if selected:
            output_var.set(selected)

    ttk.Label(frame, text="输入文件").grid(row=0, column=0, sticky="w", pady=6)
    ttk.Entry(frame, textvariable=input_var).grid(row=0, column=1, sticky="ew", padx=8)
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

    def worker(config: TaskConfig) -> None:
        try:
            output = TranscriptionService().run(
                config, on_progress=lambda event: messages.put(("progress", event))
            )
            messages.put(("done", output))
        except (HandoverError, ValueError) as exc:
            messages.put(("error", str(exc)))
        except Exception as exc:
            messages.put(("error", f"意外错误：{exc}"))

    def start() -> None:
        try:
            config = create_config(
                input_var.get(),
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
        threading.Thread(target=worker, args=(config,), daemon=True).start()

    def poll_messages() -> None:
        try:
            while True:
                kind, payload = messages.get_nowait()
                if kind == "progress":
                    event: ProgressEvent = payload
                    if event.total_seconds > 0:
                        progress_var.set(100.0 * event.completed_seconds / event.total_seconds)
                    status_var.set(event.message)
                elif kind == "done":
                    progress_var.set(100.0)
                    status_var.set(f"完成：{payload}")
                    start_button.configure(state="normal")
                    messagebox.showinfo("转写完成", f"输出目录：\n{payload}")
                elif kind == "error":
                    status_var.set("转写失败，可修正后重试")
                    start_button.configure(state="normal")
                    messagebox.showerror("转写失败", payload)
        except queue.Empty:
            pass
        root.after(120, poll_messages)

    start_button = ttk.Button(frame, text="开始转写", command=start)
    start_button.grid(row=7, column=0, columnspan=3, pady=(18, 0))
    root.after(120, poll_messages)
    root.mainloop()
