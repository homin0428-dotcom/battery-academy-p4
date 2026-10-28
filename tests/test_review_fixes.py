"""외부 검토(2026-10-21) 재현 결함 회귀 테스트.

각 테스트는 검토자가 직접 재현한 입력 조건을 그대로 사용한다. 수정 전 코드에서는 실패해야 한다.
프로젝트의 실제 configs/scenarios.json 과 data/pfmea.csv 를 사용한다.
"""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core  # noqa: E402

CFG = core.load_config()
ROWS = core.load_csv(core.DEFAULT_PFMEA)
W, F = [35, 25, 10, 5, 25], [0.2, 0.8, 0.1, 0.7, 0.5]
R_REP = [0.4, 0.3, 0.3, 0.0, 0.0]


def _rows():
    return copy.deepcopy(ROWS)


def _row(rows, action_id):
    return next(r for r in rows if r["action_id"] == action_id)


def _zone(**kw):
    z = {"fan_base_kwe": 10, "heat_base_kwth": 50, "heat_new_kwth": 45, "aux_electric_kwe": 0,
         "hp_eligible_kwth": 40, "fan_affinity": False, "fan_new_kwe": 9, "supply_temp_ok": True}
    z.update(kw)
    return z


G = dict(qset_kwth=200, qsource_kwth=100, cop_h=3.5, cop_c=3, heater_eff=1,
         compatible_cooling_kwth=10, total_cooling_kwth=20, aux_base_kwe=0)


# ------------------------------------------------------------ 대표값 불변
def test_representative_values_unchanged():
    r = core.run_scenario(CFG)
    assert r["formation"]["capacity_ratio"] == pytest.approx(1.2307692308, abs=1e-9)
    assert r["plant"]["saving_ratio"] == pytest.approx(0.2865, abs=1e-9)
    assert r["plant"]["gap"] == pytest.approx(1.62, abs=1e-9)
    assert all(x["pass"] for x in core.self_check())


# ------------------------------------------------------------ 필수 1: 품질 집계
def test_quality_unmet_in_second_action_makes_overall_unmet():
    rows = _rows()
    for r in rows:
        r["quality_status"] = "충족"
    _row(rows, "F01-A2")["quality_status"] = "미충족"   # 같은 위험 F01의 두 번째 조치만 미충족
    res = core.run_scenario(CFG, pfmea_rows=rows)
    assert res["pfmea"]["risk_quality"]["F01"] == "미충족"
    assert res["quality_status"] == "미충족"
    f01 = next(t for t in core.pfmea_table(res) if t["risk_id"] == "F01")
    assert "미충족" in f01["확인 상태"]


def test_quality_mixed_met_and_unknown_is_not_met():
    rows = _rows()
    for r in rows:
        r["quality_status"] = "충족"
    _row(rows, "F01-A2")["quality_status"] = "미확인"
    assert core.run_scenario(CFG, pfmea_rows=rows)["pfmea"]["risk_quality"]["F01"] == "검증 중"


# ------------------------------------------------------------ 필수 2: 미충족 → 적용 제외
def test_unmet_quality_concludes_excluded_not_candidate():
    res = core.run_scenario(CFG, quality_overrides={"F01": {"status": "미충족", "note": "검토 시험"}})
    assert "현재 조건에서 적용 제외" in res["conclusion"]
    assert "검증 후보 또는 조건부" not in res["conclusion"]
    assert "적용 제외" in res["kpi"][-1]["sub"]


# ------------------------------------------------------------ 필수 3: 미확인 시간 부담
def test_unknown_time_burden_is_lower_bound_and_holds_ok_verdict():
    rows = _rows() + [dict(_row(_rows(), "F02-A1"), action_id="F02-A3", impact_value="")]
    res = core.run_scenario(CFG, pfmea_rows=rows)
    fm = res["formation"]
    assert fm["occupancy_lower_bound"] is True
    assert fm["status"] == core.NUM_HOLD              # 하한 기준 '충족'은 확정하지 않음
    assert fm["capacity_is_upper_bound"] is True
    assert res["kpi"][0]["value"].startswith("≤")
    assert "F02-A3" in res["conclusion"]


def test_unknown_time_burden_fail_stays_fail():
    rows = _rows() + [dict(_row(_rows(), "F02-A1"), action_id="F02-A3", impact_value="")]
    _row(rows, "F02-A1")["impact_value"] = "2"        # 하한만으로도 미달
    fm = core.run_scenario(CFG, pfmea_rows=rows)["formation"]
    assert fm["status"] == core.NUM_FAIL and fm["occupancy_lower_bound"] is True


# ------------------------------------------------------------ 필수 4: PFMEA 단위
def test_pfmea_minutes_converted_to_hours():
    rows = _rows()
    _row(rows, "F02-A1").update(impact_value="15", impact_unit="min")
    res = core.run_scenario(CFG, pfmea_rows=rows)
    assert res["added_occupancy_h"] == pytest.approx(0.25)
    assert res["formation"]["capacity_ratio"] == pytest.approx(1.2307692308, abs=1e-9)


@pytest.mark.parametrize("unit", ["kWh", "sec", "", "pt"])
def test_pfmea_disallowed_unit_blocked(unit):
    rows = _rows()
    _row(rows, "F02-A1").update(impact_value="15", impact_unit=unit)
    with pytest.raises(core.InputError):
        core.analyze_pfmea(rows, core.resolve_inputs(CFG)[0])


def test_pfmea_non_numeric_value_is_input_error():
    rows = _rows()
    _row(rows, "F02-A1")["impact_value"] = "약 15분"
    with pytest.raises(core.InputError):
        core.analyze_pfmea(rows, core.resolve_inputs(CFG)[0])


# ------------------------------------------------------------ 필수 6: Boolean
def test_mode_b_string_false_disallows_heat_supply():
    b = core.drying_mode_b([_zone(supply_temp_ok="False"), _zone(), _zone()], G)
    assert b["zones"][0]["temp_ok"] is False
    assert b["zones"][0]["hp_usable"] == 0.0


@pytest.mark.parametrize("v,exp", [("True", True), ("예", True), ("아니오", False), (0, False), (1, True)])
def test_to_bool_explicit(v, exp):
    assert core.to_bool(v, "x") is exp


@pytest.mark.parametrize("v", ["maybe", 2, 0.5, "적합할 수도"])
def test_mode_b_uninterpretable_bool_is_error(v):
    with pytest.raises(core.InputError):
        core.drying_mode_b([_zone(supply_temp_ok=v), _zone(), _zone()], G)


# ------------------------------------------------------------ 연결 범위 표시
def test_pfmea_link_types_and_conclusion_mentions_manual_items():
    res = core.run_scenario(CFG)
    pf = res["pfmea"]
    links = {r["action_id"]: r["link_type"] for r in pf["rows"]}
    assert links["F02-A1"] == core.LINK_AUTO
    assert pf["manual_pending"], "수동 반영 대상이 표시되어야 한다"
    assert all(links[a] == core.LINK_MANUAL for a in pf["manual_pending"])
    assert "수동 검토" in res["conclusion"]


# ------------------------------------------------------------ 계산 경계
def test_regen_over_formation_energy_rejected():
    with pytest.raises(core.InputError):
        core.plant_energy(W, F, R_REP, 1.2, 2.0, "pt", 0.7, 200.0)


def test_regen_negative_rejected():
    with pytest.raises(core.InputError):
        core.plant_energy(W, F, R_REP, 1.2, 2.0, "pt", 0.7, -1.0)


def test_energy_increase_is_valid_tradeoff_not_input_error():
    zs = [_zone(aux_electric_kwe=300), _zone(), _zone()]
    res = core.run_scenario(CFG, "custom", {"drying_r_source": "mode_b", "drying_b_zones": zs, "drying_b_global": G})
    assert res["drying_b"]["saving_ratio"] < 0
    assert res["plant"]["status"] == core.NUM_FAIL
    assert "건조" in res["plant"]["increase_systems"]
    assert "전력이 증가" in res["conclusion"]


# ------------------------------------------------------------ 자동 연결 대상이나 값 미확인
def test_auto_target_with_unknown_value_is_labeled_pending():
    rows = _rows() + [dict(_row(_rows(), "F02-A1"), action_id="F02-A3", impact_value="")]
    res = core.run_scenario(CFG, pfmea_rows=rows)
    links = {r["action_id"]: r["link_type"] for r in res["pfmea"]["rows"]}
    assert links["F02-A3"] == core.LINK_AUTO_PENDING == "자동 반영 대상(값 미확인)"
    assert links["F02-A1"] == core.LINK_AUTO                     # 값이 있는 행은 그대로
    assert "F02-A3" not in res["pfmea"]["auto_linked"]           # 반영 건수에 포함되지 않음
    assert "F02-A3" not in res["pfmea"]["manual_pending"]        # 수동 대상으로도 분류하지 않음
    cell = next(t for t in core.pfmea_table(res) if t["risk_id"] == "F02")["계산 영향"]
    assert "(자동 반영 대상(값 미확인))" in cell
