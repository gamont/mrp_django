#!/usr/bin/env python3
"""Checks stable-line release metadata/assets without importing Django.

1.0.4 hardening: release tests must never pin a patch number such as 1.0.2.
That kind of assertion makes the next maintenance release fail before the
application is even exercised.  The rule is detected through the Python AST
rather than a brittle list of previous patch versions.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(r'^\d+\.\d+\.\d+$')
STABLE_PATCH_RE = re.compile(r'^1\.0\.\d+$')
SETTINGS_RE = re.compile(r'^MRP_VERSION\s*=\s*["\']([^"\']+)["\']', re.M)


def fail(message: str) -> None:
    print(f"[FAIL] {message}", file=sys.stderr)


def _stable_patch_literals_in_asserts(path: Path) -> list[tuple[int, str]]:
    """Return exact 1.0.x literals used inside assert expressions.

    Exact patch literals in release assertions are forbidden.  Tests should
    compare VERSION with settings.MRP_VERSION and, when needed, assert only the
    stable line (``version.startswith("1.0.")``).
    """
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        for child in ast.walk(node.test):
            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                if STABLE_PATCH_RE.fullmatch(child.value):
                    found.append((getattr(child, 'lineno', node.lineno), child.value))
    return found


def main() -> int:
    errors: list[str] = []
    version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
    if not VERSION_RE.match(version):
        errors.append(f"VERSION inválida: {version!r}")

    settings_text = (ROOT / 'config/settings.py').read_text(encoding='utf-8')
    match = SETTINGS_RE.search(settings_text)
    if not match:
        errors.append('MRP_VERSION ausente em config/settings.py')
    elif match.group(1) != version:
        errors.append(f"VERSION={version} != settings.MRP_VERSION={match.group(1)}")

    release_tests = sorted((ROOT / 'tests').glob('test_release_*.py'))
    for test in release_tests:
        try:
            stale = _stable_patch_literals_in_asserts(test)
        except SyntaxError as exc:
            errors.append(f"syntax {test.relative_to(ROOT)}: {exc}")
            continue
        for lineno, literal in stale:
            errors.append(
                f"stable patch literal in assert at {test.relative_to(ROOT)}:{lineno}: {literal}; "
                "use VERSION/settings equality plus startswith('1.0.')"
            )

    required = [
        'scripts/preflight.sh',
        'scripts/release_validate.sh',
        'scripts/migration_lint.py',
        'scripts/release_consistency.py',
        'scripts/compose_lint.py',
        'scripts/backup.sh',
        'scripts/restore.sh',
        'docs/INSTALLATION_1_0.md',
        'docs/BACKUP_RESTORE_1_0.md',
        'docs/PRODUCTION_RUNBOOK_1_0.md',
        'docs/ACCEPTANCE_1_0.md',
    ]
    for rel in required:
        if not (ROOT / rel).exists():
            errors.append(f"asset obrigatório ausente: {rel}")

    try:
        ast.parse(settings_text, filename='config/settings.py')
    except SyntaxError as exc:
        errors.append(f"syntax config/settings.py: {exc}")

    if errors:
        for error in errors:
            fail(error)
        print(f"RELEASE_CONSISTENCY_FAILED errors={len(errors)}", file=sys.stderr)
        return 2
    print(
        f"RELEASE_CONSISTENCY_OK version={version} stable_line=1.0.x "
        f"release_tests={len(release_tests)} patch_pins=0"
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
