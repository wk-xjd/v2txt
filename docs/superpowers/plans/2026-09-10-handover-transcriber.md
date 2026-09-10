# Handover Transcriber Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 5 小时内交付一个以 Windows 11 x64 为主要平台、兼容 macOS 14+ ARM64、支持断点恢复并输出 JSON/SRT/Markdown 的本地视频转写 CLI。

**Architecture:** Typer CLI 调用独立的 `TranscriptionService`；服务依次使用 ffprobe/ffmpeg、检查点仓库、faster-whisper 后端和纯输出渲染器。外部进程与模型后端通过窄接口隔离，使自动测试无需下载模型。

**Tech Stack:** Python 3.11.x, uv 0.11+, faster-whisper 1.2.1, Typer 0.27.2, Rich 15.0.0, pytest 9.1.1, ffmpeg/ffprobe

**Spec:** `docs/superpowers/specs/2026-09-10-v2txtr-design.md`

## Global Constraints

- `requires-python = ">=3.11,<3.12"`；`.python-version` 为 `3.11`。
- 所有直接依赖使用 `==`，完整依赖写入并提交 `uv.lock`。
- 锁定的原生依赖必须同时提供 Python 3.11 `win_amd64` 和 `macOS arm64` wheel；第一版不承诺 Intel Mac 或 Windows ARM64。
- CPU 固定使用 `int8`；模型仅允许 `base`、`small`、`medium`、`large-v3`，默认 `small`。
- 不摘要、不纠错、不删减，segment 只允许去除首尾空白。
- 不按扩展名拒绝媒体；是否可处理由 ffprobe/ffmpeg 决定。
- `testvideo/`、模型缓存及真实转写输出不得提交 Git。
- 所有功能执行 RED → GREEN → REFACTOR；每个任务结束运行完整测试。

## File Map

```text
pyproject.toml                       项目、精确依赖、CLI 入口
.python-version                      uv Python minor 约束
.gitignore                           本地视频、输出、缓存与系统文件
src/handover_transcriber/
  __init__.py                        版本
  models.py                          TaskConfig/MediaInfo/Chunk/Segment/ProgressEvent
  errors.py                          领域错误与退出码
  outputs.py                         规范化及 JSON/SRT/Markdown 渲染
  media.py                           ffprobe/ffmpeg 边界
  checkpoint.py                      指纹、清单、原子存储、安全清理
  transcriber.py                     后端协议与 faster-whisper 实现
  service.py                         可供 CLI/Web 复用的编排服务
  cli.py                             Typer/Rich 适配
  gui.py                             Tk 简易桌面界面
  launcher.py                        GUI/CLI 双入口和离线资源发现
tests/                               对应模块测试与端到端假后端测试
README.md                            Windows/macOS 安装和使用
scripts/verify_windows.ps1           目标 ThinkPad 一键实机验收
scripts/build_macos.sh               macOS ARM64 便携包
scripts/build_windows.ps1            Windows x64 便携包
docs/validation/testvideo-validation.md  真实视频验收结果
```

---

### Task 1: uv 项目骨架、模型与 CLI 参数

**Files:**
- Create: `pyproject.toml`, `.python-version`, `.gitignore`
- Create: `src/handover_transcriber/__init__.py`, `models.py`, `errors.py`, `cli.py`
- Test: `tests/test_cli.py`, `tests/test_models.py`

**Interfaces:**
- Produces: `TaskConfig`, `MediaInfo`, `AudioChunk`, `RawSegment`, `Segment`, `ProgressEvent`, `HandoverError`; `app: typer.Typer`

- [ ] **Step 1: 创建环境元数据和忽略规则**

  `pyproject.toml` 精确声明 `faster-whisper==1.2.1`、`typer==0.27.2`、`rich==15.0.0`、开发依赖 `pytest==9.1.1`，入口为 `v2txt = "handover_transcriber.cli:app"`。写入 `.python-version` 的 `3.11`；忽略 `.venv/`、`.DS_Store`、`testvideo/`、`*_transcript/`、`.local-validation/`、`.pytest_cache/`、`__pycache__/`。

- [ ] **Step 2: 写失败测试并确认 RED**

  测试默认模型/语言、四种模型接受、非法模型退出码 2、输入目录被拒绝、任意扩展名普通文件可进入服务边界。执行：

  ```bash
  uv lock
  uv sync --frozen
  uv run pytest tests/test_models.py tests/test_cli.py -q
  ```

  预期因 `handover_transcriber` 尚不存在而失败。

- [ ] **Step 3: 最小实现并确认 GREEN**

  `TaskConfig` 使用冻结 dataclass；`ModelName = Literal["base", "small", "medium", "large-v3"]`。CLI 将 `auto` 转为后端使用的 `None`，默认输出为输入同级 `<stem>_transcript`，只验证 `is_file()`，不验证扩展名。执行上述测试和 `uv run v2txt --help`。

- [ ] **Step 4: 完整测试并提交**

  ```bash
  uv run pytest -q
  git add pyproject.toml uv.lock .python-version .gitignore src tests
  git commit -m "feat: scaffold transcriber CLI"
  ```

---

### Task 2: Segment 规范化与三种输出

**Files:**
- Create: `src/handover_transcriber/outputs.py`
- Test: `tests/test_outputs.py`

**Interfaces:**
- Produces: `normalize_segments(parts, duration) -> list[Segment]`, `write_outputs(result, output_dir) -> None`, `format_srt_time(seconds) -> str`, `format_clock(seconds) -> str`
- Consumes: `RawSegment`, `Segment`, `MediaInfo`, `TaskConfig`

- [ ] **Step 1: 写失败测试并确认 RED**

  使用手算字面量验证：毫秒进位、25 小时时间戳；块偏移、排序、重新编号、空白过滤、时长夹取；JSON 中文与 schema；SRT 序号；Markdown 60 秒窗口及 15 秒静音断组。执行 `uv run pytest tests/test_outputs.py -q`，预期导入失败。

- [ ] **Step 2: 实现纯转换函数并确认 GREEN**

  `normalize_segments` 输入 `(chunk_start, raw_segments)` 序列；最终 segment 满足 `0 <= start <= end <= duration + 1`。三个输出先写同目录 `.tmp` 再 `Path.replace()`；JSON 使用 `ensure_ascii=False, indent=2`；Markdown 只以单空格连接原 segment 文本。

- [ ] **Step 3: 完整测试并提交**

  ```bash
  uv run pytest -q
  git add src/handover_transcriber/outputs.py tests/test_outputs.py
  git commit -m "feat: render transcript outputs"
  ```

---

### Task 3: 媒体探测与音频分块

**Files:**
- Create: `src/handover_transcriber/media.py`
- Test: `tests/test_media.py`

**Interfaces:**
- Produces: `MediaTools.probe(path) -> MediaInfo`, `MediaTools.create_chunks(path, audio_dir, duration) -> list[AudioChunk]`
- Consumes: `MediaInfo`, `AudioChunk`, `MediaError`

- [ ] **Step 1: 写失败测试并确认 RED**

  用测试目录内的可执行假程序模拟 ffprobe/ffmpeg，验证：缺程序、无音频流、损坏 JSON、错误后缀仍被探测、包含空格/中文的路径作为单个 argv、分块清单按序返回。执行 `uv run pytest tests/test_media.py -q`。

- [ ] **Step 2: 实现探测与分块并确认 GREEN**

  ffprobe argv 固定为：

  ```python
  ["ffprobe", "-v", "error", "-show_entries",
   "format=duration,format_name:stream=index,codec_type,codec_name",
   "-of", "json", str(input_path)]
  ```

  ffmpeg 使用 `-map 0:a:0 -vn -ac 1 -ar 16000 -c:a pcm_s16le -f segment -segment_time 900 -reset_timestamps 1 chunk-%05d.wav`。所有命令用 argv 和 `shell=False`，stderr 截断后映射为 `MediaError(exit_code=3)`。

- [ ] **Step 3: 若本机无 ffmpeg，验证可操作错误；完整测试并提交**

  ```bash
  uv run v2txt testvideo/test.mp4
  uv run pytest -q
  git add src/handover_transcriber/media.py tests/test_media.py
  git commit -m "feat: probe media and create audio chunks"
  ```

---

### Task 4: 检查点与安全恢复

**Files:**
- Create: `src/handover_transcriber/checkpoint.py`
- Test: `tests/test_checkpoint.py`

**Interfaces:**
- Produces: `CheckpointStore.open(config, media, force) -> ResumeState`, `register_chunks(chunks)`, `save_chunk(index, detected_language, segments)`, `pending_chunks()`, `load_parts()`, `cleanup_audio()`
- Consumes: `TaskConfig`, `MediaInfo`, `AudioChunk`, `RawSegment`, `CheckpointError`

- [ ] **Step 1: 写失败测试并确认 RED**

  覆盖相同指纹恢复；大小、mtime、模型、语言、prompt、分块参数任一变化时报冲突；临时 JSON 不替代有效状态；块结果先于 completed 标记；`--force` 保留未知文件；符号链接不被递归删除。执行 `uv run pytest tests/test_checkpoint.py -q`。

- [ ] **Step 2: 实现任务指纹和原子存储并确认 GREEN**

  manifest schema 版本为 1，指纹含规范化绝对路径、`st_size`、`st_mtime_ns`、媒体时长、模型、语言、prompt、16000 Hz/mono/PCM16/900 秒。JSON 使用同目录临时文件、flush、`os.fsync()`、`os.replace()`。`--force` 只清理 `.work/`、`transcript.json`、`transcript.srt`、`timeline.md`，遇到符号链接只 unlink 链接本身。

- [ ] **Step 3: 完整测试并提交**

  ```bash
  uv run pytest -q
  git add src/handover_transcriber/checkpoint.py tests/test_checkpoint.py
  git commit -m "feat: persist resumable checkpoints"
  ```

---

### Task 5: faster-whisper 后端

**Files:**
- Create: `src/handover_transcriber/transcriber.py`
- Test: `tests/test_transcriber.py`

**Interfaces:**
- Produces: `Transcriber` protocol with `transcribe(path, language, prompt) -> ChunkTranscript`; `FasterWhisperTranscriber(model_name)`
- Consumes: `RawSegment`, `TranscriptionError`

- [ ] **Step 1: 写失败测试并确认 RED**

  注入假的 `WhisperModel` 工厂，验证构造固定为 `device="cpu", compute_type="int8"`；转写启用 `vad_filter=True`、`beam_size=5`、`condition_on_previous_text=True`；`auto` 传 `language=None`；后端 segment 只 strip 首尾空白并保留语气词。执行 `uv run pytest tests/test_transcriber.py -q`。

- [ ] **Step 2: 实现惰性模型加载并确认 GREEN**

  首次转写才导入并创建 WhisperModel；一次任务复用模型。捕获模型下载、加载和生成器迭代异常，统一转为退出码 4 的 `TranscriptionError`，不吞掉 `KeyboardInterrupt`。

- [ ] **Step 3: 完整测试并提交**

  ```bash
  uv run pytest -q
  git add src/handover_transcriber/transcriber.py tests/test_transcriber.py
  git commit -m "feat: add faster-whisper backend"
  ```

---

### Task 6: 服务编排、恢复和 CLI 进度

**Files:**
- Create: `src/handover_transcriber/service.py`
- Modify: `src/handover_transcriber/cli.py`
- Create: `tests/fakes.py`
- Test: `tests/test_service.py`, `tests/test_cli_integration.py`

**Interfaces:**
- Produces: `TranscriptionService(media, checkpoint_factory, transcriber_factory).run(config, on_progress=None) -> Path`
- Consumes: Task 2–5 的公开接口

- [ ] **Step 1: 写失败端到端测试并确认 RED**

  使用真实文件系统和确定性假媒体/假转写后端，验证完整输出、按原视频时间偏移、第二块失败后恢复仅处理第二块、完成后删除音频但保留 segment 检查点、参数冲突、Ctrl+C 简洁退出。测试断言最终文件与退出码，不断言假对象自身。执行 `uv run pytest tests/test_service.py tests/test_cli_integration.py -q`。

- [ ] **Step 2: 实现服务顺序并确认 GREEN**

  固定编排顺序：validate → probe → open checkpoint → ensure chunks → register → transcribe pending → atomically save each chunk → normalize → write outputs → cleanup audio。进度事件包含 `stage`、`completed_seconds`、`total_seconds`、`message`。CLI 捕获 `HandoverError` 返回其退出码，捕获 Ctrl+C 返回 130，未知异常返回 1 并指向日志；Rich 只在 TTY 显示动态进度。

- [ ] **Step 3: 变异检查、完整测试和提交**

  临时改变一个块的时间偏移和 completed 写入顺序，确认对应测试会失败，再还原。随后：

  ```bash
  uv run pytest -q
  git add src/handover_transcriber tests
  git commit -m "feat: orchestrate resumable transcription"
  ```

---

### Task 7: 文档、格式兼容、真实视频验收与调优

**Files:**
- Create: `README.md`
- Create: `scripts/verify_windows.ps1`
- Create: `docs/validation/testvideo-validation.md`
- Test: `tests/test_real_media.py`（默认跳过，仅显式环境变量启用）

**Interfaces:**
- Validates: 安装、常见容器、真实 `base`/`small`、最终用户命令

- [ ] **Step 1: 写真实媒体测试入口并确认默认测试不会下载模型**

  `tests/test_real_media.py` 仅在 `HANDOVER_RUN_REAL_MEDIA=1` 时执行；否则 pytest skip。完整测试须在断网条件下仍可运行。

- [ ] **Step 2: 安装 ffmpeg 并生成兼容样本**

  macOS 使用 `brew install ffmpeg`；Windows README 提供 `winget install Gyan.FFmpeg`。从短合成音频生成 MP4、MOV、MKV、WebM、AVI、MP3、M4A、WAV、FLAC、OGG，逐个运行媒体探测和标准化测试。

- [ ] **Step 3: 跑真实 testvideo 基线**

  ```bash
  /usr/bin/time -p uv run v2txt testvideo/test.mp4 --model base --output .local-validation/base
  /usr/bin/time -p uv run v2txt testvideo/test.mp4 --model small --output .local-validation/small
  ```

  记录 ffmpeg、uv、Python、模型、耗时、segment 数；用校验脚本断言 duration 与 280.269 秒误差不超过一秒、时间戳单调且三种输出顺序一致。

- [ ] **Step 4: 抽查并仅在有证据时调优**

  抽查开头/中段/结尾各两段。若发现漏句、重复或上下文污染，分别只改变一个内部参数后重跑 `small`；接受条件为问题改善且耗时回退不超过 20%，否则恢复 `vad_filter=True, beam_size=5, condition_on_previous_text=True`。

- [ ] **Step 5: README 与验收记录**

  README 给出 uv、ffmpeg、首次模型下载、四种模型成本、输出说明、恢复、`--force`、Windows/macOS 命令和隐私说明。`scripts/verify_windows.ps1` 在 PowerShell 中依次检查 x64、`uv sync --frozen`、`uv run pytest -q`、ffmpeg/ffprobe、CLI 帮助，并用用户传入的视频执行 `base` 真实转写。验收文档只写统计和短例子，不收录逐字稿。

- [ ] **Step 6: 最终验证和提交**

  ```bash
  uv lock --check
  uv sync --frozen
  uv run pytest -q
  uv run v2txt --help
  uv run v2txt --version
  git status --short
  ```

  在目标 ThinkPad 上执行 `powershell -ExecutionPolicy Bypass -File scripts/verify_windows.ps1 -VideoPath C:\path\to\test.mp4`；该命令未成功前只报告 macOS 验证结果，不声明 Windows 实机通过。

  确认 `testvideo/`、`.local-validation/` 和模型缓存均未暂存，然后：

  ```bash
  git add README.md docs/validation tests/test_real_media.py src pyproject.toml uv.lock .gitignore
  git commit -m "docs: add setup and validation results"
  ```

---

### Task 8: v2txt 双入口、离线模型与便携包

**Files:**
- Modify: `pyproject.toml`, `uv.lock`, `src/handover_transcriber/cli.py`, `service.py`, `transcriber.py`, `media.py`
- Create: `src/handover_transcriber/gui.py`, `launcher.py`, `scripts/v2txt_entry.py`
- Create: `scripts/build_macos.sh`, `scripts/build_windows.ps1`, `packaging/使用说明.txt`, `artifacts/README.md`
- Test: `tests/test_gui.py`, `tests/test_packaging.py` and progress tests

- [x] 将安装命令缩短为 `v2txt`；无参数启动 Tk GUI，有参数进入 Typer CLI。
- [x] 后端逐 segment 上报处理位置，CLI 使用 Rich 进度条，GUI 使用同一事件更新进度。
- [x] 从可执行文件旁发现 `models/small`，从 PyInstaller 资源目录发现 ffmpeg/ffprobe。
- [x] 精确锁定 PyInstaller，编写 macOS ARM64 与 Windows x64 原生构建脚本。
- [x] 便携目录内放入 `base`、`small`、`medium` 三档模型和用户说明，再压缩为 ZIP；`large-v3` 保持可选外置。
- [x] 在 macOS ARM64 构建并执行成品的版本与真实视频转写测试。
- [ ] 在目标 ThinkPad Windows 11 x64 上构建 `.exe`，执行真实视频验收后归档 ZIP。
