from pathlib import Path

from typer.testing import CliRunner

import handover_transcriber.cli as cli_module
from handover_transcriber.cli import app, build_configs
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

    configs = build_configs([source])

    assert configs[0].input_path == source


def test_cli_single_output_directory_is_used_as_is(tmp_path: Path) -> None:
    source = tmp_path / "a.mp4"
    source.touch()

    configs = build_configs([source], output=tmp_path / "out")

    assert configs[0].output_dir == tmp_path / "out"


def test_cli_batch_output_directory_becomes_parent(tmp_path: Path) -> None:
    first = tmp_path / "a.mp4"
    second = tmp_path / "b.mp4"
    first.touch()
    second.touch()

    configs = build_configs([first, second], output=tmp_path / "out")

    assert [config.output_dir for config in configs] == [
        tmp_path / "out" / "a_transcript",
        tmp_path / "out" / "b_transcript",
    ]


def test_cli_batch_defaults_output_next_to_each_input(tmp_path: Path) -> None:
    first = tmp_path / "a.mp4"
    second = tmp_path / "b.mp4"
    first.touch()
    second.touch()

    configs = build_configs([first, second])

    assert [config.output_dir for config in configs] == [
        tmp_path / "a_transcript",
        tmp_path / "b_transcript",
    ]


def test_cli_batch_continues_after_failure_and_summarizes(tmp_path: Path, monkeypatch) -> None:
    bad = tmp_path / "bad.mp4"
    good = tmp_path / "good.mp4"
    bad.touch()
    good.touch()

    class Service:
        def run(self, config, on_progress=None):
            if config.input_path.name == "bad.mp4":
                raise MediaError("媒体中没有可用的音频流")
            config.output_dir.mkdir()
            on_progress(ProgressEvent("complete", 1.0, 1.0, "转写完成"))
            return config.output_dir

    monkeypatch.setattr(cli_module, "build_service", lambda: Service())

    result = runner.invoke(app, [str(bad), str(good)])

    assert result.exit_code == 3
    assert "bad.mp4" in result.output
    assert "媒体中没有可用的音频流" in result.output
    assert "批量完成：1/2 个文件" in result.output
    assert str(tmp_path / "good_transcript") in result.output


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
