"""발표에서 시연할 4가지 동작을 테스트로 고정한다 (발전 제안서 '꼭 통과해야 할 네 가지 시연').

① 에너지만 충족하면 전체 목표 충족으로 표시하지 않는다.
② 추가 관리 부담을 늘리면 허용치를 넘어 목표 미달로 바뀐다.
③ 결합 이득 유지율(κ)을 낮추면 추천 조합의 판정이 바뀐다.
④ 검증한 공정 조건을 바꾸면 기존 품질 확인을 승계하지 않는다.
"""
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import core  # noqa: E402
import evidence_engine as ee  # noqa: E402

CFG = core.load_config()
VALS, _ = core.resolve_inputs(CFG)
KB = ee.load_kb()
CLEAN, _ = ee.validate_kb(KB)
V10 = [l["lever_id"] for l in CLEAN["levers"] if l.get("v10_adopted") == "예"]
REC = V10 + ["DRY-RAD", "DRY-HSC"]


def _B(v):
    return [wi * (fi + (1 - fi) * v["q"]) for wi, fi in zip(v["w"], v["f"])]


def _assess(v, sel=REC, clean=CLEAN):
    eff = ee.classify_effects(clean, v["w"], {**ee.DEFAULT_ELECTRIC_HEATING, **(v.get("kb_electric_heating") or {})})
    return ee.assess(clean, eff, sel, v, _B(v))


def _all_gates_confirmed(v, sel=REC, conditions=None):
    q = ee.quality_status(CLEAN, sel, v)
    return {r["fmea_id"]: {"status": "확인", "conditions": conditions or {}, "memo": "테스트"} for r in q["rows"]}


# ------------------------------------------------------------ ①
def test_demo1_energy_only_is_not_overall_success():
    a = _assess(dict(VALS))
    assert a["energy_verdict"] in ("근거상 충족", "조건부 충족 (대표값 기준)")      # 에너지는 충족
    assert a["production"]["aging_status"].startswith("미확보")                    # 에이징 근거 없음
    assert a["overall"]["label"] == "증산 미완결 - 에이징 보관능력"
    assert not a["overall"]["all_ok"]


def test_demo1_quality_pending_blocks_overall_success_even_when_numbers_pass():
    kb = copy.deepcopy(KB)
    row = {c: "" for c in __import__("kb_schema").columns("effects")}
    row.update(effect_id="T-SLOT", lever_id="AGE-RACK", metric="slot_gain_ratio", value_typ="0.20", unit="ratio",
               basis="t", boundary="계통전체", chemistry="NCM", cell_format="파우치", scale="양산", source_id="R4",
               locator="p.1", excerpt="t", evidence_grade="B", verification="원문 확인")
    kb["effects"].append(row)
    clean, _ = ee.validate_kb(kb)
    v = dict(VALS)
    a = _assess(v, clean=clean)
    assert a["production"]["aging_status"].startswith("근거상 확보")
    assert a["overall"]["label"] == "수치 충족 · 확인 대기(건조 속도·품질)"        # 품질 관문·건조 속도 미확인
    v["kb_quality_confirmations"] = _all_gates_confirmed(v)
    a2 = _assess(v, clean=clean)
    assert a2["overall"]["label"] == "수치 충족 · 확인 대기(건조 속도)"            # 품질만 확인해도 건조 속도가 남음
    v["drying_max_speed_ratio_verified"] = 1.2                                       # 파일럿 실측 입력
    v["kb_quality_confirmations"] = _all_gates_confirmed(v)
    a3 = _assess(v, clean=clean)
    assert "동시 충족" in a3["overall"]["label"]
    assert next(x for x in a3["overall"]["axes"] if x["axis"].startswith("건조"))["state"] == "검증 완료"


# ------------------------------------------------------------ ②
def test_demo2_extra_burden_beyond_allowance_flips_to_shortfall():
    v = dict(VALS)
    eff = ee.classify_effects(CLEAN, v["w"])
    sens = ee.combination_sensitivity(CLEAN, eff, REC, v, _B(v))
    pmax = sens["p_max"][1.0]
    assert pmax is not None and pmax > 0
    below = _assess({**v, "kb_extra_burden_pt": pmax - 0.05})
    above = _assess({**v, "kb_extra_burden_pt": pmax + 0.05})
    assert below["cases"]["typical"]["plant_ok"] and not above["cases"]["typical"]["plant_ok"]
    assert above["energy_verdict"] in ("근거 상한에서만 충족", "근거상 미달")


# ------------------------------------------------------------ ③
def test_demo3_lower_combination_retention_changes_recommendation_verdict():
    v = dict(VALS)
    eff = ee.classify_effects(CLEAN, v["w"])
    sens = ee.combination_sensitivity(CLEAN, eff, REC, v, _B(v))
    p = (sens["p_max"][0.5] + sens["p_max"][1.0]) / 2      # κ=1이면 버티고 κ=0이면 무너지는 부담 수준
    k1 = _assess({**v, "kb_combine_retention": 1.0, "kb_extra_burden_pt": p})
    k0 = _assess({**v, "kb_combine_retention": 0.0, "kb_extra_burden_pt": p})
    assert k1["cases"]["typical"]["saving"] > k0["cases"]["typical"]["saving"]
    assert k1["cases"]["typical"]["plant_ok"] and not k0["cases"]["typical"]["plant_ok"]
    assert k1["energy_verdict"] != k0["energy_verdict"]


def test_kappa_zero_equals_largest_single_lever_in_system():
    eff = ee.classify_effects(CLEAN, VALS["w"])
    both, _ = ee.system_ranges(CLEAN, eff, ["DRY-RAD", "DRY-HSC"], kappa=0.0)
    rad, _ = ee.system_ranges(CLEAN, eff, ["DRY-RAD"])
    hsc, _ = ee.system_ranges(CLEAN, eff, ["DRY-HSC"])
    assert both["건조"]["typ"] == pytest.approx(max(rad["건조"]["typ"], hsc["건조"]["typ"]))
    indep, _ = ee.system_ranges(CLEAN, eff, ["DRY-RAD", "DRY-HSC"], kappa=1.0)
    assert indep["건조"]["typ"] == pytest.approx(1 - (1 - rad["건조"]["typ"]) * (1 - hsc["건조"]["typ"]))
    half, _ = ee.system_ranges(CLEAN, eff, ["DRY-RAD", "DRY-HSC"], kappa=0.5)
    assert half["건조"]["typ"] == pytest.approx((both["건조"]["typ"] + indep["건조"]["typ"]) / 2)


def test_sensitivity_grid_is_monotone():
    s = ee.evaluate(dict(VALS))["sensitivity"]
    g = s["saving_typ"]
    assert all(g[i][j] <= g[i + 1][j] + 1e-12 for i in range(len(g) - 1) for j in range(len(g[0])))   # κ↑ → 절감↑
    assert all(g[i][j] >= g[i][j + 1] - 1e-12 for i in range(len(g)) for j in range(len(g[0]) - 1))   # P↑ → 절감↓


# ------------------------------------------------------------ ④
def test_demo4_changed_process_condition_resets_quality_confirmation():
    v = dict(VALS)
    v["kb_quality_confirmations"] = _all_gates_confirmed(v, conditions={"formation_h": v["formation_h"]})
    q = ee.quality_status(CLEAN, REC, v)
    assert q["counts"]["확인"] == len(q["rows"]) > 0
    v2 = {**v, "formation_h": v["formation_h"] - 1.0}           # 화성 시간을 다시 바꿈
    q2 = ee.quality_status(CLEAN, REC, v2)
    assert q2["counts"]["재검증 필요"] == len(q2["rows"]) and q2["counts"]["확인"] == 0
    assert "formation_h" in q2["rows"][0]["changed"][0]


def test_quality_failure_excludes_combination():
    v = dict(VALS)
    conf = _all_gates_confirmed(v)
    first = next(iter(conf))
    conf[first] = {"status": "불합격", "memo": "테스트"}
    a = _assess({**v, "kb_quality_confirmations": conf})
    assert a["overall"]["label"].startswith("적용 제외") and first in a["overall"]["label"]


# ------------------------------------------------------------ 에이징 단축 근거 (AGE-EARLY)
@pytest.mark.parametrize("after, ok", [(12, True), (13, False)])
def test_aging_shortening_evidence_closes_or_not_production_gap(after, ok):
    import kb_schema as S
    kb = copy.deepcopy(KB)
    kb["effects"] = [e for e in kb["effects"] if e["lever_id"] != "AGE-EARLY"]   # 다른 에이징 근거 제거 후 이 행만 시험
    row = {c: "" for c in S.columns("effects")}
    row.update(effect_id="T-AGE", lever_id="AGE-EARLY", metric="aging_days_before_after", value_before="14",
               value_after=str(after), unit="day", basis="t", boundary="계통전체", chemistry="NCM", cell_format="파우치",
               scale="양산", source_id="R4", locator="p.1", excerpt="t", evidence_grade="B", verification="원문 확인")
    kb["effects"].append(row)
    clean, issues = ee.validate_kb(kb)
    assert not [i for i in issues if i["level"] == "error"]
    a = _assess(dict(VALS), sel=REC + ["AGE-EARLY"], clean=clean)
    # 필요 배수 1.2×0.90/0.95 = 1.137 → 기간비 12/14 = 0.857이면 0.974 ≤ 1 (성립), 13/14 = 0.929이면 1.056 (부족)
    assert a["production"]["aging_status"].startswith("근거상 확보" if ok else "미확보")
    assert ("에이징 단축" in a["production"]["aging_status"])


def test_duplicate_doi_under_new_id_is_rejected():
    kb = copy.deepcopy(KB)
    r1 = next(s for s in kb["sources"] if s["source_id"] == "R1")
    kb["sources"].append({**r1, "source_id": "DGN-2023-REF", "doi": "https://doi.org/" + r1["doi"].upper()})
    _clean, issues = ee.validate_kb(kb)
    err = [i for i in issues if i["level"] == "error" and i["id"] == "DGN-2023-REF"]
    assert err and "R1" in err[0]["msg"]


def test_grade_d_only_aging_evidence_is_conditional_not_confirmed():
    import kb_schema as S
    kb = copy.deepcopy(KB)
    kb["effects"] = [e for e in kb["effects"] if e["lever_id"] != "AGE-EARLY"]
    row = {c: "" for c in S.columns("effects")}
    row.update(effect_id="T-PAT", lever_id="AGE-EARLY", metric="aging_days_before_after", value_before="13",
               value_after="4", unit="day", basis="t", boundary="계통전체", chemistry="NCM", cell_format="파우치",
               scale="양산", source_id="R4", locator="청구항", excerpt="t", evidence_grade="D", verification="원문 확인")
    kb["effects"].append(row)
    clean, _ = ee.validate_kb(kb)
    a = _assess(dict(VALS), sel=REC + ["AGE-EARLY"], clean=clean)
    assert a["production"]["aging_status"].startswith("조건부 확보") and "등급 D" in a["production"]["aging_status"]
    assert a["overall"]["label"] == "수치 충족 · 확인 대기(건조 속도·품질)"


def test_cross_study_share_is_reference_unless_allowed():
    kb = copy.deepcopy(KB)
    r = dict(next(e for e in kb["effects"] if e["effect_id"] == "EF-003"))
    r.update(effect_id="T-X", boundary_share="")          # 같은 문헌 비중이 없는 공장전체 행
    kb["effects"].append(r)
    clean, _ = ee.validate_kb(kb)
    e = next(x for x in ee.classify_effects(clean, VALS["w"]) if x["effect_id"] == "T-X")
    assert e["use"] == ee.USE_REF and "타 문헌 비중 환산" in e["flags"]
    e2 = next(x for x in ee.classify_effects(clean, VALS["w"], allow_cross_share=True) if x["effect_id"] == "T-X")
    assert e2["use"] == ee.USE_CALC
    # Lechner 원행은 같은 문헌 비중 0.71로 계산에 들어감
    e3 = next(x for x in ee.classify_effects(clean, VALS["w"]) if x["effect_id"] == "EF-003")
    assert e3["use"] == ee.USE_CALC and e3["typ"] == pytest.approx((1 - 37.28 / 46.74) / 0.71)


def test_recommendation_adds_aging_lever_when_production_blocked():
    ev = ee.evaluate(dict(VALS))
    assert ev["recommended"]["production_add"] == ["AGE-EARLY"]
    assert not ev["production"]["aging_status"].startswith(("근거상", "조건부"))      # v10 레버만: 미확보
    assert ev["production_rec"]["aging_status"].startswith("조건부")               # 특허(등급 D)뿐 → 조건부


def test_confirmation_record_snapshots_conditions_and_requires_memo():
    v = dict(VALS)
    gate = next(r for r in CLEAN["fmea"] if r["lever_id"] == "FOR-FAST" and r.get("quality_gate"))
    with pytest.raises(ValueError):
        ee.confirmation_record(CLEAN, gate["fmea_id"], "확인", "", v)
    rec = ee.confirmation_record(CLEAN, gate["fmea_id"], "확인", "파일럿 T-01 통과", v)
    assert rec["conditions"]["formation_h"] == v["formation_h"]
    v["kb_quality_confirmations"] = {gate["fmea_id"]: rec}
    assert next(r for r in ee.quality_status(CLEAN, REC, v)["rows"] if r["fmea_id"] == gate["fmea_id"])["status"] == "확인"
    v2 = {**v, "formation_h": v["formation_h"] + 0.5}
    assert next(r for r in ee.quality_status(CLEAN, REC, v2)["rows"] if r["fmea_id"] == gate["fmea_id"])["status"] == "재검증 필요"


def test_added_aging_days_burden_can_break_aging_axis():
    import kb_schema as S
    kb = copy.deepcopy(KB)
    kb["effects"] = [e for e in kb["effects"] if e["lever_id"] != "AGE-EARLY"]
    row = {c: "" for c in S.columns("effects")}
    row.update(effect_id="T-AGE", lever_id="AGE-EARLY", metric="aging_days_before_after", value_before="14",
               value_after="10", unit="day", basis="t", boundary="계통전체", chemistry="NCM", cell_format="파우치",
               scale="양산", source_id="R4", locator="p.1", excerpt="t", evidence_grade="B", verification="원문 확인")
    kb["effects"].append(row)
    kb["fmea"] = [f for f in kb["fmea"] if f["lever_id"] != "AGE-EARLY"]
    fm = {c: "" for c in S.columns("fmea")}
    fm.update(fmea_id="T-FM", lever_id="AGE-EARLY", failure_mode="t", mechanism="t", affected="시간", control_action="t",
              detection_method="t", burden_metric="added_aging_days", burden_typ="3", unit="day", quality_gate="t",
              source_id="R4", locator="p.1", excerpt="t", evidence_grade="B", verification="원문 확인")
    kb["fmea"].append(fm)
    clean, iss = ee.validate_kb(kb)
    assert not [i for i in iss if i["level"] == "error"]
    a = _assess(dict(VALS), sel=REC + ["AGE-EARLY"], clean=clean)
    # 10일 + 3일 = 13일 > 12.31일 → 부족
    assert a["production"]["aging_status"].startswith("미확보")
    assert a["production"]["aging_added_days"]["typ"] == pytest.approx(3.0)
