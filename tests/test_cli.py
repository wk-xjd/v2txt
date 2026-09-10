from pathlib import Path

from typer.testing import CliRunner

import handover_transcriber.cli as cli_module
from handover_transcriber.cli import app, build_config
from handover_transcriber.errors import MediaError
from handover_transcriber.models import ProgressEvent


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


def test_cli_runs_service_and_prints_output_path(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "meeting.custom"
    source.touch()

    class Service:
        def run(self, config, on_progress=None):
            config.output_dir.mkdir()
            on_progress(ProgressEvent("complete", 1.0, 1.0, "转写完成"))
            return config.output_dir

    monkeypatch.setattr(cli_module, "build_service", lambda: Service())

    result = runner.invoke(app, [str(source)])

    assert result.exit_code == 0
    assert "转写完成" in result.output
    assert str(tmp_path / "meeting_transcript") in result.output


def test_cli_maps_domain_error_to_its_exit_code(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "meeting.mp4"
    source.touch()

    class Service:
        def run(self, config, on_progress=None):
            raise MediaError("未找到 ffprobe")

    monkeypatch.setattr(cli_module, "build_service", lambda: Service())

    result = runner.invoke(app, [str(source)])

    assert result.exit_code == 3
    assert "未找到 ffprobe" in result.output
    assert "Traceback" not in result.output


def test_cli_handles_keyboard_interrupt_without_traceback(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "meeting.mp4"
    source.touch()

    class Service:
        def run(self, config, on_progress=None):
            raise KeyboardInterrupt

    monkeypatch.setattr(cli_module, "build_service", lambda: Service())

    result = runner.invoke(app, [str(source)])

    assert result.exit_code == 130
    assert "可以使用相同命令继续" in result.output
    assert "Traceback" not in result.output
