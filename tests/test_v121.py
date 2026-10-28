"""v12.1 - 조원 자료조사 반영 + PPT용 출력. 결론 숫자는 v12와 같아야 한다."""
import pytest

import baseline
import candidates as C
import core
import evidence_engine as ee
import roadmap
import upside


@pytest.fixture(scope="module")
def ctx():
    v, _ = core.resolve_inputs(core.load_config())
    v = {**v, "kb_effect_selection": {}}          # v12.1 기능 검사는 기술군 중앙값 기준 (v12.2 공식은 설계 고정 D2 - test_v122)
    cd = C.evaluate(v)
    return v, cd


def _sel(cd):
    return next(c for c in cd["candidates"] if c["id"] == cd["selected"])


def test_headline_median_unchanged(ctx):
    _, cd = ctx
    b1 = _sel(cd)
    assert cd["selected"] == "B1"
    assert abs(b1["saving"][1] - 0.355977) < 1e-5
    assert abs(b1["E_typ"] - 77.283) < 1e-3
    assert abs(b1["margin_pt"] - 6.717) < 1e-3
    assert b1["n_gates"] == 41 and b1["n_safety_gates"] == 15     # FM-V12-01 보강은 행을 늘리지 않음


def test_new_sources_present():
    clean, _ = ee.validate_kb(ee.load_kb())
    ids = {s["source_id"]: s for s in clean["sources"]}
    for sid in ("R26", "R27", "R28", "R29"):
        assert sid in ids
    assert ids["R8"]["access"] == "원문" and "0.17" in ids["R8"]["note"]
    fm = next(f for f in clean["fmea"] if f["fmea_id"] == "FM-V12-01")
    assert "슬롯다이" in fm["failure_mode"] and "R28" in fm["excerpt"]


def test_literature_cases(ctx):
    v, cd = ctx
    rows = {r["key"]: r for r in cd["baseline_model"]["literature_cases"]["rows"]}
    assert abs(rows["split_sun"]["saving"] - 0.3575) < 5e-4 and abs(rows["split_sun"]["margin_pt"] - 6.90) < 0.01
    assert abs(rows["split_sun_f0"]["saving"] - 0.3066) < 5e-4 and abs(rows["split_sun_f0"]["margin_pt"] - 0.79) < 0.01
    assert all(r["selected"] == "B1" for r in rows.values())


def test_shadow_period_table(ctx):
    v, _ = ctx
    pt = upside.shadow_mode(v)["period_table"]
    by = {r["label"]: r for r in pt["rows"]}
    d = by["예시 1000 ppm"]["days"]
    assert abs(d[0] - 299 / 134300e-3) < 1e-6 and abs(by["예시 100 ppm"]["days"][1] - 299 / (110473 * 1e-4)) < 1e-6
    assert not any(r["ppm"][0] >= 5000 for r in pt["rows"])        # 공정 평균 불량률은 에이징 불량률이 아님


def test_space_plan(ctx):
    v, cd = ctx
    sp = cd["roadmap"]["space"]
    assert abs(sp["slot_need"] - (1.2 * 0.9 / 0.95 - 1)) < 1e-9
    assert abs(sp["area_upper"] - 0.25 * sp["slot_need"]) < 1e-12
    assert abs(sp["formation_wip"] - 0.96) < 1e-9
    assert [o["no"] for o in sp["options"]] == ["①", "②", "③", "④"]
    assert "확보 완료" not in sp["sentence"] and "달성" not in sp["sentence"]


def test_reach(ctx):
    _, cd = ctx
    rows = cd["roadmap"]["reach"]["rows"]
    assert abs(rows[0]["power_no_slot"] - 0.08733) < 1e-4 and not rows[0]["power_ok_no_slot"]
    assert abs(rows[1]["power_no_slot"] - 0.3182) < 1e-4 and abs(rows[1]["power_if_slot"] - _sel(cd)["saving"][1]) < 1e-9
    assert rows[1]["q_if_slot"] == pytest.approx(1.2) and rows[1]["q_no_slot"] == pytest.approx(19 / 18)


def test_power_grade_rule():
    assert roadmap.power_grade(13.88) == "상" and roadmap.power_grade(5.0) == "상"
    assert roadmap.power_grade(3.68) == "중" and roadmap.power_grade(1.49) == "중"
    assert roadmap.power_grade(0.5) == "하"


def test_impact_and_horizon(ctx):
    _, cd = ctx
    im = {r["lever_id"]: r for r in cd["roadmap"]["impact"]["rows"]}
    assert im["DRY-HSC"]["power"].startswith("중") and im["DRY-RAD"]["power"].startswith("상")
    assert "454~591억" in im["DRY-RAD"]["capex"]
    hz = {r["lever_id"]: r for r in cd["roadmap"]["horizon"]["rows"]}
    assert hz["DRY-RAD"]["horizon"].startswith("중기") and hz["FOR-FAST"]["horizon"] == "단기"
    assert "즉시" in hz["FOR-FAST"]["when"] and "아님" in hz["FOR-FAST"]["when"]


def test_departments_share(ctx):
    _, cd = ctx
    assert round(cd["roadmap"]["departments"]["share_dry"] * 100) == 87


def test_kpi_card(ctx):
    _, cd = ctx
    assert cd["roadmap"]["kpi"]["title"].startswith("공장 처리능력 1.056배")


def test_baseline_card_sources(ctx):
    v, _ = ctx
    card = {r["item"]: r for r in baseline.baseline_card(v)}
    assert "R26" in card["화성 10 / 에이징 5 분할"]["source"]
    assert "R8" in card["고정부하 비율 f"]["source"]
    assert "R28" in card["목표 고형분 s0 + 0.05"]["source"]
