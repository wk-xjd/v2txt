# testvideo 真实视频验收记录

## 验收环境

- 日期：2026-09-11（Asia/Shanghai）。
- 开发机：Apple M3，ARM64。
- 操作系统：macOS 26.5.2（Build 25F84）。
- uv：0.11.32。
- Python：uv 管理的 CPython 3.11.15。
- ffmpeg/ffprobe：4.4 ARM64，本地验收副本。
- 锁文件基线：commit `116826b`。
- 输入：`testvideo/test.mp4`，H.264/AAC，280.269 秒，约 9.5 MB。

## 自动验证

- 自动测试：45 passed，1 skipped；跳过项是必须显式启用的真实模型测试。
- 显式启用真实模型测试后：1 passed，耗时 197.84 秒。
- Python 源码编译检查通过。
- `uv build` 成功生成 `handover_transcriber-0.1.0-py3-none-any.whl` 和源码包。
- CLI `--help` 与 `--version` 成功。
- 缺少 ffprobe 时返回退出码 3，并显示 macOS 安装提示。

锁文件中的原生依赖已确认同时包含 Python 3.11 的 macOS ARM64 与 Windows x64 wheel：

| 依赖 | 锁定版本 | macOS ARM64 | Windows x64 |
|---|---:|---:|---:|
| CTranslate2 | 4.8.2 | 有 | 有 |
| PyAV | 18.1.0 | 有 | 有 |
| ONNX Runtime | 1.29.0 | 有 | 有 |
| Tokenizers | 0.23.2 | 有 | 有 |
| NumPy | 2.4.6 | 有 | 有 |

## 格式兼容验证

使用本地 ffmpeg 生成带音频的短样本，再通过项目 `MediaTools.probe()` 实际探测。以下格式全部成功：

| 类型 | 格式 | 探测到的音频 |
|---|---|---|
| 视频 | MP4、MOV、MKV | AAC |
| 视频 | WebM | Opus |
| 视频 | AVI | MP3 |
| 音频 | MP3 | MP3 |
| 音频 | M4A | AAC |
| 音频 | WAV | PCM S16LE |
| 音频 | FLAC | FLAC |
| 音频 | OGG | Vorbis |

媒体路径通过 argv 传递，不使用 shell 拼接；自动测试覆盖空格、中文和错误扩展名。

## 模型端到端结果

| 场景 | 总耗时 | Segment 数 | 结果 |
|---|---:|---:|---|
| `base` 首次运行，含慢速模型下载 | 1155.48 秒 | 168 | 成功 |
| `base` 模型已缓存 | 196.45 秒 | 168 | 成功 |
| `small`，上下文继承开启 | 83.62 秒 | 113 | 成功 |
| `small`，上下文继承关闭，标准 CLI + 离线目录 | 64.47 秒 | 131 | 成功 |

所有最终输出均满足：

- `transcript.json`、`transcript.srt`、`timeline.md` 同时生成。
- JSON 时长为 280.269 秒。
- Segment 开始时间单调递增。
- 所有时间戳均落在允许的媒体范围内。
- 开头、中段和结尾均存在文本，结尾未截断。

人工抽查显示 `base` 存在较多中文同音误识别；`small` 对“不良贷款”等上下文词识别更合理，因此保持 `small` 为默认模型。

## 调优结论

唯一采用的推理参数变更是：

```text
condition_on_previous_text=false
```

在相同 `small` 权重与测试视频上，总耗时从 83.62 秒下降到 64.47 秒，约减少 22.9%。抽查未出现新的连续重复，中后段部分句子更连贯。VAD 保持开启，beam size 保持 5。

下载可靠性方面采用两项改进：默认禁用容易出现 CAS 401 的 Hugging Face Xet 通道；模型加载临时失败最多重试三次。另支持通过 `HANDOVER_MODEL_DIR` 使用离线 CTranslate2 模型目录。

## 尚需目标机确认

当前环境无法执行 Windows 二进制。代码、锁文件和依赖 wheel 已完成 Windows x64 静态验证，但 Windows 实机状态仍为未确认。必须在目标 ThinkPad X1 Carbon 上执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify_windows.ps1 -VideoPath C:\path\to\test.mp4
```

该脚本成功前，不声明 Windows 实机验收完成。

## v2txt 便携包验证

- PyInstaller 6.22.2 已锁入 `uv.lock`。
- macOS ARM64 成品程序、内置 ffmpeg 和 ffprobe 均由 `file` 确认为 Mach-O ARM64。
- 便携目录包含 `models/base`、`models/small`、`models/medium`，清除 `HANDOVER_MODEL_DIR` 后三档均可离线加载。
- 解压目录约 2.2 GB，ZIP 约 2.0 GB；`large-v3` 因单模型约 3.09 GB 保持外置。
- `--version`、`--help` 和更新后的 `testvideo/test.mp4` 完整转写均从成品目录直接运行。
- 修正多进程冻结入口后，再用成品离线转写 20 秒样本：7 个 segment、三种输出齐全，无资源管理子进程告警。
- 使用同一个五秒样本分别从成品内置目录加载 `base`、`small`、`medium`，三次均成功生成全部输出。
- 无参数启动保持运行并显示 Tk 界面，人工中断后正常退出。
- ZIP SHA-256：`0208d4a88d8e9d09f3a41d9322b783a7c41dd1ea58273070c32811b7152ff9de`。

Windows 产物必须由 Windows x64 上的 `scripts/build_windows.ps1` 原生构建；macOS 构建不能替代 Windows 动态库装载和实际 CPU 推理验收。
