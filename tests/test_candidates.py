"""A/B/C 후보 비교 엔진 - 독립 손계산 검산 + 판정 규칙 + 실패 경계 일관성."""
import math

import pytest

import candidates as C
import core
import evidence_engine as ee

V, _ = core.resolve_inputs(core.load_config())
V = {**V, "kb_effect_selection": {}}   # 기술군 중앙값 기준 회귀 검사 (설계 고정은 test_v122)
CLEAN, _ = ee.validate_kb(ee.load_kb())


def _run(**over):
    v = {**V, **over}
    return C.run_candidates(v, CLEAN)


def _c(run, cid):
    return next(c for c in run["candidates"] if c["id"] == cid)


def _ax(c, prefix):
    return next(a for a in c["axes"] if a["axis"].startswith(prefix))


# ---------------------------------------------------------------- ① 독립 산술 검산
def test_mass_balance_matches_hand_calculation():
    mb = C.mass_balance(0.60, 0.65, 1.2)
    assert mb["s1_min_keep_solvent"] == pytest.approx(0.72 / 1.12)            # 64.286%
    assert mb["solvent_vs_base"] == pytest.approx(1.2 * (0.35 / 0.65) / (0.40 / 0.60))   # 0.96923
    assert mb["solvent_vs_base"] == pytest.approx(0.969231, abs=1e-6)
    assert mb["solvent_cut_same_output"] == pytest.approx(0.192308, abs=1e-6)   # 19.23%
    assert C.mass_balance(0.60, mb["s1_min_keep_solvent"], 1.2)["solvent_vs_base"] == pytest.approx(1.0)


def test_drying_residual_keeps_fixed_load_and_matches_formula():
    v = {**V, "drying_solvent_load_share": [0.0, 0.5, 1.0]}
    mb = C.mass_balance(0.60, 0.65, 1.2)
    res = C.drying_residual(v, mb)
    f, q, R = v["f"][0], 1.2, mb["solvent_vs_base"]
    assert res["conservative"] == pytest.approx(1.0)                              # φ=0: 용매가 줄어도 전력 불변
    assert res["typical"] == pytest.approx((f + (1 - f) * (0.5 * R + 0.5 * q)) / (f + (1 - f) * q))
    # φ=1이어도 고정부하 f는 남는다 → 잔여비 > 용매비
    assert res["optimistic"] == pytest.approx((f + (1 - f) * R) / (f + (1 - f) * q))
    assert res["optimistic"] > R / q


def test_drying_axis_residence_and_required_time():
    run = _run()
    a, b = _ax(_c(run, "A"), "건조"), _ax(_c(run, "B1"), "건조")
    assert a["available_time_ratio"] == pytest.approx(1 / 1.2)                   # 0.8333
    assert a["need_time_ratio"] == pytest.approx(1.0) and not a["calc_ok"]       # 기존 배합: 증발속도 1.2배 필요
    assert a["evap_rate_multiplier"] == pytest.approx(1.2)
    assert b["need_time_ratio"] == pytest.approx((0.35 / 0.65) / (0.40 / 0.60)) and b["calc_ok"]
    assert a["state"] == b["state"] == C.ST_UNK                                  # 속도 상한 미계측 → 미확인


def test_formation_40min_and_aging_slot_table():
    run = _run()
    b = _c(run, "B1")
    fa = _ax(b, "화성")
    assert fa["allowed_added_h"] == pytest.approx(20 / 1.2 - 16)                 # 0.6667 h = 40분
    ag = _ax(b, "에이징")
    assert ag["required_slot_gain"] == pytest.approx(1.2 * 0.9 / 0.95 - 1)       # 13.68%
    assert ag["allowed_days_without_slots"] == pytest.approx(14 * 0.95 / (1.2 * 0.9))   # 12.315일
    cc = _c(run, "C")
    assert _ax(cc, "에이징")["required_slot_gain"] == pytest.approx(1.2 * 0.9 / 0.95 * 13 / 14 - 1, abs=1e-9)   # 5.56%


def test_same_baseline_and_money_formula():
    run = _run()
    pe = ee.plant_electricity(run["eff"], V)
    for c in run["candidates"]:
        assert c["E0"] == pytest.approx(111.2)                                    # 12 GWh 무개선 기준선 하나
        pt = 111.2 - c["E_typ"]
        assert c["money_typ"]["krw_eok"][0] == pytest.approx(pt / 100 * pe["gwh_lo"] * 1e6 * V["electricity_price_krw_per_kwh"] / 1e8)


def test_b_uses_mass_balance_not_literature_hsc_and_applies_other_levers_to_residual():
    run = _run()
    b = _c(run, "B1")
    # 같은 레버(고형분 제외)를 기존 배합으로 계산한 건조 절감 → 잔여부하에만 적용되는지
    lev = [l for l in b["levers"] if l != "DRY-HSC"]
    sysr, *_ = ee._run_cases(CLEAN, run["eff"], lev, V, C._B(V))
    r_lit = sysr["건조"]["typ"]
    assert b["r_drying"][1] == pytest.approx(1 - (1 - r_lit) * b["drying_residual"]["typical"])
    hsc = [e for e in C._mask_hsc(run["eff"]) if e["lever_id"] == "DRY-HSC" and e["role"] == "saving"]
    assert hsc and all(e["use"] != ee.USE_CALC for e in hsc)


# ---------------------------------------------------------------- 판정 규칙
def test_unknown_is_never_shown_as_pass_by_default():
    run = _run()
    for c in run["candidates"]:
        assert c["label"] not in (C.ST_DONE, C.ST_OK)
        assert not (c["n_fail"] == 0 and "현장 확인" not in c["label"])
    assert run["selected"] == "B1"
    assert _c(run, "A")["label"].startswith("미달")
    assert not _c(run, "C")["eligible"]                                          # 공간 미확인이면 C는 후보 아님


def test_space_decides_between_b_and_c():
    r_ok = _run(aging_slot_gain_approved=0.20)
    assert r_ok["selected"] == "B1" and _ax(_c(r_ok, "B1"), "에이징")["state"] == C.ST_DONE
    r_mid = _run(aging_slot_gain_approved=0.06)                                  # 13일(+5.56%)은 되고 14일(+13.68%)은 안 됨
    assert r_mid["selected"] == "C" and _ax(_c(r_mid, "C"), "에이징")["state"] == C.ST_UNK   # 단축 검출력 미검증
    r_zero = _run(aging_slot_gain_approved=0.0)
    assert "미달" in r_zero["status"]


def test_quality_failure_removes_candidate_and_switches():
    run = _run()
    g = next(r for r in _c(run, "B1")["quality"]["rows"] if r["lever_id"] == "DRY-RAD")
    r2 = _run(kb_quality_confirmations={g["fmea_id"]: {"status": "불합격", "memo": "t"}})
    assert not _c(r2, "B1")["eligible"] and r2["selected"] != "B1"


def test_gas_heating_changes_selection_and_reports_best_shortfall():
    eh = {**ee.DEFAULT_ELECTRIC_HEATING, "건조": False}
    r = C.run_candidates({**V, "kb_electric_heating": eh}, CLEAN)
    assert all(c["n_fail"] for c in r["candidates"] if c["eligible"])
    assert r["status"].startswith("최선 미달 후보")
    sel = _c(r, r["selected"])
    assert sel["shortfall"] and sel["shortfall"]["gap_pt"] > 0


def test_measured_drying_speed_gives_verified_or_fail():
    assert _ax(_c(_run(drying_max_speed_ratio_verified=1.25), "B1"), "건조")["state"] == C.ST_DONE
    r = _run(drying_max_speed_ratio_verified=1.1)
    assert _ax(_c(r, "B1"), "건조")["state"] == C.ST_FAIL


# ---------------------------------------------------------------- ③ 실패 경계 일관성
def test_boundaries_flip_exactly_at_boundary():
    run = _run()
    res = C.check_boundary_consistency(V, CLEAN, run["eff"], run["selected"])
    assert res and all(res.values()), res
    b = {x["kind"]: x for x in C.boundaries(V, CLEAN, run["eff"], run["selected"], run)}
    assert b["고형분(건조 처리능력)"]["value"] == pytest.approx(0.72 / 1.12)
    assert b["추가 관리 전력"]["value"] == pytest.approx(_c(run, "B1")["margin_pt"])


# ---------------------------------------------------------------- ④ 검증 우선순위
def test_priority_ranks_decision_changing_tests_first():
    ev = C.evaluate(V, CLEAN)
    tests = ev["priority"]["tests"]
    ranks = [t["impact_rank"] for t in tests]
    assert ranks == sorted(ranks)
    heat = next(t for t in tests if t["id"] == "HEAT-DRY")
    assert heat["impact"] == "추천 후보 변경"
    m = ev["priority"]["mandatory"]
    assert m and m == sorted(m, key=lambda x: (not x["safety"], x["lever_id"]))


def test_binomial_upper_bound():
    assert C.miss_rate_upper(300) == pytest.approx(1 - 0.05 ** (1 / 300))
    assert C.miss_rate_upper(300) == pytest.approx(0.00994, abs=5e-5)
    n = C.n_for_miss_rate(0.01)
    assert C.miss_rate_upper(n) <= 0.01 < C.miss_rate_upper(n - 1)


def test_evaluate_exposes_candidates():
    ev = ee.evaluate(V)
    assert ev["candidates"]["selected"] == "B1"
    assert {a["axis"][:2] for a in ev["overall"]["axes"]} >= {"에너", "건조", "화성", "에이", "품질"}
    assert all(a["state"] in C.STATES for a in ev["overall"]["axes"])
    assert not math.isnan(ev["candidates"]["baseline"]["E_q_no_change"])


# ---------------------------------------------------------------- v11.1 출력 추가분
def test_heat_sensitivity_uses_each_candidates_own_levers():
    ev = C.evaluate(V, CLEAN)
    row = {(r["case"], r["candidate"]): r for r in ev["heat"]["rows"]}
    gas = row[("건조 가스·스팀", "B1")]
    eh = {**ee.DEFAULT_ELECTRIC_HEATING, "건조": False}
    r2 = C.run_candidates({**V, "kb_electric_heating": eh}, CLEAN)
    b1 = _c(r2, "B1")
    assert gas["saving"][1] == pytest.approx(b1["saving"][1])
    # 고형분 잔여부하 × (1 - 가스 조건 문헌 건조 절감) - 다른 조합(고형분 60%)의 값과 다르다
    lev = [l for l in b1["levers"] if l != "DRY-HSC"]
    sysr, *_ = ee._run_cases(CLEAN, r2["eff"], lev, V, C._B(V))
    assert gas["r_drying"] == pytest.approx(1 - (1 - sysr["건조"]["typ"]) * b1["drying_residual"]["typical"])
    assert gas["r_drying"] != pytest.approx(sysr["건조"]["typ"])
    assert row[("기준(건조·드라이룸 전기)", "B1")]["selected"]


def test_stage_progress_accumulates_to_selected_candidate():
    ev = C.evaluate(V, CLEAN)
    st = ev["stages"]["stages"]
    assert [x["stage"] for x in st][0] == "1년차 운영 변경"
    assert st[-1]["saving"][1] == pytest.approx(_c(_run(), "B1")["saving"][1])
    assert sorted(st[-1]["levers"]) == sorted(_c(_run(), "B1")["levers"])
    assert "DRY-HSC" in st[0]["levers"] and st[0]["solids"] == pytest.approx(0.65)


def test_reverse_models_and_safety_counts():
    ev = C.evaluate(V, CLEAN)
    rv = {r["system"]: r for r in ev["reverse_models"]["rows"]}
    assert rv["건조"]["linear"] == pytest.approx(36 / 42)
    assert rv["건조"]["engine"] == pytest.approx(27.2 / 40.6)
    assert rv["드라이룸"]["linear"] == pytest.approx(1.2)
    n = {c["id"]: c["n_safety_gates"] for c in ev["candidates"]}
    assert n["B1"] <= n["C"] and all(isinstance(x, int) for x in n.values())


def test_absolute_electricity_rows_show_unit_and_relative_change():
    eh = {**ee.DEFAULT_ELECTRIC_HEATING, "건조": False}
    eff = ee.classify_effects(CLEAN, V["w"], eh, False, ee.plant_basis(CLEAN, V))
    e44 = next(e for e in eff if e["effect_id"] == "EF-044")
    assert "%가 아님" in e44["how"] and "+139.6%" in e44["how"]
