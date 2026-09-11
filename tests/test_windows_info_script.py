from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts/collect_windows_info.bat"


def test_windows_info_script_collects_tuning_fields_without_device_identifiers() -> None:
    text = SCRIPT.read_text(encoding="utf-8").lower()

    for expected in (
        "win32_processor",
        "numberofcores",
        "numberoflogicalprocessors",
        "totalphysicalmemory",
        "win32_operatingsystem",
        "get-physicaldisk",
        "freephysicalmemory",
        "powercfg.exe /getactivescheme",
    ):
        assert expected in text

    for forbidden in ("serialnumber", "productkey", "ipaddress", "macaddress"):
        assert forbidden not in text


def test_windows_info_script_writes_result_beside_itself() -> None:
    text = SCRIPT.read_text(encoding="utf-8").lower()

    assert 'set "output=%~dp0v2txt-machine-info.txt"' in text
    assert '> "%output%" 2>&1' in text
