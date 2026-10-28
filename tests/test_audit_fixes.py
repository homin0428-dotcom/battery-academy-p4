"""감사 후속 수정 회귀 테스트 (모드 B 경계·단위·열원 경고, 중복 가드, 에이징 구역, R2, 폰트 라이선스).

기존 test_core.py 의 기대값은 바꾸지 않았다. 여기 테스트는 모두 추가분이다.
"""
import copy
import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import core  # noqa: E402
import reporting  # noqa: E402
from test_core import gl, zones  # noqa: E402  (모드 B 시험용 가상 입력 생성기)

approx = pytest.approx


@pytest.fixture(scope="module")
def cfg():
    return core.load_config()


def pdf_text(path):
    from pypdf import PdfReader
    return "\n".join(p.extract_text() for p in PdfReader(str(path)).pages)


# ---------------------------------------------------------------- 1. 모드 B: 기존 보조부하 경계 대칭
def test_mode_b_aux_base_in_both_base_and_new():
    r0 = core.drying_mode_b(zones(), gl())
    r5 = core.drying_mode_b(zones(), gl(aux_base_kwe=5.0))
    assert r5["E_new"] - r0["E_new"] == approx(5.0)          # 기존 보조부하는 변경 후에도 남는다
    assert r5["E_base"] - r0["E_base"] == approx(5.0)
    assert r5["saving_ratio"] == approx(1 - r5["E_new"] / r5["E_base"])
    assert r5["saving_ratio"] < r0["saving_ratio"]           # 같은 값을 양쪽에 더하면 절감률이 부풀지 않는다
    assert r0["aux_base"] == 0.0 and r5["aux_base"] == 5.0
    # 구간별 보조부하(변경안에서 추가되는 부하)는 E_new 에만 들어간다
    z2 = core.drying_mode_b(zones(aux_electric_kwe=2.0), gl())
    assert z2["E_new"] - r0["E_new"] == approx(3.0) and z2["E_base"] == approx(r0["E_base"])


# ---------------------------------------------------------------- 2. 모드 B: 단위 검사
def test_mode_b_unit_mismatch_raises(cfg):
    _, meta = core.resolve_inputs(cfg, "custom")
    core.check_units(meta)                                     # 기본 단위는 통과
    for key in ("drying_b_global", "drying_b_zones"):
        bad = copy.deepcopy(meta)
        bad[key]["unit"] = "MW"
        with pytest.raises(core.InputError, match="단위 불일치"):
            core.check_units(bad)
    with pytest.raises(core.InputError, match="단위 불일치"):
        core.drying_mode_b(zones(), gl(), unit="MW")
    assert core.drying_mode_b(zones(), gl(), unit="kWth/kWe")["status"] == core.NUM_OK
    res = core.run_scenario(cfg, "custom", {"drying_b_global": {"value": gl(), "unit": "MW"}})
    assert "단위 불일치" in res["blocked"] and "plant" not in res
    res = core.run_scenario(cfg, "custom", {"drying_b_zones": {"value": zones(), "unit": "kW"}})
    assert res.get("blocked")


# ---------------------------------------------------------------- 3. 모드 B: 열원 한계 경고·제한 요인
def test_mode_b_source_limit_warning_and_limit_factor():
    ok = core.drying_mode_b(zones(), gl())
    assert ok["source_limited"] is False and ok["warnings"] == [] and ok["unmet_hp_kwth"] == 0.0
    r = core.drying_mode_b(zones(), gl(qsource_kwth=60.0))      # 한계 90 < 요구 180
    assert r["source_limited"] is True and r["limit_by"] == "열원"
    assert r["source_limit_kwth"] == approx(90.0) and r["Qh"] == approx(90.0)   # 상한 처리는 유지
    assert r["unmet_hp_kwth"] == approx(90.0)
    assert any("Qdemand" in w and "열원 한계 90.00 kWth" in w for w in r["warnings"])
    both = core.drying_mode_b(zones(), gl(qsource_kwth=60.0, qset_kwth=400.0))
    assert any("Qset" in w for w in both["warnings"]) and any("Qdemand" in w for w in both["warnings"])
    # 수요는 한계 이내지만 Qset 만 한계를 넘는 경우도 경고한다
    only_set = core.drying_mode_b(zones(hp_eligible_kwth=10.0), gl(qsource_kwth=60.0, qset_kwth=100.0))
    assert only_set["Qh"] == approx(30.0) and only_set["limit_by"] == "수요"
    assert [w for w in only_set["warnings"] if w.startswith("Qset")] and \
        not [w for w in only_set["warnings"] if w.startswith("Qdemand")]


def test_mode_b_source_limit_reaches_run_csv_pdf_manifest(cfg, tmp_path):
    res = core.run_scenario(cfg, "custom", {"drying_r_source": "mode_b", "drying_b_zones": zones(),
                                            "drying_b_global": gl(qsource_kwth=60.0)})
    assert res["drying_b"]["source_limited"] and any(w.startswith("건조 모드 B:") for w in res["warnings"])
    out = tmp_path / "o"
    assert reporting.export_all(res, out, reporting.make_run_info("cli"))["pdf_pages"] == 4
    with open(out / "requirements.csv", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    lim = [r for r in rows if r["item"] == "Qh 제한 요인"][0]
    assert lim["kind"] == "건조 모드 B 경계" and lim["interpretation"] == "열원"
    assert [r for r in rows if r["kind"] == "건조 모드 B 경고"]
    src = [r for r in rows if r["item"].startswith("열원 한계")][0]
    assert float(src["value"]) == approx(90.0) and src["unit"] == "kWth"
    assert "90.00 kWth" in pdf_text(out / "result_report.pdf")
    man = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
    assert any("건조 모드 B" in w for w in man["warnings"])


# ---------------------------------------------------------------- 4. 구간 절감 전체 중복 적용 가드(실행 경로 연결)
def test_zone_savings_guard_wired_in_run(cfg):
    r = core.run_scenario(cfg, "custom", {"drying_r_source": "mode_a", "drying_a_airflow_scope": "zone"})
    assert r["plant"]["status"] == core.NUM_ERR and "중복 적용" in r["plant"]["error"]
    assert any("중복 적용" in w for w in r["warnings"])
    assert r["reverse"] == [] and r["r_effective"][0] is None
    ok = core.run_scenario(cfg, "custom", {"drying_r_source": "mode_a", "drying_a_airflow_scope": "system"})
    assert ok["plant"]["status"] in (core.NUM_OK, core.NUM_FAIL)
    # zone 범위 값이어도 모드 A를 공장 모델에 쓰지 않으면(수동 출처) 중복 적용이 아니다
    man = core.run_scenario(cfg, "custom", {"drying_r_source": "manual", "drying_a_airflow_scope": "zone"})
    assert man["plant"]["E_total"] == approx(85.62)
    assert core.run_scenario(cfg, "custom", {"drying_a_airflow_scope": "all"})["plant"]["status"] == core.NUM_ERR
    assert core.run_scenario(cfg, "representative")["plant"]["E_total"] == approx(85.62)   # 기본값 불변


# ---------------------------------------------------------------- 5. 에이징 구역별 계산
AZ_A = {"name": "고온 구역", "old_throughput_per_day": 100, "old_wait_days": 14, "new_throughput_per_day": 120,
        "new_wait_days": 10, "area_per_cell": 0.5, "slots_per_area": 2.0, "conversion_fraction": 0.5}
AZ_B = {"name": "상온 구역", "current_utilization": 0.85, "old_throughput_per_day": 50, "old_wait_days": 14,
        "new_throughput_per_day": 100, "new_wait_days": 14, "area_per_cell": 0.5, "slots_per_area": 2.0,
        "conversion_fraction": 0.5}


def test_aging_single_zone_unchanged_without_zone_data(cfg):
    base = core.aging_slots(1.2, 0.9, 0.95, 100, 14, 120, 10, 0.5, 2.0, 0.5)
    assert core.aging_slots(1.2, 0.9, 0.95, 100, 14, 120, 10, 0.5, 2.0, 0.5, zones=None) == base
    assert core.aging_slots(1.2, 0.9, 0.95, 100, 14, 120, 10, 0.5, 2.0, 0.5, zones=[]) == base
    assert base["zone_mode"] is False and base["zones"] == []
    assert base["convertible_slots"] == approx(100.0) and base["space_status"] == "조건부"
    rep = core.run_scenario(cfg, "representative")
    assert rep["aging"]["zone_mode"] is False
    assert rep["aging"]["additional_slot_ratio"] == approx(0.1368421053, abs=1e-9)


def test_aging_zones_computed_per_zone_without_netting():
    r = core.aging_slots(1.2, 0.9, 0.95, zones=[AZ_A, AZ_B])
    a, b = r["zones"]
    assert r["zone_mode"] and [z["name"] for z in r["zones"]] == ["고온 구역", "상온 구역"]
    assert a["additional_slot_ratio"] == approx(0.1368421053, abs=1e-9)         # 전체 사용률 사용
    assert b["additional_slot_ratio"] == approx(1.2 * 0.85 / 0.95 - 1, abs=1e-9)  # 구역 사용률 사용
    assert a["freed_wip"] == approx(200) and a["freed_area_m2"] == approx(100)
    assert a["convertible_slots"] == approx(100.0) and a["space_status"] == "조건부"
    assert b["freed_area_m2"] == approx(-350) and b["space_status"] == "추가 공간 필요"   # 0으로 바꾸지 않음
    assert b["convertible_slots"] == 0
    assert r["convertible_slots"] == approx(100.0)          # 부족 구역이 다른 구역의 전환 슬롯을 깎거나 메우지 않음
    assert r["freed_area_m2"] == approx(-250)               # 합계는 단순 합이며 부족은 상태로 표시
    assert r["space_status"] == "일부 구역 추가 공간 필요" and r["aging_days"] == 14
    assert r["additional_slot_ratio"] == approx(0.1368421053, abs=1e-9)         # 전체 슬롯비는 기존 식 그대로


def test_aging_zones_missing_input_holds_only_totals():
    r = core.aging_slots(1.2, 0.9, 0.95, zones=[AZ_A, {"name": "미확인 구역"}])
    assert r["zones"][0]["convertible_slots"] == approx(100.0) and r["zones"][0]["space_status"] == "조건부"
    assert r["zones"][1]["space_status"] == "계산 보류" and r["zones"][1]["convertible_slots"] is None
    assert r["convertible_slots"] is None and r["freed_area_m2"] is None        # 합계를 0으로 채우지 않음
    assert r["space_status"] == "계산 보류" and any("미확인 구역" in m for m in r["missing"])
    both_short = core.aging_slots(1.2, 0.9, 0.95, zones=[AZ_B, {**AZ_B, "name": "z2"}])
    assert both_short["space_status"] == "추가 공간 필요"


def test_aging_zones_validation():
    with pytest.raises(core.InputError, match="중복"):
        core.aging_slots(1.2, 0.9, 0.95, zones=[AZ_A, AZ_A])
    with pytest.raises(core.InputError, match="알 수 없는"):
        core.aging_slots(1.2, 0.9, 0.95, zones=[{**AZ_A, "hot_days": 5}])
    with pytest.raises(core.InputError, match="고온 구역"):
        core.aging_slots(1.2, 0.9, 0.95, zones=[{**AZ_A, "old_wait_days": -1}])
    with pytest.raises(core.InputError, match="상온 구역"):
        core.aging_slots(1.2, 0.9, 0.95, zones=[AZ_A, {**AZ_B, "conversion_fraction": 1.5}])
    with pytest.raises(core.InputError):
        core.aging_slots(1.2, 0.9, 0.95, zones=["x"])


def test_aging_zones_reach_run_csv_pdf(cfg, tmp_path):
    res = core.run_scenario(cfg, "custom", {"aging_zones": [AZ_A, AZ_B]})
    assert res["aging"]["zone_mode"] and res["plant"]["E_total"] == approx(85.62)       # 공장 전력 불변
    items = [x["item"] for x in res["requirements"]]
    assert "에이징 고온 구역 추가 슬롯비" in items and "에이징 상온 구역 추가 슬롯비" in items
    out = tmp_path / "o"
    assert reporting.export_all(res, out, reporting.make_run_info("cli"))["pdf_pages"] == 4
    with open(out / "requirements.csv", encoding="utf-8-sig") as fh:
        rows = [r for r in csv.DictReader(fh) if r["kind"] == "에이징 구역"]
    conv = [r for r in rows if r["item"] == "고온 구역 전환 가능 슬롯(조건부)"][0]
    assert float(conv["value"]) == approx(100.0) and conv["unit"] == "slot"


def test_pdf_stays_four_pages_in_worst_case(cfg, tmp_path):
    many = [{**AZ_A, "name": f"구역 {i}"} for i in range(1, 9)]
    res = core.run_scenario(cfg, "custom", {"drying_r_source": "mode_b", "drying_b_zones": zones(),
                                            "drying_b_global": gl(qsource_kwth=60.0, qset_kwth=400.0),
                                            "aging_zones": many})
    assert len(res["warnings"]) >= 2 and len(res["aging"]["zones"]) == 8
    assert reporting.export_all(res, tmp_path / "o", reporting.make_run_info("cli"))["pdf_pages"] == 4


# ---------------------------------------------------------------- 7. R2 / 6. 폰트 라이선스
def test_r2_recorded_but_not_listed_as_used(tmp_path):
    ev = {e["evidence_id"]: e for e in core.load_csv(core.DEFAULT_EVIDENCE)}
    assert ev["R2"]["doi"] == "10.1016/j.joule.2019.11.002" and "Formation Challenges" in ev["R2"]["title"]
    assert "미인용" in ev["R2"]["used_in"]
    assert [k for k in ev if k.startswith("R")] == [f"R{i}" for i in range(1, 12)]      # R1~R11 빠짐 없음
    out = tmp_path / "o"
    reporting.export_all(core.run_scenario(core.load_config(), "representative"), out, reporting.make_run_info("cli"))
    with open(out / "evidence.csv", encoding="utf-8-sig") as fh:
        rows = {r["evidence_id"]: r for r in csv.DictReader(fh)}
    assert rows["R2"]["used_in_report"] == "N" and rows["R3"]["used_in_report"] == "Y"
    text = pdf_text(out / "result_report.pdf")
    assert "R2" in text and "10.1016/j.joule.2019.11.002" not in text      # 사용하지 않은 문헌은 표에 넣지 않음


def test_font_license_preserved(tmp_path):
    lic = (ROOT / "assets" / "fonts" / "OFL.txt").read_text(encoding="utf-8")
    assert "SIL OPEN FONT LICENSE Version 1.1" in lic and "NHN Corporation" in lic and "DISCLAIMER" in lic
    assert "OFL" in (ROOT / "README.md").read_text(encoding="utf-8")
    out = tmp_path / "o"
    reporting.export_all(core.run_scenario(core.load_config(), "representative"), out, reporting.make_run_info("cli"))
    assert "SIL Open Font License 1.1" in pdf_text(out / "result_report.pdf")
    man = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
    assert "OFL" in man["font_note"] and any(s["path"].endswith("OFL.txt") for s in man["input_sources"])
