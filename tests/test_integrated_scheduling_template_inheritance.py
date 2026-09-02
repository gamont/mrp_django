from pathlib import Path


TEMPLATE_ROOT = Path(
    "apps/integrated_scheduling/templates/integrated_scheduling"
)


def test_integrated_scheduling_templates_do_not_extend_missing_root_base():
    offenders = []

    for template in TEMPLATE_ROOT.rglob("*.html"):
        content = template.read_text(encoding="utf-8")

        if '{% extends "base.html" %}' in content:
            offenders.append(str(template))

    assert not offenders, (
        "Integrated Scheduling templates must extend "
        '"ui/base.html", not the missing root "base.html":\n'
        + "\n".join(offenders)
    )
