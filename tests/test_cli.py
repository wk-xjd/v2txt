from pathlib import Path

from typer.testing import CliRunner

from handover_transcriber.cli import app, build_config


runner = CliRunner()


def test_cli_rejects_unknown_model(tmp_path: Path) -> None:
    source = tmp_path / "meeting.mp4"
    source.touch()

    result = runner.invoke(app, [str(source), "--model", "turbo"])

    assert result.exit_code == 2
    assert "base" in result.output
    assert "large-v3" in result.output


def test_cli_rejects_directory_input(tmp_path: Path) -> None:
    result = runner.invoke(app, [str(tmp_path)])

    assert result.exit_code == 2
    assert "文件" in result.output


def test_cli_accepts_arbitrary_file_extension_before_service_runs(tmp_path: Path) -> None:
    source = tmp_path / "meeting.custom"
    source.touch()

    config = build_config(source)

    assert config.input_path == source
