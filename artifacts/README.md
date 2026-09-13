# v2txt 构建产物

构建脚本会在这里生成便携目录和 ZIP，不提交大体积二进制文件。

- `macos-arm64/v2txt/`：macOS Apple Silicon 便携目录
- `v2txt-macos-arm64.zip`：macOS 分发包
- `windows-x64/v2txt/`：Windows 11 x64 便携目录（含全部三档模型）
- `v2txt-windows-x64.zip`：Windows 分发包（含 `base`、`small` 两档模型）
- `v2txt-medium-model.zip`：`medium` 模型分发包（为满足网盘单文件上限拆出）

便携目录包含程序、ffmpeg/ffprobe 和 `base`、`small`、`medium` 三档模型。
解压后无需安装 Python、uv 或下载这三档模型。
便携目录还包含 `云端AI整理提示词.md`，用于完成转写后的纠错、时间线目录、详细交接文档和原视频时间定位。

## Windows 拆分交付（网盘单文件不超过 2 GB 时）

1. `v2txt-windows-x64.zip`（约 850 MB）：解压得到 `v2txt\` 文件夹，程序可直接使用。
2. `v2txt-medium-model.zip`（约 1.4 GB）：解压得到一个 `medium` 文件夹和一份放置说明；
   把 `medium` 文件夹整个复制进 `v2txt\models\`，与 base、small 放在一起即可。

未放入 `models\medium\` 前，选择 medium 模型会回退为联网下载（公司网络受限时可能失败）；
也可以设置 `HANDOVER_MODEL_DIR` 指向其他离线模型目录。
