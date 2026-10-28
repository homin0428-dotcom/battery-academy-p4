"""외부 검토 반영 후 reporting.py 출력 회귀 테스트 (PDF 4쪽·표시 문구·manifest)."""
import copy
import json
import sys
from pathlib import Path

import pytest
from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core  # noqa: E402
import reporting  # noqa: E402

CFG = core.load_config()
G = dict(qset_kwth=200, qsource_kwth=100, cop_h=3.5, cop_c=3, heater_eff=1,
         compatible_cooling_kwth=10, total_cooling_kwth=20, aux_base_kwe=0)


def _zone(**kw):
    z = {"fan_base_kwe": 10, "heat_base_kwth": 50, "heat_new_kwth": 45, "aux_electric_kwe": 0,
         "hp_eligible_kwth": 40, "fan_affinity": False, "fan_new_kwe": 9, "supply_temp_ok": True}
    z.update(kw)
    return z


def _rows_unknown_time():
    rows = core.load_csv(core.DEFAULT_PFMEA)
    base = next(r for r in rows if r["action_id"] == "F02-A1")
    return rows + [dict(base, action_id="F02-A3", impact_value="")]


def _export(res, tmp_path):
    info = reporting.make_run_info("test")
    out = reporting.export_all(res, tmp_path, info)
    text = "\n".join(p.extract_text() for p in PdfReader(str(tmp_path / "result_report.pdf")).pages)
    return out, text, json.loads((tmp_path / "run_manifest.json").read_text(encoding="utf-8"))


def test_unmet_pdf_first_sentence_excluded_and_4_pages(tmp_path):
    res = core.run_scenario(CFG, quality_overrides={"F01": {"status": "미충족", "note": "x"}})
    assert res["conclusion"].split(".")[0].endswith("적용 제외로 판정한다")
    out, text, man = _export(res, tmp_path)
    assert out["pdf_pages"] == 4
    assert "현재 조건에서 적용" in text and "품질 미충족으로 적용 제외: 1건(F01)" in text
    assert man["derived"]["unmet_risks"] == ["F01"]


def test_lower_bound_hold_still_shows_numbers_with_markers(tmp_path):
    res = core.run_scenario(CFG, pfmea_rows=_rows_unknown_time())
    assert res["formation"]["status"] == core.NUM_HOLD and res["formation"]["occupancy_lower_bound"]
    out, text, man = _export(res, tmp_path)
    assert out["pdf_pages"] == 4
    assert "≤1.231배" in text and "≥0.25 h" in text and "0.667" in text   # 상한·하한·허용 점유 수치 표시
    assert man["derived"]["occupancy_lower_bound"] is True and man["derived"]["capacity_is_upper_bound"] is True


def test_pfmea_table_shows_link_tags(tmp_path):
    res = core.run_scenario(CFG)
    cells = " ".join(t["계산 영향"] for t in core.pfmea_table(res))
    assert "(자동 반영)" in cells and "(수동 반영 대상)" in cells
    _, text, _ = _export(res, tmp_path)
    assert "(수동 반영 대상)" in text.replace("\n", "")


def test_increase_systems_in_pdf_and_manifest(tmp_path):
    zs = [_zone(aux_electric_kwe=300), _zone(), _zone()]
    res = core.run_scenario(CFG, "custom", {"drying_r_source": "mode_b", "drying_b_zones": zs, "drying_b_global": G})
    out, text, man = _export(res, tmp_path)
    assert out["pdf_pages"] == 4
    assert man["derived"]["increase_systems"] == ["건조"]
    assert "전력 증가" in text.replace("\n", "")
