"""핵심 검산·오류 처리·통합 검산. 기대값은 v10 PDF/과제 검산값이며 테스트 통과를 위해 바꾸지 않는다."""
import copy
import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import core  # noqa: E402
import run  # noqa: E402

approx = pytest.approx
W = [35, 25, 10, 5, 25]
F = [0.2, 0.8, 0.1, 0.7, 0.5]
R = [0.4, 0.3, 0.3, 0, 0]


@pytest.fixture(scope="module")
def cfg():
    return core.load_config()


@pytest.fixture(scope="module")
def rep(cfg):
    return core.run_scenario(cfg, "representative")


def fm(fh, add, ch=1.0):
    return core.formation_capacity(fh, add, ch, 1.0, 1.0)


# ---------------------------------------------------------------- 15.1 화성
def test_formation_reference_values():
    assert 20 / 16.25 == approx(1.2307692308)
    assert 20 / 18 == approx(1.1111111111)
    assert 1.08 * 20 / 18 == approx(1.2)
    assert fm(16, 0.25)["capacity_ratio"] == approx(1.2307692308, abs=1e-9)
    assert fm(16, 2)["capacity_ratio"] == approx(1.1111111111, abs=1e-9)
    assert fm(16, 2, 1.08)["capacity_ratio"] == approx(1.2, abs=1e-9)
    assert fm(16, 0.25)["allowed_added_h"] == approx(0.6666666667, abs=1e-9)


def test_formation_status_and_required_channel():
    assert fm(16, 0.25)["status"] == core.NUM_OK
    assert fm(16, 2)["status"] == core.NUM_FAIL
    assert fm(16, 2, 1.08)["status"] == core.NUM_OK        # 반올림 이전 값으로 판정(≈1.2)
    r = fm(16, 2)
    assert r["required_channel_ratio"] == approx(1.08)
    assert r["extra_channel_ratio"] == approx(0.08)
    assert fm(14, 0)["extra_channel_ratio"] == 0


def test_formation_negative_allowed_not_clipped():
    assert fm(18, 0)["allowed_added_h"] < 0          # 0으로 바꾸지 않는다
    assert fm(18, 0)["allowed_added_h"] == approx(20 / 1.2 - 18)


def test_formation_channels_rounded_up():
    r = core.formation_capacity(16, 2, 1.0, 1.0, 1.0, baseline_channels=100)
    assert r["required_channels"] == 108


# ---------------------------------------------------------------- 15.2 / 15.3
def test_aging_slots_reference():
    r = core.aging_slots(1.2, 0.9, 0.95)
    assert r["additional_slot_ratio"] == approx(0.1368421053, abs=1e-9)
    assert core.aging_slots(1.2, 0.85, 0.95)["additional_slot_ratio"] == approx(0.0737, abs=1e-4)
    assert r["convertible_slots"] is None and r["space_status"] == "계산 보류"   # 공간 입력 미확인


def test_aging_space_conditional_and_negative_area():
    ok = core.aging_slots(1.2, 0.9, 0.95, 100, 14, 120, 10, 0.5, 2.0, 0.5)
    assert ok["freed_wip"] == approx(200) and ok["freed_area_m2"] == approx(100)
    assert ok["convertible_slots"] == approx(100 * 2.0 * 0.5) and ok["space_status"] == "조건부"
    bad = core.aging_slots(1.2, 0.9, 0.95, 100, 14, 200, 14, 0.5, 2.0, 0.5)
    assert bad["freed_area_m2"] < 0 and bad["space_status"] == "추가 공간 필요"
    assert bad["convertible_slots"] == 0


def test_fan_affinity():
    assert 0.9 ** 3 == approx(0.729)
    assert 0.8 ** 3 == approx(0.512)
    assert core.fan_affinity(10, 0.8) == approx(5.12)


# ---------------------------------------------------------------- 15.4 건조 A
def test_drying_mode_a_reference():
    c1 = core.drying_mode_a(1.0, 0.7, 0.52, 3.85, 3.0)["saving_ratio"]
    c2 = core.drying_mode_a(0.8, 0.7, 0.52, 3.85, 3.0)["saving_ratio"]
    # 기대값 '약 30.795% / 42.204%' 는 소수 셋째 자리 반올림값 -> 허용 오차 5e-6
    assert c1 == approx(0.30795, abs=5e-6) and c2 == approx(0.42204, abs=5e-6)
    assert f"{c1 * 100:.1f}%" == "30.8%" and f"{c2 * 100:.1f}%" == "42.2%"
    # v10 표의 다른 열
    assert core.drying_mode_a(1.0, 0.7, 0.52, 3.0, 3.0)["saving_ratio"] == approx(0.277, abs=5e-4)


def test_drying_mode_a_validation():
    with pytest.raises(core.InputError):
        core.drying_mode_a(0.8, 0.7, 0.52, 1.0, 3.0)      # COP_h <= 1
    with pytest.raises(core.InputError):
        core.drying_mode_a(1.2, 0.7, 0.52, 3.85, 3.0)


# ---------------------------------------------------------------- 건조 B (시험용 가상 입력)
def zones(**kw):
    z = {"name": "z", "fan_base_kwe": 10.0, "fan_new_kwe": None, "airflow_ratio": 0.9, "fan_affinity": True,
         "heat_base_kwth": 100.0, "heat_new_kwth": 90.0, "aux_electric_kwe": 1.0, "hp_eligible_kwth": 60.0,
         "supply_temp_ok": True}
    z.update(kw)
    return [copy.deepcopy(z) for _ in range(3)]


def gl(**kw):
    g = {"qset_kwth": 500.0, "qsource_kwth": 500.0, "cop_h": 3.0, "cop_c": 3.0, "heater_eff": 1.0,
         "compatible_cooling_kwth": 20.0, "total_cooling_kwth": 30.0, "aux_base_kwe": 0.0}
    g.update(kw)
    return g


def test_mode_b_calculation():
    r = core.drying_mode_b(zones(), gl())
    assert r["status"] == core.NUM_OK
    assert r["Qh"] == approx(180.0)                       # min(500, 180, 500/(1-1/3)=750)
    assert r["W"] == approx(60.0) and r["Qc"] == approx(120.0)
    assert r["Qcool_used"] == approx(20.0)               # 적합 냉각수요로 제한
    fan_new = 3 * 10 * 0.9 ** 3
    e_new = (270 - 180) / 1.0 + 60 + (30 - 20) / 3 + fan_new + 3
    e_base = 30 + 300 + 30 / 3
    assert r["E_new"] == approx(e_new) and r["saving_ratio"] == approx(1 - e_new / e_base)


def test_mode_b_missing_inputs_hold_not_zero():
    r = core.drying_mode_b(core.load_config()["base_inputs"]["drying_b_zones"]["value"],
                           core.load_config()["base_inputs"]["drying_b_global"]["value"])
    assert r["status"] == core.NUM_HOLD and len(r["missing"]) >= 29
    zs = zones(); zs[0]["heat_new_kwth"] = None
    assert core.drying_mode_b(zs, gl())["status"] == core.NUM_HOLD
    assert core.drying_mode_b(zones(), gl(total_cooling_kwth=None, compatible_cooling_kwth=None))["status"] == core.NUM_HOLD
    assert core.drying_mode_b(zones(), gl(qsource_kwth=None))["status"] == core.NUM_HOLD   # 열원 무한대 가정 금지


def test_mode_b_zero_cooling_is_confirmed_zero():
    r = core.drying_mode_b(zones(), gl(compatible_cooling_kwth=0.0, total_cooling_kwth=0.0))
    assert r["status"] == core.NUM_OK and r["Qcool_used"] == 0.0


def test_mode_b_source_limit_never_exceeded():
    r = core.drying_mode_b(zones(), gl(qsource_kwth=60.0))      # 열원 60 -> Qh <= 60/(1-1/3)=90
    assert r["Qh"] == approx(90.0) and r["limit_by"] == "열원"
    assert r["Qc"] <= 60.0 + 1e-9


def test_mode_b_supply_temperature_blocks_heat_pump():
    zs = zones(supply_temp_ok=False)
    assert core.drying_mode_b(zs, gl())["Qh"] == 0.0


def test_mode_b_errors():
    with pytest.raises(core.InputError):
        core.drying_mode_b(zones(), gl(cop_h=1.0))
    with pytest.raises(core.InputError):
        core.drying_mode_b(zones(heat_new_kwth=-1.0, hp_eligible_kwth=0.0), gl())      # 음수 열량
    with pytest.raises(core.InputError):
        core.drying_mode_b(zones(), gl(compatible_cooling_kwth=40.0))                  # 적합 냉각수요 초과
    with pytest.raises(core.InputError):
        core.drying_mode_b(zones(hp_eligible_kwth=95.0), gl())                         # 열부하 초과
    with pytest.raises(core.InputError):
        core.drying_mode_b(zones()[:2], gl())                                           # 정확히 3구간


# ---------------------------------------------------------------- 15.5 공장 전력
def test_plant_reference_values():
    assert core.plant_energy(W, F, [0] * 5, 1.2, 0)["E_total"] == approx(111.2)
    p = core.plant_energy(W, F, R, 1.2, 2)
    assert p["E_total"] == approx(85.62) and p["saving_ratio"] == approx(0.2865)
    assert p["target_energy"] == approx(84.0) and p["gap"] == approx(1.62) and p["status"] == core.NUM_FAIL
    assert [round(e, 2) for e in (p["B"][0] - p["E"][0], p["B"][1] - p["E"][1], p["B"][2] - p["E"][2])] == [16.24, 7.8, 3.54]
    z = core.plant_energy(W, F, R, 1.2, 0)
    assert z["E_total"] == approx(83.62) and z["saving_ratio"] == approx(0.3031666667) and z["status"] == core.NUM_OK
    assert core.plant_energy(W, [0] * 5, R, 1.2, 2)["E_total"] == approx(92.6)


def test_p_add_not_rescaled():
    assert core.plant_energy(W, F, R, 1.2, 2)["P_add"] == 2          # 0.02로 바꾸지 않음
    with pytest.raises(core.InputError):
        core.plant_energy(W, F, R, 1.2, 0.02, p_add_unit="ratio")


# ---------------------------------------------------------------- 15.6 역산
def test_reverse_requirements_reference(rep):
    req = {x["system"]: x["r_required"] for x in rep["reverse"]}
    assert req["건조"] == approx(0.4399014778, abs=1e-9)
    assert req["드라이룸"] == approx(0.3623076923, abs=1e-9)
    assert req["기타"] == approx(0.0589090909, abs=1e-9)


def test_reverse_roundtrip_hits_target():
    p = core.plant_energy(W, F, R, 1.2, 2)
    for j, x in enumerate(core.reverse_requirements(p, R)):
        if x["r_required"] is None or not 0 <= x["r_required"] <= 1:
            continue
        r2 = list(R); r2[j] = x["r_required"]
        assert core.plant_energy(W, F, r2, 1.2, 2)["E_total"] == approx(p["target_energy"])


def test_reverse_over_one_not_clipped_and_zero_B():
    p = core.plant_energy(W, F, R, 1.2, 40)
    d = core.reverse_requirements(p, R)[0]
    assert d["r_required"] > 1 and "불가능" in d["interpretation"]
    p0 = core.plant_energy([0, 60, 10, 5, 25], F, R, 1.2, 2)
    assert core.reverse_requirements(p0, R)[0]["r_required"] is None
    assert core.required_reduction(10, 2, 84, 0) is None
    p_ok = core.plant_energy(W, F, [0.9, 0.9, 0.9, 0, 0.5], 1.2, 0)
    assert core.reverse_requirements(p_ok, [0.9, 0.9, 0.9, 0, 0.5])[0]["interpretation"].startswith("추가 절감 불필요")


# ---------------------------------------------------------------- 15.7 오류 처리
def test_input_errors():
    with pytest.raises(core.InputError):
        core.formation_capacity(-16, 0.25, 1.0, 1.0, 1.0)
    with pytest.raises(core.InputError):
        core.formation_capacity(16, -0.25, 1.0, 1.0, 1.0)
    with pytest.raises(core.InputError):
        core.formation_capacity(16, 0.25, 0.0, 1.0, 1.0)
    with pytest.raises(core.InputError):
        core.formation_capacity(16, 0.25, 1.0, 1.5, 1.0)
    with pytest.raises(core.InputError):
        core.plant_energy([35, 25, 10, 5, 20], F, R, 1.2, 2)          # 비중합 != 100
    with pytest.raises(core.InputError):
        core.plant_energy(W, [1.2, 0, 0, 0, 0], R, 1.2, 2)
    with pytest.raises(core.InputError):
        core.plant_energy(W, F, R, 0, 2)


def test_unit_mismatch_blocks_calculation(cfg):
    res = core.run_scenario(cfg, "custom", {"p_add_aggregate": {"value": 2, "unit": "kWh"}})
    assert "단위 불일치" in res["blocked"] and "plant" not in res
    res = core.run_scenario(cfg, "custom", {"formation_h": {"value": 16, "unit": "day"}})
    assert res.get("blocked")


def test_null_vs_zero(cfg):
    assert core.formation_capacity(16, None, 1.0, 1.0, 1.0)["status"] == core.NUM_HOLD
    assert core.formation_capacity(16, 0, 1.0, 1.0, 1.0)["status"] == core.NUM_OK
    r = core.run_scenario(cfg, "custom", {"added_occupancy_source": "input"})   # added_occupancy_h = null
    assert r["formation"]["status"] == core.NUM_HOLD
    assert r["plant"]["status"] in (core.NUM_OK, core.NUM_FAIL)                  # 독립 계산은 계속
    r0 = core.run_scenario(cfg, "custom", {"added_occupancy_source": "input", "added_occupancy_h": 0})
    assert r0["formation"]["capacity_ratio"] == approx(1.25)
    r = core.run_scenario(cfg, "custom", {"p_add_aggregate": None})
    assert r["plant"]["status"] == core.NUM_HOLD and r["formation"]["status"] == core.NUM_OK
    r = core.run_scenario(cfg, "custom", {"p_add_aggregate": 0})
    assert r["plant"]["E_total"] == approx(83.62)


def test_mode_b_hold_does_not_fall_back_to_mode_a(cfg):
    r = core.run_scenario(cfg, "custom", {"drying_r_source": "mode_b"})
    assert r["drying_b"]["status"] == core.NUM_HOLD and r["plant"]["status"] == core.NUM_HOLD
    assert r["formation"]["status"] == core.NUM_OK and r["drying_a"]["status"] == core.NUM_OK


# ---------------------------------------------------------------- 이중 계산 방지
def test_mode_a_b_not_double_applied(cfg):
    with pytest.raises(core.InputError):
        core.validate_accounting(["mode_a", "mode_b"])
    with pytest.raises(core.InputError):
        core.validate_accounting(["manual", "mode_a"])
    with pytest.raises(core.InputError):
        core.validate_accounting(["mode_a"], zone_savings_applied_globally=True)
    core.validate_accounting(["mode_a"])
    # 모드 A 채택 시 수동 r[0]=0.4 는 사용되지 않는다
    r = core.run_scenario(cfg, "custom", {"drying_r_source": "mode_a"})
    assert r["r_effective"][0] == approx(r["drying_a"]["saving_ratio"]) and r["r_effective"][0] != 0.4


def test_regen_not_double_counted():
    core.validate_accounting(["manual"], {"accounting": "in_r", "independent_pt": None})
    with pytest.raises(core.InputError):
        core.validate_accounting(["manual"], {"accounting": "in_r", "independent_pt": 1.0})
    with pytest.raises(core.InputError):
        core.validate_accounting(["manual"], {"accounting": "independent", "independent_pt": 1.0,
                                              "r_includes_regen": True, "usable": True})
    with pytest.raises(core.InputError):
        core.validate_accounting(["manual"], {"accounting": "independent", "independent_pt": 1.0, "usable": None})
    with pytest.raises(core.InputError):
        core.validate_accounting(["manual"], {"accounting": "independent", "independent_pt": None})


def test_regen_independent_in_run(cfg):
    r = core.run_scenario(cfg, "custom", {"regen_accounting": "independent", "regen_independent_pt": 1.0,
                                          "regen_usable": True})
    assert r["plant"]["E_total"] == approx(84.62)
    r = core.run_scenario(cfg, "custom", {"regen_accounting": "in_r", "regen_independent_pt": 1.0})
    assert r["plant"]["status"] == core.NUM_ERR


# ---------------------------------------------------------------- PFMEA
def test_pfmea_six_risks_and_accounting(rep):
    pf = rep["pfmea"]
    assert pf["counts"]["risks"] == 6
    assert {r["risk_id"] for r in pf["rows"]} == {"F01", "F02", "D01", "D02", "R01", "A01"}
    assert all(r["accounting_location"] in core.ACCT_LOCATIONS for r in pf["rows"])
    assert rep["added_occupancy_h"] == approx(0.25) and rep["p_add"]["value"] == 2.0
    assert pf["counts"]["reflected"] == 1 and pf["counts"]["burden_unknown"] == 8      # 미확인 부담은 0으로 처리하지 않음
    assert core.pfmea_table(rep)[0]["공정 변경"].startswith("F01")


def test_quality_unknown_vs_numeric(rep):
    assert rep["plant"]["status"] == core.NUM_FAIL and rep["quality_status"] == "미확인"
    assert rep["formation"]["status"] == core.NUM_OK                    # 수치 충족 + 품질 미확인 = 검증 후보
    assert "검증 후보" in rep["conclusion"] or "조건부" in rep["conclusion"]


def test_quality_override_requires_note_and_unmet_excludes(cfg):
    r = core.run_scenario(cfg, "representative", quality_overrides={"F02": {"status": "충족", "note": ""}})
    assert r["pfmea"].get("status") == core.NUM_ERR
    r = core.run_scenario(cfg, "representative", quality_overrides={"F02": {"status": "미충족", "note": "독립 검증 실패(시험)"}})
    assert r["quality_status"] == "미충족" and r["pfmea"]["counts"]["excluded"] == 1
    assert r["added_occupancy_h"] is None and r["formation"]["status"] == core.NUM_HOLD   # 제외된 효과는 자동 반영 안 함
    r = core.run_scenario(cfg, "representative", quality_overrides={
        k: {"status": "충족", "note": "시험용 근거 메모"} for k in ("F01", "F02", "D01", "D02", "R01", "A01")})
    assert r["quality_status"] == "충족"
    r = core.run_scenario(cfg, "representative", quality_overrides={"F01": {"status": "검증 중", "note": "시험"}})
    assert r["quality_status"] == "검증 중"


def test_duplicate_action_id_rejected(cfg):
    rows = core.load_csv(core.DEFAULT_PFMEA)
    r = core.run_scenario(cfg, "representative", pfmea_rows=rows + [dict(rows[2])])
    assert r["pfmea"]["status"] == core.NUM_ERR and "중복 action_id" in r["pfmea"]["error"]
    assert r["formation"]["status"] == core.NUM_HOLD


def test_aggregate_and_itemized_not_mixed(cfg):
    r = core.run_scenario(cfg, "custom", {"p_add_mode": "itemized"})        # aggregate 2.0 도 남아 있음 -> 차단
    assert r["pfmea"]["status"] == core.NUM_ERR and "itemized" in r["pfmea"]["error"]
    rows = core.load_csv(core.DEFAULT_PFMEA)
    for x in rows:
        if x["action_id"] == "D01-A2":
            x["impact_value"] = "1.5"
    r = core.run_scenario(cfg, "representative", pfmea_rows=rows)           # aggregate + 개별 정량 -> 차단
    assert r["pfmea"]["status"] == core.NUM_ERR


def test_itemized_mode(cfg):
    rows = core.load_csv(core.DEFAULT_PFMEA)
    r = core.run_scenario(cfg, "custom", {"p_add_mode": "itemized", "p_add_aggregate": None}, pfmea_rows=rows)
    assert r["plant"]["status"] == core.NUM_HOLD                          # 개별 전력 부담 미확인 -> 합계 확정 불가
    for x in rows:
        if x["action_id"] in ("D01-A2", "R01-A1"):
            x["impact_value"] = "1.0"
    r = core.run_scenario(cfg, "custom", {"p_add_mode": "itemized", "p_add_aggregate": None}, pfmea_rows=rows)
    assert r["p_add"]["value"] == approx(2.0) and r["plant"]["E_total"] == approx(85.62)


def test_pfmea_effect_not_counted_twice(cfg):
    r = core.run_scenario(cfg, "custom", {"added_occupancy_source": "input", "added_occupancy_h": 2.0})
    assert r["formation"]["total_occupancy_h"] == approx(18.0)           # PFMEA 0.25h 는 더하지 않음
    row = [x for x in r["pfmea"]["rows"] if x["action_id"] == "F02-A1"][0]
    assert row["calc_status"].startswith("수치 기록")


# ---------------------------------------------------------------- 시나리오·그래프
def test_scenarios(cfg):
    ap = core.run_scenario(cfg, "all_proportional")
    assert ap["plant"]["E_total"] == approx(92.6) and ap["scenario_label"] == "모든 부하 비례"
    assert core.run_scenario(cfg, "representative")["scenario_label"] == "v10 대표"
    assert core.run_scenario(cfg, "custom")["scenario_label"] == "사용자 조건"


def test_comparison_and_before_after(rep):
    ids = {c["id"]: c for c in rep["comparison"]}
    assert ids["C3"]["capacity_ratio"] == approx(1.2) and ids["E2"]["E_total"] == approx(85.62)
    assert ids["E1"]["saving_ratio"] == approx(0.3031666667) and ids["E0"]["E_total"] == approx(111.2)
    ba = {b["stage"]: b for b in rep["before_after"]}
    assert ba["관리조치 반영 후"]["E_total"] == approx(85.62) and ba["공정 개선만(관리조치 전)"]["E_total"] == approx(83.62)


def test_boundary_data_and_grid_limit(rep):
    fd = core.formation_boundary_data(rep["inputs"])
    at16 = {d["channel_ratio"]: d["allowed_added_h"] for d in fd if abs(d["formation_h"] - 16) < 1e-9}
    assert at16[1.0] == approx(0.6666666667, abs=1e-9) and at16[1.08] == approx(2.0, abs=1e-9)
    ed = core.energy_boundary_data(rep["inputs"], rep["r_effective"], [0.0, 2.0])
    pt = [d for d in ed if d["P_add"] == 2.0 and abs(d["r_dryroom"] - 0.3) < 1e-9][0]
    assert pt["r_drying_required"] == approx(0.4399014778, abs=1e-9)
    with pytest.raises(core.InputError):
        core._check_grid(5001)


def test_self_check_all_pass():
    items = core.self_check()
    assert len(items) == 15 and all(i["pass"] for i in items)


def test_fmt_policy():
    assert core.fmt_pct_up(0.3623076923) == "36.3%" and core.fmt_pct_up(0.4399014778) == "44.0%"
    assert core.fmt_pct(0.28650) == "28.65%"


# ---------------------------------------------------------------- 15.8 통합 검산: CLI -> Core -> CSV -> PDF
def test_cli_core_csv_pdf_consistent(tmp_path, cfg):
    out = tmp_path / "o"
    assert run.main(["--scenario", "representative", "--out", str(out)]) == 0
    expected = core.run_scenario(cfg, "representative")
    for name in ("result_report.pdf", "scenario_comparison.csv", "requirements.csv", "pfmea_summary.csv",
                 "evidence.csv", "formation_boundary.png", "energy_boundary.png", "run_manifest.json"):
        assert (out / name).exists(), name
    with open(out / "scenario_comparison.csv", encoding="utf-8-sig") as fh:
        rows = {r["id"]: r for r in csv.DictReader(fh)}
    assert float(rows["E2"]["E_total"]) == approx(expected["plant"]["E_total"])
    assert float(rows["E2"]["saving_ratio"]) == approx(expected["plant"]["saving_ratio"])
    assert float(rows["C1"]["capacity_ratio"]) == approx(expected["formation"]["capacity_ratio"])
    with open(out / "requirements.csv", encoding="utf-8-sig") as fh:
        req = {r["item"]: r for r in csv.DictReader(fh)}
    assert float(req["건조"]["r_required"]) == approx(0.4399014778, abs=1e-9)
    with open(out / "pfmea_summary.csv", encoding="utf-8-sig") as fh:
        assert len(list(csv.DictReader(fh))) == 9
    man = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
    assert man["scenario"] == "representative" and man["execution_mode"] == "cli"
    assert man["configuration_hash"] == expected["config_hash"] and man["test_status"]["status"] == "not_run"
    assert man["python_version"] and "numpy" in man["package_versions"] and man["input_sources"]

    from pypdf import PdfReader
    from PIL import Image
    rd = PdfReader(str(out / "result_report.pdf"))
    assert len(rd.pages) == 4
    text = "\n".join(p.extract_text() for p in rd.pages)
    pl = expected["plant"]
    for token in (core.fmt_pct(pl["saving_ratio"], 2), f"{pl['E_total']:.2f}", f"{pl['gap']:+.2f}",
                  core.fmt_pct_up(0.4399014778), "10.1038/s41560-023-01355-z"):
        assert token in text, token
    for n in ("formation_boundary.png", "energy_boundary.png"):
        im = Image.open(out / n)
        assert round(im.info["dpi"][0]) == 300
    assert (out / "scenario_comparison.csv").read_bytes().startswith(b"\xef\xbb\xbf")   # utf-8-sig


def test_cli_custom_set_and_bad_set(tmp_path):
    assert run.main(["--scenario", "custom", "--set", "channel_ratio=1.08", "--set",
                     "added_occupancy_source=\"input\"", "--set", "added_occupancy_h=2", "--out", str(tmp_path),
                     "--no-export"]) == 0
    with pytest.raises(SystemExit):
        run.parse_sets(["x=not-json"])
    assert run.main(["--scenario", "custom", "--set", "q=1.2", "--out", str(tmp_path), "--no-export"]) == 0


def test_forbidden_features_absent():
    import re
    src = "".join((ROOT / n).read_text(encoding="utf-8") for n in ("core.py", "app.py", "run.py", "reporting.py")).lower()
    for word in ("sklearn", "torch", "tensorflow", "shap", "openai", "anthropic", "sqlite", "docker"):
        assert not re.search(rf"{word}", src), word
