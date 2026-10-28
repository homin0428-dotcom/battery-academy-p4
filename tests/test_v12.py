"""v12 반례 시험 16개 - 모델이 틀렸을 때 실패하도록 설계한 시험 (설계서 §6 M12 표 그대로)."""
import json

import pytest

import baseline as BL
import candidates as C
import capacity as K
import core
import evidence_engine as ee
import joint as J
import necessity as N
import upside as U

V, _ = core.resolve_inputs(core.load_config())
V = {**V, "kb_effect_selection": {}}   # v12 모델 검사는 기술군 중앙값 기준 (v12.2 공식 설계 고정은 test_v122)
CLEAN, _ = ee.validate_kb(ee.load_kb())
RUN = C.run_candidates(V, CLEAN)
EFF = RUN["eff"]


def _c(run, cid):
    return next(c for c in run["candidates"] if c["id"] == cid)


def _ax(c, p):
    return next(a for a in c["axes"] if a["axis"].startswith(p))


B1 = _c(RUN, "B1")
SPEC_B1 = next(s for s in V["kb_candidates"] if s["id"] == "B1")


def test_official_result_unchanged():
    assert B1["saving"][1] == pytest.approx(0.355977, abs=1e-6)
    assert B1["E_typ"] == pytest.approx(77.283, abs=1e-3) and B1["margin_pt"] == pytest.approx(6.717, abs=1e-3)
    assert RUN["selected"] == "B1"


# 1
def test_01_solids_continuity_at_s0():
    vals = [C.evaluate_candidate(CLEAN, EFF, {**SPEC_B1, "solids_override": s}, B1["levers"], V)["saving"][1]
            for s in (0.5999, 0.6, 0.6001)]
    assert max(vals) - min(vals) < 1e-4                                    # 0.01%p 미만
    assert vals[1] == pytest.approx(0.3411, abs=2e-4)


# 2
def test_02_s1_equal_s0_matches_hsc_removed_combination():
    at_s0 = C.evaluate_candidate(CLEAN, EFF, {**SPEC_B1, "solids_override": 0.60}, B1["levers"], V)
    no_hsc = C.evaluate_candidate(CLEAN, EFF, {"id": "x", "name": "x"}, [l for l in B1["levers"] if l != "DRY-HSC"], V)
    assert at_s0["saving"][1] == pytest.approx(no_hsc["saving"][1], abs=1e-12)


def test_02b_invalid_solids_raise():
    for bad in (0, -0.1, 1.0, 1.2):
        with pytest.raises(core.InputError):
            C.run_candidates({**V, "solids_old": bad}, CLEAN)


# 3
def test_03_verification_isolated_per_candidate():
    rec = [{"candidate_id": "B1", "metric": "drying_speed_ratio", "value": 1.25, "conditions": _ax(B1, "건조")["conditions"]}]
    r = C.run_candidates({**V, "kb_verifications": rec}, CLEAN)
    assert _ax(_c(r, "B1"), "건조")["state"] == C.ST_DONE
    for cid in ("A", "B0", "B2"):
        assert _ax(_c(r, cid), "건조")["state"] != C.ST_DONE


# 4
def test_04_condition_change_invalidates_confirmation():
    rec = [{"candidate_id": "B1", "metric": "drying_speed_ratio", "value": 1.25, "conditions": {"solids": 0.65}}]
    r = C.run_candidates({**V, "solids_old": 0.62, "kb_verifications": rec}, CLEAN)   # B1 고형분 0.67로 바뀜
    a = _ax(_c(r, "B1"), "건조")
    assert a["state"] != C.ST_DONE and "재검증 필요" in a["status"]
    # 품질 관문: B1 조건(고형분 0.65)으로 확인한 기록은 고형분이 바뀌면 재검증
    g = next(x for x in B1["quality"]["rows"] if ee._lever(CLEAN, x["lever_id"])["system"] == "건조")
    cv = {**V, "solids": 0.65, "candidate_id": "B1"}
    conf = {g["fmea_id"]: ee.confirmation_record(CLEAN, g["fmea_id"], "확인", "시험 T-1", cv, "B1")}
    r2 = C.run_candidates({**V, "kb_quality_confirmations": conf, "kb_candidates": [
        {**s, "solids": 0.80} if s["id"] == "B1" else s for s in V["kb_candidates"]]}, CLEAN)
    st = next(x for x in _c(r2, "B1")["quality"]["rows"] if x["fmea_id"] == g["fmea_id"])["status"]
    assert st == "재검증 필요"
    # 에이징 14일 조건으로 확인한 관문이 C(13일)로 승계되지 않음
    ga = next(x for x in B1["quality"]["rows"] if ee._lever(CLEAN, x["lever_id"])["system"] == "에이징")
    conf2 = {ga["fmea_id"]: ee.confirmation_record(CLEAN, ga["fmea_id"], "확인", "T-2", {**V, "aging_days": 14})}
    r3 = C.run_candidates({**V, "kb_quality_confirmations": conf2}, CLEAN)
    rows_c = {x["fmea_id"]: x["status"] for x in _c(r3, "C")["quality"]["rows"]}
    if ga["fmea_id"] in rows_c:
        assert rows_c[ga["fmea_id"]] != "확인"


# 5
def test_05_waterfall_sums_to_saving():
    wf = BL.decompose(V, B1)
    assert wf["check"]
    assert sum(s["pp"] for s in wf["steps"]) / 100 == pytest.approx(B1["saving"][1], abs=1e-9)
    assert wf["dilution_pp"] == pytest.approx(7.333, abs=1e-3) and wf["tech_pp"] == pytest.approx(28.26, abs=0.01)


# 6
def test_06_f_zero_stress():
    r = C.run_candidates({**V, "f": [0.0] * 5}, CLEAN)
    b = _c(r, "B1")
    assert b["saving"][1] == pytest.approx(0.3045, abs=1e-4) and b["margin_pt"] == pytest.approx(0.54, abs=0.01)


# 7
def test_07_joint_alpha_P():
    s = {x["id"]: x for x in J.stress(V, CLEAN, B1)["rows"]}
    assert s["S1"]["saving"] == pytest.approx(0.2971, abs=1e-4) and not s["S1"]["ok"]
    rg = J.region(V, CLEAN, EFF, B1)
    assert rg["closed_form_ok"] and rg["alpha_star"] == pytest.approx(0.781, abs=1e-3)
    assert rg["p_max"][0.9] == pytest.approx(3.65, abs=0.01)


# 8
def test_08_b0_drying_axis():
    b0 = _c(RUN, "B0")
    d = _ax(b0, "건조")
    assert d["need_time_ratio"] == pytest.approx(1.0) and not d["calc_ok"] and d["weak_ok"]
    assert b0["saving"][1] == pytest.approx(0.3411, abs=1e-4) and b0["margin_pt"] == pytest.approx(4.93, abs=0.01)


# 9
def test_09_lever_necessity():
    rows = {r["lever_id"]: r for r in N.lever_necessity(V, CLEAN, EFF, B1)["rows"]}
    assert rows["DRY-RAD"]["delta_pp"] == pytest.approx(13.88, abs=0.01)
    assert rows["DRM-LOCAL"]["delta_pp"] == pytest.approx(8.01, abs=0.01)
    assert rows["FOR-FAST"]["delta_pp"] == pytest.approx(3.68, abs=0.01)
    assert rows["DRY-HSC"]["delta_pp"] == pytest.approx(1.49, abs=0.01)
    assert rows["DRY-RAD"]["label_without"].startswith("미달")


# 10
def test_10_b2_required():
    assert N.b2_required(V, CLEAN, EFF, RUN)["hx_required"] == pytest.approx(0.266, abs=1e-3)
    st = N.structure(V, CLEAN, EFF, B1)
    assert st["h_star"] == pytest.approx(0.596, abs=2e-3) and st["M3"] == pytest.approx(0.3411, abs=1e-4)


# 11
def test_11_yield():
    same = C.evaluate_candidate(CLEAN, EFF, SPEC_B1, B1["levers"], {**V, "q_good": V["q"]})
    assert same["saving"][1] == pytest.approx(B1["saving"][1], abs=1e-12)
    y = K.yield_scenario(V, CLEAN, EFF, B1, 0.95)
    assert y["q_load"] == pytest.approx(1.2 / 0.95) and y["E"] > B1["E_typ"]


# 12
def test_12_shadow_mode():
    sh = U.shadow_mode(V)
    assert sh["n_required"] == 299
    r = {x["days"]: x for x in sh["rows"]}
    assert r[13]["slot_need"] == pytest.approx(0.0556, abs=1e-4) and r[12.315]["slot_need"] == pytest.approx(0, abs=1e-4)
    assert r[10]["lead_time_h"] == 256 and sh["base_lead_time_h"] == 356


# 13
def test_13_upside_and_shadow_do_not_change_result():
    ev = C.evaluate(V, CLEAN)
    assert ev["selected"] == "B1"
    assert _c(ev, "B1")["saving"][1] == pytest.approx(B1["saving"][1], abs=1e-12)


# 14
def test_14_results_json_matches_csv_and_pdf(tmp_path):
    res = core.run_scenario(core.load_config(), "representative")
    import reporting
    r = reporting.export_all(res, tmp_path, reporting.make_run_info("cli"))
    assert r["consistency"]["ok"], r["consistency"]
    js = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert js["official_candidate"] == "B1" and js["headline"]["saving"]["typical"] == pytest.approx(0.349755, abs=1e-6)   # v12.2 공식 = 설계 고정 D2


# 15
def test_15_stage_qt():
    st = K.stage_table(V, CLEAN, EFF, B1)["stages"][0]
    assert st["q_t"] == pytest.approx(1.0556, abs=1e-4)
    assert st["at_q_t"]["saving"] == pytest.approx(0.0873, abs=2e-4)
    assert st["at_q12"]["saving"] == pytest.approx(0.1371, abs=1e-4)


# 16
def test_16_old_model_isolated_in_appendix(tmp_path):
    res = core.run_scenario(core.load_config(), "representative")
    import reporting
    reporting.export_all(res, tmp_path, reporting.make_run_info("cli"))
    from pypdf import PdfReader
    pages = [p.extract_text() or "" for p in PdfReader(str(tmp_path / "evidence_report.pdf")).pages]
    idx = next(i for i, t in enumerate(pages) if "부록 A" in t)
    main = " ".join(pages[:idx])
    assert "추천 조합(+DRY-RAD" not in main and "AGE-EARLY): 수치" not in main
    assert idx >= 6


# ---------------------------------------------------------------- v12 추가 (M7·M9·M10·설정)
def test_17_new_fmea_rows_and_gate_counts():
    ids = {f["fmea_id"] for f in CLEAN["fmea"]}
    assert {"FM-V12-01", "FM-V12-02", "FM-V12-03"} <= ids
    rows = {r["fmea_id"] for r in B1["quality"]["rows"]}
    assert {"FM-V12-01", "FM-V12-02", "FM-V12-03"} <= rows                 # B1(고형분·복사·국소화)에 모두 걸림
    g = {f["fmea_id"]: f for f in CLEAN["fmea"]}
    assert g["FM-V12-01"]["evidence_grade"] == "D" and g["FM-V12-01"]["source_id"] == "R22"     # Reynolds 2022 원문 확인
    assert g["FM-V12-02"]["evidence_grade"] == "E" and g["FM-V12-03"]["evidence_grade"] == "E"


def test_17b_baseline_sources_registered():
    src = {s["source_id"] for s in CLEAN["sources"]}
    assert {"R22", "R23", "R24", "R25"} <= src
    assert V["solids_old"] == 0.60
    card = {r["item"]: r for r in BL.baseline_card(V)}
    assert card["기존 고형분 s0"]["origin"].startswith("문헌") and "R22" in card["기존 고형분 s0"]["source"]
    sh = U.shadow_mode(V)
    assert sh["natural_example"]["weeks_natural"][0] == pytest.approx(299 / (100000 * 7 * 1e-5))


def test_18_effect_selection_filters_and_default_unchanged():
    sel = {"DRM-LOCAL": ["EF-003", "EF-004"]}
    eff2 = ee.apply_effect_selection(EFF, sel)
    assert ee.lever_saving(eff2, "DRM-LOCAL")["ids"] == ["EF-003", "EF-004"]
    r = C.run_candidates({**V, "kb_effect_selection": sel}, CLEAN)
    assert _c(r, "B1")["saving"][1] != pytest.approx(B1["saving"][1], abs=1e-6)
    assert ee.apply_effect_selection(EFF, {}) is EFF


def test_19_core_package_mode():
    ev = C.evaluate({**V, "kb_package_mode": "core"}, CLEAN)
    b = _c(ev, "B1")
    assert b["saving"][1] == pytest.approx(B1["saving"][1], abs=1e-9)   # 기여 0 레버를 빼도 절감 동일
    assert b["n_gates"] < B1["n_gates"] and set(b["levers"]) == {"DRY-RAD", "DRM-LOCAL", "FOR-FAST", "DRY-HSC", "AGE-RACK"}


def test_20_economics_and_rollout():
    import economics as E
    nec = N.lever_necessity(V, CLEAN, EFF, B1)
    le = E.lever_economics(V, ee.plant_electricity(EFF, V), nec)
    rad = next(r for r in le["rows"] if r["lever_id"] == "DRY-RAD")
    assert rad["pt"] == pytest.approx(13.88 * 1.2, abs=0.02)
    assert rad["breakeven_eok"][3][0] == pytest.approx(rad["krw_eok"][0] * 3)
    ro = E.rollout(V, CLEAN, B1, nec)
    assert ro["warnings"] == []
    bad = E.rollout({**V, "rollout": [{"lever_id": "DRY-ZONE", "start_q": 1, "duration_q": 2, "target_pp": 2.0}]}, CLEAN, B1, nec)
    assert bad["warnings"]                                                  # 기여 0 레버에 목표 → 경고
    le2 = E.lever_economics({**V, "capex_eok": {"DRY-RAD": [300, 600]}}, ee.plant_electricity(EFF, V), nec)
    assert next(r for r in le2["rows"] if r["lever_id"] == "DRY-RAD")["payback_years"] is not None


def test_21_heat_map_does_not_change_result():
    import heat_integration as H
    hm = H.analyze(V)
    assert len(hm["nodes"]) >= 5 and hm["matches"] and all(m["power_effect_pt"] == 0 for m in hm["matches"])
    ev = C.evaluate(V, CLEAN)
    assert _c(ev, "B1")["saving"][1] == pytest.approx(B1["saving"][1], abs=1e-12)


def test_22_joint_test_in_priority_and_ranges_from_config():
    ev = C.evaluate(V, CLEAN)
    j = next(t for t in ev["priority"]["tests"] if t["id"] == "JOINT")
    assert j["impact"] == "목표 판정 변경"
    assert V["baseline_ranges"]["f_all"]["lo"] == 0.5
    sv = BL.sensitivity({**V, "baseline_ranges": {"phi": {"label": "φ", "lo": 0.0, "hi": 1.0}}}, CLEAN)
    assert len(sv["rows"]) == 1
