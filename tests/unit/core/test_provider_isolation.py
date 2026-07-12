from pathlib import Path

CORE_ROOT = Path(__file__).resolve().parents[4] / "src" / "rp_engine" / "core"


def test_core_layer_does_not_import_lmstudio() -> None:
    for file_path in CORE_ROOT.rglob("*.py"):
        content = file_path.read_text(encoding="utf-8")
        assert "import lmstudio" not in content
        assert "from lmstudio" not in content
