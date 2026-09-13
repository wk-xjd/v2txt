#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARTIFACT_ROOT="$PROJECT_ROOT/artifacts"
TARGET_ROOT="$ARTIFACT_ROOT/macos-arm64"
PACKAGE_DIR="$TARGET_ROOT/v2txt"
MODEL_ROOT="${V2TXT_MODEL_ROOT:-$PROJECT_ROOT/.local-models}"
FFMPEG_BIN="${V2TXT_FFMPEG:-$(command -v ffmpeg || true)}"
FFPROBE_BIN="${V2TXT_FFPROBE:-$(command -v ffprobe || true)}"

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "此脚本只构建 macOS ARM64 产物。" >&2
  exit 1
fi
if [[ ! -x "$FFMPEG_BIN" || ! -x "$FFPROBE_BIN" ]]; then
  echo "未找到可执行的 ffmpeg/ffprobe。可用 V2TXT_FFMPEG 和 V2TXT_FFPROBE 指定。" >&2
  exit 1
fi
cd "$PROJECT_ROOT"
uv sync --frozen
uv run python scripts/download_models.py --root "$MODEL_ROOT" --models base small medium
rm -rf "$TARGET_ROOT" "$PROJECT_ROOT/build/pyinstaller-macos"
mkdir -p "$TARGET_ROOT" "$PROJECT_ROOT/build"

uv run pyinstaller \
  --noconfirm \
  --clean \
  --onedir \
  --console \
  --name v2txt \
  --distpath "$TARGET_ROOT" \
  --workpath "$PROJECT_ROOT/build/pyinstaller-macos" \
  --specpath "$PROJECT_ROOT/build" \
  --add-binary "$FFMPEG_BIN:." \
  --add-binary "$FFPROBE_BIN:." \
  --collect-all faster_whisper \
  --collect-all ctranslate2 \
  --collect-all tokenizers \
  "$PROJECT_ROOT/scripts/v2txt_entry.py"

for model in base small medium; do
  mkdir -p "$PACKAGE_DIR/models/$model"
  cp -R "$MODEL_ROOT/$model/." "$PACKAGE_DIR/models/$model/"
done
cp "$PROJECT_ROOT/packaging/macOS使用说明.txt" "$PACKAGE_DIR/使用说明.txt"
cp "$PROJECT_ROOT/prompts/video-handover-workflow-prompt.md" "$PACKAGE_DIR/云端AI整理提示词.md"

"$PACKAGE_DIR/v2txt" --version
rm -f "$ARTIFACT_ROOT/v2txt-macos-arm64.zip"
ditto -c -k --sequesterRsrc --keepParent "$PACKAGE_DIR" "$ARTIFACT_ROOT/v2txt-macos-arm64.zip"
echo "构建完成：$ARTIFACT_ROOT/v2txt-macos-arm64.zip"
