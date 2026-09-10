# v2txt 构建产物

构建脚本会在这里生成便携目录和 ZIP，不提交大体积二进制文件。

- `macos-arm64/v2txt/`：macOS Apple Silicon 便携目录
- `v2txt-macos-arm64.zip`：macOS 分发包
- `windows-x64/v2txt/`：Windows 11 x64 便携目录
- `v2txt-windows-x64.zip`：Windows 分发包

便携目录包含程序、ffmpeg/ffprobe 和默认 `small` 模型。解压后无需安装
Python、uv 或另行下载默认模型。
