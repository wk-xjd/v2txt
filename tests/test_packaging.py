import subprocess
import sys


def test_packaging_entrypoint_runs_cli_version() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/v2txt_entry.py", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "0.1.0"
