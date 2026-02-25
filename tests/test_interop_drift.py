from __future__ import annotations

import pytest

from wordmark import interop_drift


def test_analyze_reference_drift_none_when_references_unchanged() -> None:
    before = "Figure 2A shows results. Table 1 lists terms. Eq. 3 defines the model."
    after = "Figure 2A shows results. Table 1 lists terms. Eq. 3 defines the model."

    report = interop_drift.analyze_reference_drift(before, after, warning_threshold="low")
    assert report["detected"] is False
    assert report["severity"] == "none"
    assert report["signals"] == []
    assert report["warning"] is False


def test_analyze_reference_drift_detects_global_figure_shift() -> None:
    before = (
        "Figure 2A shows accumulation. Figure 3B shows composition. "
        "Table 1 is unchanged."
    )
    after = (
        "Figure 1A shows accumulation. Figure 2B shows composition. "
        "Table 1 is unchanged."
    )

    report = interop_drift.analyze_reference_drift(before, after, warning_threshold="low")
    assert report["detected"] is True
    assert "figure_ref_shift" in report["signals"]
    assert report["severity"] == "low"
    assert report["warning"] is True
    assert report["change_magnitude"] > 0


def test_analyze_reference_drift_threshold_filters_warning() -> None:
    before = "Figure 2 shows trend."
    after = "Figure 1 shows trend."

    report = interop_drift.analyze_reference_drift(before, after, warning_threshold="high")
    assert report["detected"] is True
    assert report["severity"] == "low"
    assert report["warning"] is False


def test_analyze_reference_drift_invalid_threshold_raises() -> None:
    with pytest.raises(ValueError):
        interop_drift.analyze_reference_drift("Figure 1.", "Figure 1.", warning_threshold="warn")


def test_analyze_reference_drift_reports_high_severity_for_multi_family_changes() -> None:
    before = (
        "Figure 1 supports the claim. Figure 2 supports replication. "
        "Table 1 summarises predictors. Eq. 1 defines likelihood. Appendix A provides details."
    )
    after = (
        "Figure 3 supports the claim. Figure 4 supports replication. "
        "Table 2 summarises predictors. Eq. 5 defines likelihood. Appendix C provides details."
    )

    report = interop_drift.analyze_reference_drift(before, after, warning_threshold="moderate")
    assert report["detected"] is True
    assert report["severity"] == "high"
    assert report["warning"] is True
    assert set(report["changed_families"]) == {"appendix", "equation", "figure", "table"}
