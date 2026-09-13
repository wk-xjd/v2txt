import subprocess
import sys
from pathlib import Path


def test_packaging_entrypoint_runs_cli_version() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/v2txt_entry.py", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "0.1.0"


def test_windows_package_includes_target_machine_info_collector() -> None:
    script = Path("scripts/build_windows.ps1").read_text(encoding="utf-8")

    assert "scripts\\collect_windows_info.bat" in script
    assert 'Destination (Join-Path $packageDir "collect_windows_info.bat")' in script
    assert 'Destination (Join-Path $packageDir "云端AI整理提示词.md")' in script


def test_macos_package_uses_platform_specific_instructions() -> None:
    script = Path("scripts/build_macos.sh").read_text(encoding="utf-8")

    assert 'packaging/macOS使用说明.txt' in script
    assert '"$PACKAGE_DIR/云端AI整理提示词.md"' in script
