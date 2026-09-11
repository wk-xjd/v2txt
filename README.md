# v2txt

把长时间交接视频或音频在本地转换为带时间戳的 JSON、SRT 和 Markdown。工具不做摘要、不删减、不纠错，也不会上传媒体内容。

需要在 Windows x64 构建机生成产物、再交付到 ThinkPad 验收时，从 [WINDOWS_HANDOFF.md](WINDOWS_HANDOFF.md) 开始。ThinkPad 是产品目标机，不是开发设备。

## 非开发者直接使用

从 `artifacts/` 取得对应平台的 ZIP 并完整解压（不能只单独复制可执行文件）：

- Windows 11 x64：双击 `v2txt/v2txt.exe`。
- macOS Apple Silicon：打开终端执行 `v2txt/v2txt`；未签名内部包首次运行可能需要在“隐私与安全性”中允许。

无参数启动是简单图形界面；传入视频路径则是 CLI。便携包已包含 ffmpeg、ffprobe 和 `base`、`small`、`medium` 三档模型，不需要安装 Python、uv，也不需要联网下载这三档模型。

## 支持平台

- 主要平台：Windows 11 x64。
- 次要平台：macOS 14+ ARM64（Apple Silicon）。
- Python：由 uv 自动安装并锁定为 3.11.x。
- 不保证 Intel Mac、Windows ARM、DRM 媒体或本机 ffmpeg 无法解码的格式。

常见 MP4、MOV、MKV、WebM、AVI、WMV、FLV、M4V、MPEG、TS、MTS、M2TS、3GP、MP3、M4A、AAC、WAV、FLAC、OGG、Opus 和 WMA 均交给 ffmpeg 实际探测，不按扩展名拒绝文件。

## 开发环境安装

### Windows 11 x64

在 PowerShell 中执行：

```powershell
winget install astral-sh.uv
winget install Gyan.FFmpeg
```

关闭并重新打开 PowerShell，进入项目目录：

```powershell
uv sync --frozen
uv run v2txt --help
```

### macOS ARM64

```bash
brew install uv ffmpeg
uv sync --frozen
uv run v2txt --help
```

源码运行时，首次使用某个模型会从 Hugging Face 下载模型权重；之后复用本机缓存。便携包已经内置 `base`、`small`、`medium`。公司环境如果限制网络，也可以复制 CTranslate2 模型目录。

也可以把 CTranslate2 格式的离线模型按名称放在统一目录中：

```text
models/
├── base/
├── small/
├── medium/
└── large-v3/
```

然后设置环境变量。Windows PowerShell：

```powershell
$env:HANDOVER_MODEL_DIR = "D:\models"
uv run v2txt meeting.mp4 --model small
```

macOS：

```bash
HANDOVER_MODEL_DIR=/path/to/models uv run v2txt meeting.mp4 --model small
```

环境变量存在时，对应的 `<目录>/<模型名>` 必须存在；否则工具会明确报错，不会悄悄改用其他权重。

## 使用

```bash
# 便携包：默认中文、small 模型，并显示进度条
v2txt meeting.mp4

# 源码开发环境：默认中文、small 模型
uv run v2txt meeting.mp4

# 更快或更准确
uv run v2txt meeting.mp4 --model base
uv run v2txt meeting.mp4 --model medium
uv run v2txt meeting.mp4 --model large-v3

# 自动检测语言
uv run v2txt meeting.mp4 --language auto

# 提示技术名词
uv run v2txt meeting.mp4 --prompt "KDockPanelHostProxy, Cowork, WebView"

# 指定输出目录
uv run v2txt meeting.mp4 -o output

# 批量：一次处理多个文件，模型只加载一次
uv run v2txt a.mp4 b.mp4 c.mp4

# 批量指定输出父目录：生成 out/<名称>_transcript/
uv run v2txt a.mp4 b.mp4 -o out
```

批量模式（命令行传多个文件，或界面里一次选择多个文件）逐个转写并各自输出；单个文件失败不会中断其余文件，结尾打印成功/失败汇总，退出码取第一个失败的错误码。多个文件时 `-o` 是父目录，每个文件生成 `<名称>_transcript` 子目录；单个文件时 `-o` 仍是输出目录本身。界面多选后输出目录留空即可输出到各自视频旁。

模型建议：

| 模型 | 速度 | 准确率 | 用途 |
|---|---|---|---|
| `base` | 最快 | 较低 | 快速预览、清晰录音 |
| `small` | 较快 | 较好 | 默认，普通中文交接视频 |
| `medium` | 慢 | 更好 | 重要视频、术语较多 |
| `large-v3` | 很慢 | 最高 | 高性能机器或最高准确率需求 |

低配 X1 Carbon 建议从 `small` 开始。`large-v3` 在 CPU 上可能耗时很长。

中文（`--language zh`，默认）会在解码前注入“以下是普通话的句子。”提示以偏向简体输出；`--prompt` 提供的术语会拼接在该提示之后。写入结果前，中文转写会用 OpenCC 把残留繁体统一转换为简体；自动识别为其他语言时不做转换。旧版本已完成的分块检查点不会补做转换，跨版本续跑请换新输出目录或加 `--force`。

## 构建便携包

macOS ARM64 在 macOS 主机执行 `scripts/build_macos.sh`；Windows x64 必须在 Windows x64 构建机执行下列命令：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1 -VideoPath testvideo/test.mp4
```

两个脚本都从锁文件安装依赖，从国内 ModelScope 下载并校验 `base`、`small`、`medium`，加入 ffmpeg/ffprobe 后在 `artifacts/` 生成 ZIP。Windows 命令还会让打包后的 `.exe` 真实转写测试视频并核对三种输出。PyInstaller 不是跨平台编译器，因此 macOS 不能直接生成可信的 Windows `.exe`。

## 输出

默认创建 `<视频名>_transcript/`：

```text
meeting_transcript/
├── transcript.json   完整结构化 segment 和秒级时间戳
├── transcript.srt    标准字幕
├── timeline.md       约 60 秒一段的时间线文本
└── .work/            断点恢复状态
```

长视频每 15 分钟形成一个音频块。中断后重新执行完全相同的命令，会跳过已完成的块。修改模型、语言或 prompt 时请使用新的输出目录；若确定要覆盖旧任务，可加 `--force`。`--force` 不会删除输入视频或输出目录中的未知文件。

## Windows 构建与 ThinkPad 交付验收

Windows `.exe` 在任意 Windows 11 x64 构建机生成，不要求使用 ThinkPad 构建。构建后把完整 ZIP 复制到目标 ThinkPad；目标机只需解压运行，不需要 Git、uv、Python 或系统 ffmpeg。

构建机运行仓库验收：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify_windows.ps1 -VideoPath C:\path\to\test.mp4
```

目标 ThinkPad 解压后双击 `v2txt.exe` 做最终 GUI 和性能验收。便携包还包含 `collect_windows_info.bat`，双击后会在包内生成 `v2txt-machine-info.txt`；该文件不收集序列号、产品密钥、用户文件或网络配置。

## 常见问题

- `未找到 ffmpeg/ffprobe`：安装 ffmpeg 后重新打开终端。
- 模型首次运行很慢：正在下载权重；下载完成后会缓存。
- 模型下载临时断开：工具会自动重试三次；持续失败时可使用上述离线模型目录。
- 转写速度慢：先改用 `--model base`；关闭其他高 CPU 占用程序。
- 输出目录任务冲突：保持原参数继续，换新目录，或确认后加 `--force`。
- 视频没有声音：工具会明确报告“没有可用的音频流”，不会生成空文档。
