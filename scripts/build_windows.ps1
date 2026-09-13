param(
    [string]$ModelRoot = "$PSScriptRoot\..\.local-models",
    [string]$FfmpegPath = "",
    [string]$FfprobePath = "",
    [string]$VideoPath = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$artifactRoot = Join-Path $projectRoot "artifacts"
$targetRoot = Join-Path $artifactRoot "windows-x64"
$packageDir = Join-Path $targetRoot "v2txt"

if ($env:PROCESSOR_ARCHITECTURE -ne "AMD64") {
    throw "此脚本只构建 Windows x64 产物，当前架构为 $env:PROCESSOR_ARCHITECTURE"
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "缺少 uv。请运行：winget install astral-sh.uv"
}
if (-not $FfmpegPath) { $FfmpegPath = (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source }
if (-not $FfprobePath) { $FfprobePath = (Get-Command ffprobe -ErrorAction SilentlyContinue).Source }
if (-not (Test-Path -LiteralPath $FfmpegPath -PathType Leaf)) { throw "未找到 ffmpeg.exe" }
if (-not (Test-Path -LiteralPath $FfprobePath -PathType Leaf)) { throw "未找到 ffprobe.exe" }
Set-Location $projectRoot
uv sync --frozen
if ($LASTEXITCODE -ne 0) { throw "uv sync 失败" }
uv run python scripts\download_models.py --root $ModelRoot --models base small medium
if ($LASTEXITCODE -ne 0) { throw "离线模型准备失败" }

Remove-Item -LiteralPath $targetRoot -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $projectRoot "build\pyinstaller-windows") -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $targetRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $projectRoot "build") | Out-Null

$pyiArgs = @(
    "--noconfirm", "--clean", "--onedir", "--console",
    "--name", "v2txt",
    "--distpath", $targetRoot,
    "--workpath", (Join-Path $projectRoot "build\pyinstaller-windows"),
    "--specpath", (Join-Path $projectRoot "build"),
    "--add-binary", "$FfmpegPath;.",
    "--add-binary", "$FfprobePath;.",
    "--collect-all", "faster_whisper",
    "--collect-all", "ctranslate2",
    "--collect-all", "tokenizers",
    "--collect-all", "opencc",
    (Join-Path $projectRoot "scripts\v2txt_entry.py")
)
uv run pyinstaller @pyiArgs
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 构建失败" }

foreach ($model in @("base", "small", "medium")) {
    $destination = Join-Path $packageDir "models\$model"
    New-Item -ItemType Directory -Force -Path $destination | Out-Null
    Copy-Item -Path (Join-Path $ModelRoot "$model\*") -Destination $destination -Recurse -Force
}
Copy-Item -LiteralPath (Join-Path $projectRoot "packaging\使用说明.txt") -Destination (Join-Path $packageDir "使用说明.txt")
Copy-Item -LiteralPath (Join-Path $projectRoot "scripts\collect_windows_info.bat") -Destination (Join-Path $packageDir "collect_windows_info.bat")
Copy-Item -LiteralPath (Join-Path $projectRoot "prompts\video-handover-workflow-prompt.md") -Destination (Join-Path $packageDir "云端AI整理提示词.md")

& (Join-Path $packageDir "v2txt.exe") --version
if ($LASTEXITCODE -ne 0) { throw "打包后的 v2txt.exe 无法启动" }

if ($VideoPath) {
    if (-not (Test-Path -LiteralPath $VideoPath -PathType Leaf)) {
        throw "验收视频不存在：$VideoPath"
    }
    $smokeOutput = Join-Path $artifactRoot "windows-package-smoke"
    & (Join-Path $packageDir "v2txt.exe") $VideoPath --model small --output $smokeOutput --force
    if ($LASTEXITCODE -ne 0) { throw "打包后的程序真实视频转写失败" }
    foreach ($name in @("transcript.json", "transcript.srt", "timeline.md")) {
        if (-not (Test-Path -LiteralPath (Join-Path $smokeOutput $name) -PathType Leaf)) {
            throw "打包验收缺少输出：$name"
        }
    }
}

$zipPath = Join-Path $artifactRoot "v2txt-windows-x64.zip"
Remove-Item -LiteralPath $zipPath -Force -ErrorAction SilentlyContinue
Compress-Archive -Path $packageDir -DestinationPath $zipPath -CompressionLevel Optimal
Write-Host "构建完成：$zipPath" -ForegroundColor Green
