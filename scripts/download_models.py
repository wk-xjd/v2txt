from __future__ import annotations

import argparse
import hashlib
import sys
import time
import urllib.request
from pathlib import Path


MODEL_FILES = {
    "base": {
        "config.json": (2309, "56a6d8110d311f19c8f0471e562832c7527f146b567275bfca59fcf7c184da9a"),
        "model.bin": (145217532, "d01c3014881c9c6f3133c182f3d2887eb6ca1c789a7538c5c007196857a0a6a9"),
        "tokenizer.json": (2203239, "fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab"),
        "vocabulary.txt": (459861, "34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913"),
    },
    "small": {
        "config.json": (2370, "b55496ac7940a7ae47d2c01eab40edfd8701feec1229d9cce3b40014383fb828"),
        "model.bin": (483546902, "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671"),
        "tokenizer.json": (2203239, "fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab"),
        "vocabulary.txt": (459861, "34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913"),
    },
    "medium": {
        "config.json": (2257, "3622a2ddc41ec0e0fd4e68c13c6830f03b90c38d89aaad184de02c8c642cf807"),
        "model.bin": (1527906378, "9b45e1009dcc4ab601eff815b61d80e60ce3fd8c74c1a14f4a282258286b51ae"),
        "tokenizer.json": (2203239, "fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab"),
        "vocabulary.txt": (459861, "34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913"),
    },
}


def valid_file(path: Path, size: int, sha256: str) -> bool:
    if not path.is_file() or path.stat().st_size != size:
        return False
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == sha256


def download_file(model: str, name: str, target: Path, size: int, sha256: str) -> None:
    if valid_file(target, size, sha256):
        print(f"[{model}] {name} 已存在且校验通过")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    url = f"https://www.modelscope.cn/models/Systran/faster-whisper-{model}/resolve/master/{name}"
    print(f"[{model}] 下载 {name}（{size / 1024 / 1024:.1f} MB）")
    digest = hashlib.sha256()
    downloaded = 0
    last_report = 0.0
    try:
        with urllib.request.urlopen(url, timeout=60) as response, temporary.open("wb") as output:
            while chunk := response.read(4 * 1024 * 1024):
                output.write(chunk)
                digest.update(chunk)
                downloaded += len(chunk)
                now = time.monotonic()
                if now - last_report >= 1.0:
                    print(f"  {downloaded / size * 100:5.1f}%", end="\r", flush=True)
                    last_report = now
        print("  100.0%")
        if downloaded != size or digest.hexdigest() != sha256:
            raise RuntimeError(f"{model}/{name} 校验失败")
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="从 ModelScope 下载 v2txt 离线模型")
    parser.add_argument("--root", type=Path, default=Path(".local-models"))
    parser.add_argument("--models", nargs="+", choices=MODEL_FILES, default=list(MODEL_FILES))
    args = parser.parse_args()
    for model in args.models:
        for name, (size, sha256) in MODEL_FILES[model].items():
            download_file(model, name, args.root / model / name, size, sha256)
    print(f"模型已准备：{args.root.resolve()}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"模型下载失败：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc
