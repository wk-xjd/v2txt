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
