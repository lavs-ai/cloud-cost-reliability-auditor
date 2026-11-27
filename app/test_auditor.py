"""Tests for the cloud cost + reliability auditor.

Run with:  python -m pytest app/test_auditor.py
or plain:  python app/test_auditor.py
No AWS credentials or network access needed — all tests use demo data.
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auditor import (  # noqa: E402
    count_by_severity,
    findings_from_sample,
    load_demo_data,
    render_markdown,
    run,
    sort_findings,
)


def test_severity_ranking_critical_first():
    findings = [
        {"severity": "low", "title": "low"},
        {"severity": "critical", "title": "critical"},
        {"severity": "high", "title": "high"},
        {"severity": "medium", "title": "medium"},
    ]
    ranked = sort_findings(findings)
    assert [f["severity"] for f in ranked] == [
        "critical", "high", "medium", "low",
    ]


def test_severity_ranking_unknown_sorts_last():
    findings = [
        {"severity": "weird", "title": "unknown"},
        {"severity": "critical", "title": "critical"},
    ]
    assert sort_findings(findings)[0]["severity"] == "critical"


def test_count_by_severity():
    findings = [
        {"severity": "critical"}, {"severity": "high"},
        {"severity": "high"}, {"severity": "low"},
    ]
    assert count_by_severity(findings) == {
        "critical": 1, "high": 2, "low": 1,
    }


def test_demo_data_loads_and_is_labelled_sample():
    data = load_demo_data()
    assert "SAMPLE" in data["label"]
    findings = findings_from_sample(data)
    assert len(findings) == 7
    assert {f["severity"] for f in findings} == {
        "critical", "high", "medium", "low",
    }
    # Every finding has what the report needs.
    for f in findings:
        for key in ("id", "severity", "category", "title", "detail",
                    "recommendation"):
            assert f[key], f"finding {f.get('id')} is missing {key}"


def test_demo_report_generation():
    with tempfile.TemporaryDirectory() as tmp:
        rc = run(demo=True, region="ap-southeast-2", output_dir=tmp)
        assert rc == 0
        md = (Path(tmp) / "report.md").read_text(encoding="utf-8")
        report = json.loads((Path(tmp) / "report.json").read_text())
        assert "Cloud Cost + Reliability Audit" in md
        assert "SAMPLE DATA ONLY" in md
        assert "No restore test on record" in md
        assert "No budget alarm found" in md
        assert report["counts_by_severity"]["critical"] == 2
        assert report["counts_by_severity"]["high"] == 3
        assert len(report["findings"]) == 7
        # Most severe finding is first in the JSON report.
        assert report["findings"][0]["severity"] == "critical"


def test_render_markdown_with_no_findings():
    md = render_markdown([], {"account": "x", "region": "ap-southeast-2",
                              "date": "2026-11-27", "mode": "demo"})
    assert "No findings" in md
    assert "does not mean the account is fully safe" in md


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {t.__name__}: {exc}")
    print(f"{len(tests) - failed}/{len(tests)} tests passed")
    sys.exit(1 if failed else 0)
