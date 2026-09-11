# v2txt 构建产物

构建脚本会在这里生成便携目录和 ZIP，不提交大体积二进制文件。

- `macos-arm64/v2txt/`：macOS Apple Silicon 便携目录
- `v2txt-macos-arm64.zip`：macOS 分发包
- `windows-x64/v2txt/`：Windows 11 x64 便携目录（含全部三档模型）
- `v2txt-windows-x64.zip`：Windows 分发包（含 `base`、`small` 两档模型）
- `v2txt-medium-model.zip`：`medium` 模型分发包（为满足网盘单文件上限拆出）

便携目录包含程序、ffmpeg/ffprobe 和 `base`、`small`、`medium` 三档模型。
解压后无需安装 Python、uv 或下载这三档模型。

## Windows 拆包交付（网盘单文件不超过 2 GB 时）

两个 ZIP 解压到同一个位置（例如 `D:\`），合并后得到完整的 `v2txt\` 目录：

1. `v2txt-windows-x64.zip`：程序、ffmpeg/ffprobe、`models\base`、`models\small`。
2. `v2txt-medium-model.zip`：只包含 `v2txt\models\medium\`，解压后与主包合并。

未放入 `models\medium\` 前，选择 medium 模型会回退为联网下载（公司网络受限时可能失败）；
也可以设置 `HANDOVER_MODEL_DIR` 指向其他离线模型目录。
