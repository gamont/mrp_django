from pathlib import Path


TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "apps"
    / "integrated_scheduling"
    / "templates"
    / "integrated_scheduling"
    / "operational_mps_detail.html"
)


def test_operational_mps_detail_does_not_nest_bucket_iteration():
    source = TEMPLATE.read_text()

    assert "for t in buckets" not in source
    assert 'bucket_targets|json_script:"mps-bucket-targets"' in source
    assert 'class="mps-target-bucket"' in source


def test_operational_mps_targets_are_loaded_on_demand():
    source = TEMPLATE.read_text()

    assert "function populateTargets(select)" in source
    assert "select.dataset.loaded === 'true'" in source
    assert "addEventListener('focus'" in source
