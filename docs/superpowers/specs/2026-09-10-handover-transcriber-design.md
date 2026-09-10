# Handover Transcriber 技术设计

## 1. 目标

构建一个 Windows 与 macOS 通用的本地命令行工具，把长时间交接视频或音频忠实转换为带时间线的文本。工具只负责语音识别和格式整理，不做摘要、内容删减、技术纠错或语义改写。

第一版以低配 ThinkPad X1 Carbon 的 CPU 运行环境为性能基线，同时兼容 Apple Silicon Mac。所有媒体和转写数据均在本机处理，不上传到第三方服务。

## 2. 成功标准

- 接受常见视频和音频容器作为输入；实际可解码能力由本机 `ffmpeg` 构建决定，工具不依赖扩展名猜测媒体内容。
- 在 Windows 与 macOS 上使用同一套 Python 代码运行。
- 支持 `base`、`small`、`medium`、`large-v3` 四种 Whisper 模型，默认使用 `small`。
- 默认使用 CPU 和 `int8` 计算，不要求 NVIDIA 显卡。
- 输出结构化 JSON、标准 SRT 字幕和可阅读的时间线 Markdown。
- 每条识别内容可追溯到原视频中的开始和结束时间。
- 长任务中断后可从已完成的音频分块继续，避免重复处理全部视频。
- 不改写、不总结、不纠错、不主动删除识别文本。
- CLI 和核心服务解耦，未来 Web 界面可直接调用 Python API。

## 3. 非目标

第一版不包含：

- 桌面界面或 Web 界面。
- 说话人识别。
- 视频关键帧、OCR 或画面理解。
- 自动摘要、主题聚类或正式交接文档生成。
- 云端转写服务。
- 多文件批量队列。
- 模型训练或领域微调。

## 4. 技术选型

- Python 3.11.x；`pyproject.toml` 使用 `>=3.11,<3.12` 限定解释器版本，`.python-version` 指定 `3.11`。
- `uv` 负责创建环境、安装依赖、运行命令和生成可复现的 `uv.lock`。
- `faster-whisper` 负责本地语音识别。
- 系统安装的 `ffmpeg` 和 `ffprobe` 负责媒体探测、音频标准化和分块。
- `Typer` 提供 CLI 参数解析、帮助文本和退出码。
- `Rich` 显示阶段、进度和可操作的错误信息。
- `pytest` 用于单元测试和集成测试。

选择 `faster-whisper` 的原因是它基于 CTranslate2，可在 Windows/macOS 的 CPU 上使用 `int8`，并提供时间戳、VAD 和模型缓存能力。第一版不为 Apple Silicon 单独引入 MLX 后端，以保持跨平台行为一致。

### 4.1 Python 与依赖版本策略

- 仓库提交 `pyproject.toml`、`.python-version` 和 `uv.lock`。
- `pyproject.toml` 中所有直接运行时依赖和开发依赖均使用精确版本约束 `==`，不使用浮动的 `*`、`^`、`~=` 或无上限范围。
- `uv.lock` 锁定完整的传递依赖集合，并纳入 Git；Windows 与 macOS 使用同一份锁文件。
- 开发、测试和运行统一通过 `uv sync`、`uv run pytest` 和 `uv run handover-transcribe`，不维护第二套 `requirements.txt`。
- 依赖升级必须显式修改精确版本并重新执行 `uv lock` 与完整测试，不能在普通安装过程中隐式升级。
- Whisper 模型权重不属于 Python 包依赖，不进入 `uv.lock`；其名称和任务参数记录在检查点中，首次使用时下载到模型缓存。

Python 3.11 作为第一版唯一支持的 minor 版本，减少 `faster-whisper`、CTranslate2 与平台原生 wheel 组合带来的差异。后续支持新的 Python minor 版本时，需在 Windows 和 macOS 上完成测试后扩大 `requires-python` 范围。

### 4.2 媒体兼容范围

工具把媒体能力交给 `ffprobe`/`ffmpeg` 判断，不设置扩展名白名单。第一版明确覆盖以下常见输入：

- 视频：MP4、MOV、MKV、WebM、AVI、WMV、FLV、M4V、MPEG/MPG、TS/MTS/M2TS、3GP。
- 音频：MP3、M4A、AAC、WAV、FLAC、OGG/Opus、WMA。

“覆盖”表示：只要本机 `ffprobe` 能读取容器、检测到至少一条音频流，且 `ffmpeg` 能把该音频流解码为 PCM WAV，后续流程就必须正常工作。文件扩展名大小写不影响处理，扩展名错误但内容可被 `ffprobe` 识别时也允许处理。

DRM 加密媒体、损坏文件、无音频流视频，以及本机 `ffmpeg` 未编译对应解码器的格式不在保证范围内。遇到这些情况时，工具输出可操作的探测或解码错误，不把它们统一误报为“不支持的扩展名”。

## 5. 用户界面

安装后提供 `handover-transcribe` 命令：

```bash
uv run handover-transcribe video.mp4
uv run handover-transcribe video.mp4 --model base
uv run handover-transcribe video.mp4 --model medium
uv run handover-transcribe video.mp4 --model large-v3
uv run handover-transcribe video.mp4 --language auto
uv run handover-transcribe video.mp4 --prompt "KDockPanelHostProxy, Cowork, WebView"
uv run handover-transcribe video.mp4 --output ./output
uv run handover-transcribe video.mp4 --force
```

### 5.1 参数

| 参数 | 默认值 | 含义 |
|---|---:|---|
| `INPUT` | 必填 | 单个本地视频或音频文件；格式由 `ffprobe` 探测 |
| `--model` | `small` | `base`、`small`、`medium` 或 `large-v3` |
| `--language` | `zh` | ISO 语言代码；`auto` 表示自动检测 |
| `--prompt` | 空 | 提示模型识别项目名、函数名和英文缩写 |
| `--output`, `-o` | `<输入文件名>_transcript` | 输出目录 |
| `--force` | `false` | 删除该输出目录内与当前任务匹配的旧工作状态后重新运行 |
| `--version` | — | 显示工具版本 |

第一版不开放设备、计算类型、beam size、VAD 阈值等底层参数。内部固定使用 CPU、`int8` 和 VAD，减少错误配置。未来如有明确需求，可增加高级配置文件而不改变现有 CLI。

### 5.2 退出码

- `0`：成功生成所有输出。
- `2`：CLI 参数错误，或输入路径不是可读取的普通文件。
- `3`：缺少 `ffmpeg`/`ffprobe` 或媒体无法读取。
- `4`：模型加载或转写失败。
- `5`：输出目录、磁盘空间或文件写入失败。

## 6. 系统架构

```text
CLI
 │
 ▼
TranscriptionService
 ├── MediaProbe       检查输入、读取时长和媒体信息
 ├── AudioChunker     标准化音频并切分为可恢复的小块
 ├── WhisperBackend   加载模型并逐块转写
 ├── CheckpointStore  原子保存任务清单与分块结果
 └── OutputWriter     生成 JSON、SRT 和 Markdown
```

### 6.1 模块边界

- `cli.py`：仅解析参数、调用服务、渲染进度并将领域错误映射为退出码。
- `service.py`：编排探测、分块、转写、恢复和最终输出，不包含 CLI 表现逻辑。
- `media.py`：封装 `ffprobe` 和 `ffmpeg` 子进程，返回结构化媒体信息和音频块清单。
- `transcriber.py`：定义转写后端协议并提供 `faster-whisper` 实现。
- `checkpoint.py`：定义任务指纹、清单格式、原子写入和恢复规则。
- `outputs.py`：纯函数式地把规范化 segment 渲染为 JSON、SRT 和 Markdown。
- `models.py`：保存内部数据模型和四种允许的模型名称。
- `errors.py`：保存可预期的领域异常及其退出码。

核心模块不依赖 Typer 或 Rich，因此未来 FastAPI/Web 层可以直接实例化 `TranscriptionService`，并通过进度回调接收状态。

## 7. 数据流

1. 校验输入路径是可读取的普通文件，并校验输出路径和模型名称；不按扩展名拒绝输入。
2. 查找 `ffmpeg` 与 `ffprobe`，读取媒体时长、格式和音频流信息。
3. 计算任务指纹；若存在兼容检查点则载入，否则创建新任务。
4. 使用 `ffmpeg` 生成 16 kHz、单声道、16-bit PCM WAV 音频块。
5. 按顺序将未完成的音频块交给 `faster-whisper`，使用 VAD 转写。
6. 把块内相对时间加上块起点，得到相对原视频的绝对时间戳。
7. 每完成一个块，原子写入其 segment 文件并更新任务清单。
8. 所有块完成后，合并并校验 segment 顺序，生成三种最终输出。
9. 删除标准化音频块，保留小型任务清单和分块识别结果，支持重新生成输出。

## 8. 长视频分块与恢复

### 8.1 分块策略

标准化音频按 15 分钟切块。该长度使低配 CPU 能定期落盘，同时避免产生过多小文件。每块文件名包含从零开始的序号：

```text
.work/audio/chunk-00000.wav
.work/audio/chunk-00001.wav
```

第一版采用连续、无重叠的音频块。极少数跨越切分点的单词可能被识别得不完整，这是简单可恢复方案的已知权衡。后续可在不改变最终输出格式的情况下加入静音点切分或重叠去重。

### 8.2 任务指纹

检查点记录以下字段：

- 输入文件的规范化绝对路径。
- 输入文件大小和纳秒级修改时间。
- 媒体总时长。
- 模型、语言和 prompt。
- 音频标准化参数及分块时长。
- 检查点格式版本。

输入内容或任何影响识别结果的参数变化时，旧检查点视为不兼容。工具停止并提示用户选择原输出目录对应的参数，或使用 `--force` 重新开始；不会静默混合不同任务的结果。

### 8.3 原子性

所有 JSON 状态先写入同目录临时文件，再通过原子替换发布。清单只有在对应分块结果成功落盘后才标记该块完成。进程被终止时，最多重做当前未提交的音频块。

## 9. 内部数据模型

规范化 segment：

```json
{
  "id": 0,
  "start": 12.34,
  "end": 18.91,
  "text": "大家先看一下这个模块。"
}
```

约束：

- `id` 从零开始，在全局合并后连续递增。
- `start` 和 `end` 是相对原媒体开头的秒数。
- `0 <= start <= end <= duration + 1`；额外一秒容忍媒体容器与音频编码的舍入差异。
- `text` 保留转写后端返回的内容，仅移除首尾空白；不删除语气词、不合并观点。
- 空白 segment 不进入最终输出。

## 10. 输出格式

最终目录示例：

```text
video_transcript/
├── transcript.json
├── transcript.srt
├── timeline.md
└── .work/
    ├── manifest.json
    └── segments/
        ├── chunk-00000.json
        └── chunk-00001.json
```

### 10.1 `transcript.json`

```json
{
  "schema_version": 1,
  "source": {
    "file_name": "video.mp4",
    "duration_seconds": 7234.56
  },
  "transcription": {
    "model": "small",
    "language_requested": "zh",
    "language_detected": "zh",
    "device": "cpu",
    "compute_type": "int8"
  },
  "segments": [
    {
      "id": 0,
      "start": 12.34,
      "end": 18.91,
      "text": "大家先看一下这个模块。"
    }
  ]
}
```

JSON 使用 UTF-8、保留中文字符，并以稳定的两空格缩进输出。源文件只记录文件名，不在最终结果中泄露本机绝对路径。

### 10.2 `transcript.srt`

每个规范化 segment 对应一条字幕。时间使用 `HH:MM:SS,mmm`，支持超过 24 小时的媒体；字幕序号从 1 开始。

```srt
1
00:00:12,340 --> 00:00:18,910
大家先看一下这个模块。
```

### 10.3 `timeline.md`

Markdown 按最多 60 秒的连续时间窗口组合 segment，组合只改变排版，不改写文本。遇到超过 15 秒的静音间隔时提前结束当前段落。

```markdown
# video 时间线转写

- 来源：`video.mp4`
- 时长：02:00:34
- 模型：`small`
- 语言：`zh`

## 00:00:12 - 00:00:58

大家先看一下这个模块。这个模块主要负责……
```

段落文本按 segment 原顺序以单个空格连接。每个标题的时间范围取该组第一个 segment 的开始时间和最后一个 segment 的结束时间。

## 11. 错误处理

- 缺少外部程序时，错误信息包含 Windows/macOS 各自的安装提示。
- 输入无音频流时直接失败，不创建伪造的空转写。
- 容器无法探测或音频无法解码时，保留 `ffprobe`/`ffmpeg` 的简化诊断，指出是容器、音频流还是解码器问题。
- 输出目录已包含不兼容任务时直接失败并解释冲突字段。
- 模型下载或加载失败时保留已生成的音频块和任务状态。
- 单块转写失败时不把该块标记为完成；重新执行会从该块继续。
- 磁盘写入失败时不删除临时音频，便于释放空间后重试。
- Ctrl+C 返回非零状态并显示可继续运行的同一命令，不打印 Python traceback。
- `--force` 只清理当前输出目录中的本工具工作状态和最终输出，不删除输入媒体或输出目录中的未知文件。

意外异常默认显示简短错误和日志文件位置。调试日志不得包含音频内容或完整转写正文。

## 12. 安全与隐私

- 不发起转写数据上传；唯一可能的网络访问是首次从模型仓库下载所选模型。
- 不执行来自文件名、prompt 或媒体元数据的 shell 文本；`ffmpeg` 参数以数组形式传递给子进程。
- 不跟随输出目录内伪装成工作文件的符号链接进行删除。
- 清理操作限定在已验证的 `.work/audio` 和本工具拥有的输出文件。
- 日志记录路径、阶段、耗时和错误，不记录完整转写内容。

## 13. 性能与资源

- `faster-whisper` 在 CPU 上使用 `compute_type="int8"`。
- 每次只转写一个 15 分钟音频块，避免同时占用过多内存和磁盘 I/O。
- 音频块按需生成；第一版允许 `ffmpeg` 一次生成所有块，以简化恢复清单。
- 模型在一次任务中只加载一次。
- Rich 进度按已完成媒体时长计算，不承诺实时速度。
- `large-v3` 在低配 CPU 上可能非常慢，CLI 在开始前显示提示但允许继续。

## 14. 测试策略

### 14.1 单元测试

- 四种模型名称的接受与其他值的拒绝。
- 时间戳格式化，包括毫秒进位、超过一小时和超过 24 小时。
- segment 全局偏移、排序、重新编号和空白过滤。
- 60 秒 Markdown 分组及 15 秒静音断组。
- JSON、SRT、Markdown 的固定样例测试。
- 任务指纹兼容与冲突字段报告。
- 原子检查点写入和不完整临时文件恢复。
- 安全清理仅删除工具拥有的路径。
- 领域异常到 CLI 退出码的映射。

### 14.2 集成测试

- 使用程序生成的短 WAV，经伪转写后端完成完整流水线，验证三种输出。
- 使用伪 `ffmpeg`/`ffprobe` 进程验证命令参数、无音频流和外部程序失败。
- 参数化验证常见视频与音频容器的探测结果均进入相同音频标准化流程，不按扩展名分叉业务逻辑。
- 验证大写扩展名和扩展名错误但可探测的媒体不会被 CLI 提前拒绝。
- 模拟第二个块失败，再次运行时仅处理未完成块。
- 模拟 Ctrl+C，验证已完成检查点保留且不显示 traceback。

测试套件不下载 Whisper 模型，也不依赖真实网络。真实模型的烟雾测试作为手动验收步骤，用数秒中文音频运行 `base` 模型。

## 15. 验收场景

1. 在 Windows 的 CPU 环境使用已安装的 `uv` 执行 `uv sync --frozen`，确认严格按锁文件安装 Python 与依赖，再安装 ffmpeg。
2. 对一个至少包含两段语音和一段静音的中文 MP4 执行默认命令。
3. 使用同一短媒体内容生成 MOV、MKV、WebM、AVI、MP3、M4A、WAV、FLAC 和 OGG 样本，确认均能进入转写流程。
4. 确认生成 JSON、SRT、Markdown，三个文件的文本顺序和时间戳一致。
5. 在长视频处理若干块后中断，再运行相同命令，确认跳过已完成块。
6. 改用 `--model medium` 指向同一输出目录，确认工具拒绝混合结果。
7. 改用新输出目录完成 `medium` 转写。
8. 在 macOS 执行 `uv sync --frozen` 并重复短文件转写，确认依赖解析和输出结构一致。

## 16. 实施拆分

实施计划将按以下可独立验证的工作单元展开，每个单元遵循测试先行：

1. `uv` 项目打包、Python/依赖锁定、领域数据模型、参数约束和 CLI 骨架。
2. 时间戳、segment 规范化及三种最终输出渲染。
3. 媒体探测、ffmpeg 音频标准化与 15 分钟分块。
4. 检查点、任务指纹、原子写入和安全清理。
5. `faster-whisper` 后端与四种模型配置。
6. 服务编排、恢复逻辑、进度事件和错误映射。
7. 端到端 CLI 集成测试、安装说明和真实音频烟雾验收。

## 17. 后续扩展边界

未来 Web 层只需要：

- 构造与 CLI 相同的任务配置。
- 调用 `TranscriptionService.run()`。
- 把服务产生的结构化进度事件转换为 WebSocket 或轮询状态。
- 暴露已有输出文件供下载。

说话人识别、OCR、摘要和批处理均作为独立阶段加入，不修改 `transcript.json` 中已有 segment 的含义。
