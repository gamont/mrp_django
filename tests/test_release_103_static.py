from pathlib import Path
import ast
import re

ROOT = Path(__file__).resolve().parents[1]
PATCH_RE = re.compile(r"^1\.0\.\d+$")


def test_release_metadata_stays_patch_agnostic():
    version = (ROOT / "VERSION").read_text().strip()
    settings_text = (ROOT / "config/settings.py").read_text()
    assert version.startswith("1.0.")
    assert f'MRP_VERSION = "{version}"' in settings_text


def test_release_assertions_do_not_pin_stable_patch_versions():
    offenders = []
    for path in sorted((ROOT / "tests").glob("test_release_*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assert):
                continue
            for child in ast.walk(node.test):
                if isinstance(child, ast.Constant) and isinstance(child.value, str):
                    if PATCH_RE.fullmatch(child.value):
                        offenders.append((path.name, child.value))
    assert not offenders


def test_consistency_gate_uses_ast_based_patch_pin_detection():
    text = (ROOT / "scripts/release_consistency.py").read_text()
    assert "STABLE_PATCH_RE" in text
    assert "ast.Assert" in text
    assert "patch_pins=0" in text
