import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts/download_models.py"
SPEC = importlib.util.spec_from_file_location("download_models", SCRIPT)
assert SPEC and SPEC.loader
download_models = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(download_models)


def test_offline_bundle_defines_three_models_and_required_files() -> None:
    assert set(download_models.MODEL_FILES) == {"base", "small", "medium"}
    for files in download_models.MODEL_FILES.values():
        assert set(files) == {"config.json", "model.bin", "tokenizer.json", "vocabulary.txt"}


def test_valid_file_checks_size_and_hash(tmp_path: Path) -> None:
    target = tmp_path / "model.bin"
    target.write_bytes(b"model")

    assert download_models.valid_file(
        target,
        5,
        "9372c470eeadd5ecd9c3c74c2b3cb633f8e2f2fad799250a0f70d652b6b825e4",
    )
    assert not download_models.valid_file(target, 6, "ignored")
