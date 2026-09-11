# v2txt Windows 接力说明

更新日期：2026-09-11（Asia/Shanghai）

这份文档用于在 Windows 11 x64 构建环境继续生成产品，再把便携包交付到 ThinkPad 验收和运行。ThinkPad 是产品目标机，不是开发设备。仓库只包含代码、测试、文档和构建脚本；公司视频、转写正文、模型权重及本地二进制产物均被 `.gitignore` 排除。

环境边界：

- 开发设备：当前不是 ThinkPad，可以继续编写和提交跨平台代码。
- Windows 构建机：任意 Windows 11 x64 电脑或 CI，用于运行 uv、测试和 PyInstaller。
- 产品目标机：低配 ThinkPad X1 Carbon，只接收完整便携 ZIP，负责最终功能和性能验收。

## 1. 项目目标

`v2txt` 是本地视频/音频时间线转写工具：

- 忠实转写，不摘要、不删减、不做语义改写。
- 输出 `transcript.json`、`transcript.srt`、`timeline.md`。
- 同一个程序：无参数启动 Tk 图形界面，传入参数时使用 CLI。
- 主要目标平台是 Windows 11 x64 低配 ThinkPad X1 Carbon。
- 次要平台是 macOS ARM64。
- 支持 `base`、`small`、`medium`、`large-v3`，默认 `small`。
- 便携包内置 `base`、`small`、`medium`；`large-v3` 保持外置。
- 默认 CPU `int8`，无需独立显卡。

私有仓库：<https://github.com/wk-xjd/v2txt>

## 2. 当前状态

已完成：

- CLI、GUI、ffmpeg 媒体探测与分块。
- faster-whisper CPU 转写。
- 15 分钟分块和断点恢复。
- JSON/SRT/Markdown 三种输出。
- CLI/Tk 实时处理位置进度。
- uv Python 3.11 和完整依赖锁。
- PyInstaller macOS ARM64/Windows x64 原生构建脚本。
- 从国内 ModelScope 下载并校验三档离线模型的脚本。
- macOS ARM64 三模型便携包及真实媒体验证。
- 48 项自动测试通过，1 项真实媒体测试默认跳过。

尚未完成：

- Windows x64 `.exe` 必须在一台 Windows x64 构建机生成，但不要求在 ThinkPad 上构建。
- Windows 构建机的打包验证，以及目标 ThinkPad 的真实视频、GUI、性能和三档模型验收尚未完成。
- 当前内部产物未做商业代码签名，Windows Defender/SmartScreen 可能提示未知发布者。

接力起点提交：

```text
77d50bf feat: add Windows hardware info collector
673b1b1 feat: bundle three offline whisper models
3a6d1eb build: verify packaged Windows executable
655c8f5 feat: package v2txt with offline GUI workflow
```

切换机器后先确认 `main` 至少包含 `77d50bf` 以及更新本接力文档的提交。

## 3. Windows x64 构建机准备

推荐至少预留 10 GB 磁盘空间。三档模型约 2.16 GB，构建目录和 ZIP 还需要数 GB。

打开 PowerShell：

```powershell
winget install Git.Git
winget install GitHub.cli
winget install astral-sh.uv
winget install Gyan.FFmpeg
```

关闭并重新打开 PowerShell，然后登录和克隆私有仓库：

```powershell
gh auth login
gh repo clone wk-xjd/v2txt
cd v2txt
git status -sb
git log --oneline -5
```

如果公司网络无法使用 `gh`，也可以从 GitHub 私有仓库网页下载源码 ZIP，但继续提交时仍推荐配置 Git。

这些开发工具只安装在构建机，不要求安装到目标 ThinkPad。

## 4. 收集目标 ThinkPad 配置

构建完成后，`collect_windows_info.bat` 会放在便携包中。把完整 ZIP 复制到目标 ThinkPad、解压，然后双击：

```text
collect_windows_info.bat
```

它会在同目录生成：

```text
v2txt-machine-info.txt
```

文件只包含 CPU、核心/线程、内存、Windows 版本、磁盘、显卡和电源计划；不采集序列号、产品密钥、用户文件或网络配置，也不检查开发工具。目标机不需要存在源码仓库。

## 5. 准备测试视频

`testvideo/` 不进入 Git。把测试视频手动复制为：

```text
testvideo\test.mp4
```

当前 macOS 验收素材属性是 H.264/AAC、280.269 秒、约 9.5 MB。Windows 构建机烟雾测试和 ThinkPad 交付验收可以使用同一文件，也可以使用不含敏感信息的短中文视频。

## 6. 在 Windows x64 构建机安装、测试和打包

在仓库根目录执行：

```powershell
uv sync --frozen
uv run pytest -q
uv run v2txt --version
uv run v2txt --help
```

预期自动测试至少为：

```text
48 passed, 1 skipped
```

一键下载三档模型、打包并使用成品转写测试视频：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1 -VideoPath .\testvideo\test.mp4
```

脚本会：

1. 使用 `uv.lock` 安装精确依赖。
2. 从 ModelScope 下载 `base`、`small`、`medium`，逐文件校验大小和 SHA-256。
3. 将 `v2txt.exe`、Python 运行时、ffmpeg、ffprobe 打入便携目录。
4. 将三档模型复制到 `models/<模型名>/`。
5. 运行成品 `--version`。
6. 使用成品内置 `small` 转写测试视频并检查三种输出。
7. 生成 Windows ZIP。

产物位置：

```text
artifacts\windows-x64\v2txt\v2txt.exe
artifacts\v2txt-windows-x64.zip
artifacts\windows-smoke-output\
```

构建机完成后，把 `artifacts\v2txt-windows-x64.zip` 复制到目标 ThinkPad。不能只复制 `v2txt.exe`，因为 `_internal/`、`models/`、ffmpeg 和 ffprobe 都是运行所需资源。

## 7. 目标 ThinkPad 交付验收

ThinkPad 不需要源码仓库，也不需要安装 Git、GitHub CLI、uv、Python 或系统 ffmpeg。把 ZIP 解压到例如 `D:\v2txt\`，所有测试都从该目录执行。

### 7.1 GUI

双击：

```text
D:\v2txt\v2txt.exe
```

确认：

- 能打开“v2txt - 视频转文字”界面。
- 能选择带中文或空格路径的视频。
- 模型下拉框包含四档，并提示 `base/small/medium` 已内置。
- 点击开始后界面不冻结，进度条持续更新。
- 完成提示给出输出目录。

### 7.2 CLI

```powershell
D:\v2txt\v2txt.exe D:\testvideo\test.mp4 --model small --output D:\v2txt-results\small --force
```

确认终端显示 Rich 进度条，并生成：

```text
transcript.json
transcript.srt
timeline.md
```

### 7.3 三档离线模型

断网或临时禁用网络后分别运行，输出目录不要复用：

```powershell
D:\v2txt\v2txt.exe D:\testvideo\test.mp4 --model base   --output D:\v2txt-results\base   --force
D:\v2txt\v2txt.exe D:\testvideo\test.mp4 --model small  --output D:\v2txt-results\small  --force
D:\v2txt\v2txt.exe D:\testvideo\test.mp4 --model medium --output D:\v2txt-results\medium --force
```

`large-v3` 没有打入主包，因为单模型约 3.09 GB，而且在低压 CPU 上非常慢。程序仍保留该选项，可联网下载或放入 `models\large-v3\`。

### 7.4 构建机仓库验收（不要在目标 ThinkPad 执行）

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_windows.ps1 -VideoPath .\testvideo\test.mp4
```

这条命令依赖源码、uv 和系统 ffmpeg，只属于 Windows 构建机。只有构建机脚本通过，并且便携包在目标 ThinkPad 上完成 GUI、CLI、三档离线模型和真实视频测试后，才能把 Windows 状态改为“交付目标机实测通过”。

## 8. 参数基线与 Windows 调优

当前推理参数：

```text
device=cpu
compute_type=int8
vad_filter=true
beam_size=5
condition_on_previous_text=false
chunk_seconds=900
```

macOS 的 `small` 单变量对比：

- `condition_on_previous_text=true`：83.62 秒，113 segments。
- `condition_on_previous_text=false`：64.47 秒，131 segments。
- 关闭后耗时降低约 22.9%，抽查未观察到新增重复，因此已采用。

Windows 首轮只建议比较 `beam_size=1/3/5` 和 CPU 线程设置，每次只改一个变量；记录总耗时、segment 数、CPU/内存峰值，并抽查开头/中段/结尾。不要仅按速度接受参数，必须同时检查漏句、重复和技术词识别。

低配 X1 Carbon 推荐顺序：

1. `small`：默认，准确率和速度平衡。
2. `base`：清晰录音快速预览。
3. `medium`：重要材料，预期更慢且占用更多内存。
4. `large-v3`：不建议在该机器作为常规档位。

## 9. 模型与包信息

ModelScope CTranslate2 权重：

- `base`：约 145 MB。
- `small`：约 484 MB。
- `medium`：约 1.53 GB。

固定文件大小和 SHA-256 位于 `scripts/download_models.py`。模型缓存在 `.local-models/`，不会进入 Git。

最后一个 macOS ARM64 三模型包：

```text
artifacts/v2txt-macos-arm64.zip
解压约 2.2 GB
ZIP 约 2.0 GB
SHA-256 0208d4a88d8e9d09f3a41d9322b783a7c41dd1ea58273070c32811b7152ff9de
```

macOS 成品已分别离线加载 `base`、`small`、`medium` 并转写五秒样本成功。该二进制不能代替 Windows 验收；PyInstaller 产物必须在目标系统原生构建。

## 10. 关键文件

- `README.md`：用户和开发者使用说明。
- `docs/superpowers/specs/2026-09-10-handover-transcriber-design.md`：技术设计。
- `docs/superpowers/plans/2026-09-10-handover-transcriber.md`：任务拆分。
- `docs/validation/testvideo-validation.md`：macOS 真实样本和打包验收记录。
- `docs/validation/windows-x64-validation.md`：Windows 验收填写模板。
- `scripts/collect_windows_info.bat`：ThinkPad 配置采集。
- `scripts/download_models.py`：国内模型下载与校验。
- `scripts/build_windows.ps1`：Windows 便携包构建和成品烟雾测试。
- `scripts/verify_windows.ps1`：Windows 仓库级验收。
- `packaging/使用说明.txt`：随便携包分发的非开发者说明。

## 11. Windows 完成后的记录与提交

把机器配置摘要、测试结果、各模型耗时、产物大小和 SHA-256 写入：

```text
docs\validation\testvideo-validation.md
```

不要提交以下内容：

```text
testvideo\
.local-models\
.local-validation\
artifacts 下的二进制和 ZIP
scripts\v2txt-machine-info.txt
转写正文或公司敏感信息
```

提交前执行：

```powershell
uv run pytest -q
git status --short
git diff --check
git add README.md WINDOWS_HANDOFF.md docs scripts src tests pyproject.toml uv.lock
git commit -m "test: validate v2txt on Windows x64"
git push origin main
```

若 Windows 发现问题，保留失败输出和准确复现命令，但不要把敏感视频、完整逐字稿或模型权重放进 GitHub。
