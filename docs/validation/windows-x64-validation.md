# Windows 11 x64 实机验收记录

状态：待在目标 ThinkPad X1 Carbon 上执行。

> 只记录硬件摘要、命令、耗时、统计和错误；不要粘贴序列号、公司视频内容或完整逐字稿。

## 环境摘要

- 验收日期：
- 电脑型号：
- CPU：
- 物理核心 / 逻辑线程：
- 内存：
- Windows 版本 / Build：
- 磁盘及可用空间：
- 活动电源计划：
- uv 版本：
- Python 版本：
- ffmpeg 版本：
- Git commit：

配置来源：运行 `scripts\collect_windows_info.bat`。原始 `v2txt-machine-info.txt` 留在本机，不提交。

## 自动测试

```powershell
uv sync --frozen
uv run pytest -q
uv run v2txt --version
uv run v2txt --help
```

- 测试结果：待填写
- CLI 版本/帮助：待填写

## Windows 便携包

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1 -VideoPath .\testvideo\test.mp4
```

- 构建结果：待填写
- `v2txt.exe --version`：待填写
- ZIP 大小：待填写
- ZIP SHA-256：待填写
- SmartScreen/Defender 情况：待填写

获取 SHA-256：

```powershell
Get-FileHash .\artifacts\v2txt-windows-x64.zip -Algorithm SHA256
```

## GUI 验收

- [ ] 双击 `v2txt.exe` 能打开 GUI。
- [ ] 中文/空格输入路径可选择。
- [ ] 模型列表正确，三档内置提示正确。
- [ ] 转写期间界面不冻结且进度更新。
- [ ] 完成后生成 JSON、SRT、Markdown。
- [ ] 失败时显示可操作错误，不显示 Python traceback。

## 三档离线模型

| 模型 | 完全断网加载 | 总耗时 | Segment 数 | 峰值内存 | 抽查结果 |
|---|---:|---:|---:|---:|---|
| `base` | 待测 |  |  |  |  |
| `small` | 待测 |  |  |  |  |
| `medium` | 待测 |  |  |  |  |

测试输入：只记录容器、编解码器、时长和文件大小，不记录敏感内容。

## 参数对比

固定其他变量，每次只改变一个参数：

| 模型 | beam size | CPU threads | 总耗时 | Segment 数 | 问题/收益 |
|---|---:|---:|---:|---:|---|
| `small` | 5 | 自动 |  |  | 基线 |
| `small` | 3 | 自动 |  |  |  |
| `small` | 1 | 自动 |  |  |  |

## 结论

- Windows x64 交付状态：待验证
- 默认模型是否保持 `small`：待填写
- 最终参数：待填写
- 遗留问题：待填写
