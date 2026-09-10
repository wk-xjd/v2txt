import json
from pathlib import Path

from handover_transcriber.models import RawSegment, Segment
from handover_transcriber.outputs import (
    format_clock,
    format_srt_time,
    normalize_segments,
    render_timeline,
    write_outputs,
)


def test_srt_timestamp_rounds_with_carry_and_supports_25_hours() -> None:
    assert format_srt_time(3599.9996) == "01:00:00,000"
    assert format_srt_time(90061.234) == "25:01:01,234"
    assert format_clock(90061.9) == "25:01:01"


def test_normalize_offsets_orders_numbers_and_filters_segments() -> None:
    parts = [
        (900.0, [RawSegment(3.0, 5.0, " 后段 ")]),
        (0.0, [RawSegment(-1.0, 2.0, " 前段 "), RawSegment(2.0, 3.0, "  ")]),
    ]

    assert normalize_segments(parts, duration=904.0) == [
        Segment(id=0, start=0.0, end=2.0, text="前段"),
        Segment(id=1, start=903.0, end=905.0, text="后段"),
    ]


def test_timeline_groups_by_sixty_seconds_and_long_silence() -> None:
    segments = [
        Segment(0, 2.0, 5.0, "第一句。"),
        Segment(1, 8.0, 12.0, "第二句。"),
        Segment(2, 30.0, 34.0, "静音后。"),
        Segment(3, 70.0, 75.0, "超过窗口。"),
    ]

    text = render_timeline("演示.mp4", 80.0, "small", "zh", segments)

    assert "## 00:00:02 - 00:00:12\n\n第一句。 第二句。" in text
    assert "## 00:00:30 - 00:00:34\n\n静音后。" in text
    assert "## 00:01:10 - 00:01:15\n\n超过窗口。" in text


def test_write_outputs_creates_consistent_utf8_files(tmp_path: Path) -> None:
    segments = [Segment(0, 12.34, 18.91, "大家先看一下这个模块。")]

    write_outputs(
        tmp_path,
        source_name="演示.mp4",
        duration=80.0,
        model="small",
        language_requested="zh",
        language_detected="zh",
        segments=segments,
    )

    payload = json.loads((tmp_path / "transcript.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["source"] == {"file_name": "演示.mp4", "duration_seconds": 80.0}
    assert payload["transcription"] == {
        "model": "small",
        "language_requested": "zh",
        "language_detected": "zh",
        "device": "cpu",
        "compute_type": "int8",
    }
    assert payload["segments"] == [
        {"id": 0, "start": 12.34, "end": 18.91, "text": "大家先看一下这个模块。"}
    ]
    assert (tmp_path / "transcript.srt").read_text(encoding="utf-8") == (
        "1\n00:00:12,340 --> 00:00:18,910\n大家先看一下这个模块。\n"
    )
    timeline = (tmp_path / "timeline.md").read_text(encoding="utf-8")
    assert "- 来源：`演示.mp4`" in timeline
    assert "## 00:00:12 - 00:00:18" in timeline
    assert not list(tmp_path.glob("*.tmp"))
