from pathlib import Path


TEMPLATE = Path(
    "apps/maintenance/templates/maintenance/advanced_planner.html"
)


def test_advanced_planner_does_not_scan_all_orders_for_each_day():
    content = TEMPLATE.read_text(encoding="utf-8")

    assert "{% for day in calendar_days %}" in content
    assert "{% for wo in day.orders %}" in content

    assert "{% for day in days %}" not in content
    assert "{% for wo in orders %}" not in content
