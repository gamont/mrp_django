#!/usr/bin/env python3
"""Validação estática e sem Django das dependências de migrations.

Não substitui `manage.py makemigrations --check` nem `migrate`; serve para capturar
arquivos duplicados, dependências locais inexistentes e mais de uma leaf por app.
"""
from __future__ import annotations

import ast
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPS = ROOT / "apps"
MIG_RE = re.compile(r"^\d{4}_.+\.py$")


def dependency_literals(path: Path) -> list[tuple[str, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "dependencies" for t in node.targets):
            value = node.value
            if not isinstance(value, (ast.List, ast.Tuple)):
                continue
            for item in value.elts:
                if isinstance(item, (ast.List, ast.Tuple)) and len(item.elts) >= 2:
                    a, b = item.elts[:2]
                    if isinstance(a, ast.Constant) and isinstance(a.value, str) and isinstance(b, ast.Constant) and isinstance(b.value, str):
                        out.append((a.value, b.value))
    return out


def main() -> int:
    migrations: dict[str, dict[str, Path]] = defaultdict(dict)
    duplicates: list[str] = []
    for path in APPS.glob("*/migrations/*.py"):
        if not MIG_RE.match(path.name):
            continue
        app = path.parents[1].name
        name = path.stem
        if name in migrations[app]:
            duplicates.append(f"{app}.{name}")
        migrations[app][name] = path

    errors = list(duplicates)
    reverse: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for app, items in migrations.items():
        for name, path in items.items():
            try:
                deps = dependency_literals(path)
            except SyntaxError as exc:
                errors.append(f"syntax {path}: {exc}")
                continue
            for dep_app, dep_name in deps:
                if dep_app in migrations and dep_name not in migrations[dep_app]:
                    errors.append(f"missing dependency {app}.{name} -> {dep_app}.{dep_name}")
                if dep_app in migrations and dep_name in migrations[dep_app]:
                    reverse[(dep_app, dep_name)].add((app, name))

    # Apenas folhas por app; dependências cross-app não removem a leaf local.
    leaves = []
    for app, items in migrations.items():
        local_parents = set()
        for name, path in items.items():
            for dep_app, dep_name in dependency_literals(path):
                if dep_app == app and dep_name in items:
                    local_parents.add(dep_name)
        app_leaves = sorted(set(items) - local_parents)
        if len(app_leaves) > 1:
            errors.append(f"multiple leaves in {app}: {', '.join(app_leaves)}")
        leaves.extend(f"{app}.{x}" for x in app_leaves)

    if errors:
        for err in errors:
            print(f"[FAIL] {err}", file=sys.stderr)
        print(f"MIGRATION_LINT_FAILED errors={len(errors)}", file=sys.stderr)
        return 2
    print(f"MIGRATION_LINT_OK apps={len(migrations)} migrations={sum(map(len, migrations.values()))} leaves={len(leaves)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
