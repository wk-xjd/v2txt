param(
    [Parameter(Mandatory = $true)]
    [string]$VideoPath
)

$ErrorActionPreference = "Stop"

if ($env:PROCESSOR_ARCHITECTURE -ne "AMD64") {
    throw "第一版只支持 Windows x64，当前架构为 $env:PROCESSOR_ARCHITECTURE"
}

foreach ($command in @("uv", "ffmpeg", "ffprobe")) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "缺少 $command。uv: winget install astral-sh.uv；ffmpeg: winget install Gyan.FFmpeg"
    }
}

if (-not (Test-Path -LiteralPath $VideoPath -PathType Leaf)) {
    throw "视频文件不存在：$VideoPath"
}

uv sync --frozen
if ($LASTEXITCODE -ne 0) { throw "uv sync 失败" }

uv run pytest -q
if ($LASTEXITCODE -ne 0) { throw "自动测试失败" }

uv run v2txt --help
if ($LASTEXITCODE -ne 0) { throw "CLI 帮助命令失败" }

$outputPath = Join-Path $PSScriptRoot "..\.local-validation\windows-base"
uv run v2txt $VideoPath --model base --output $outputPath --force
if ($LASTEXITCODE -ne 0) { throw "真实视频转写失败" }

$jsonPath = Join-Path $outputPath "transcript.json"
if (-not (Test-Path -LiteralPath $jsonPath -PathType Leaf)) {
    throw "未生成 transcript.json"
}

Write-Host "Windows x64 验证通过。输出：$outputPath" -ForegroundColor Green
