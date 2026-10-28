"""Streamlit UI 구조 검사 (streamlit.testing, 브라우저 없이 스크립트 실행)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from streamlit.testing.v1 import AppTest

import core


def _app():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90)
    at.run()
    return at


def test_app_runs_with_exactly_three_tabs():
    at = _app()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["전환안 요약", "조건과 Trade-off", "PFMEA와 근거"]


def test_app_uses_core_result_values():
    at = _app()
    text = " ".join(str(m.value) for m in at.subheader) + " ".join(str(i.value) for i in at.info)
    assert "28.65%" in text and "1.231배" in text and "+1.62 pt" in text and "44.0%" in text


def test_app_scenario_switch():
    at = _app()
    at.selectbox(key="scenario").select("all_proportional").run()
    assert not at.exception
    assert "22.83%" in " ".join(str(m.value) for m in at.subheader) or "22.8" in " ".join(str(m.value) for m in at.subheader)


def test_app_has_no_formula_of_its_own():
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    for forbidden in ("** 3", "**3", "/ COP", "1.2 *", "* 0.7", "20 /"):
        assert forbidden not in src
