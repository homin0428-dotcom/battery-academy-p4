"""v12.2 - 설계 고정(D2) 공식 결과 + 설계 비교 · 두 목표 신호등 · 금액 카드 · P0 수정."""
import pytest

import candidates as C
import core
import design

D1 = {"DRM-LOCAL": ["EF-003"], "FOR-FAST": ["EF-017"], "DRY-RAD": ["EF-006"]}
D2 = {"DRM-LOCAL": ["EF-003"], "FOR-FAST": ["EF-018"], "DRY-RAD": ["EF-006"]}


@pytest.fixture(scope="module")
def ctx():
    v, _ = core.resolve_inputs(core.load_config())
    return v, C.evaluate(v)


def _sel(cd):
    return next(c for c in cd["candidates"] if c["id"] == cd["selected"])


def test_official_is_design_d2(ctx):
    v, cd = ctx
    assert v["kb_effect_selection"] == D2
    s = _sel(cd)
    assert cd["selected"] == "B1"
    assert abs(s["saving"][1] - 0.34976) < 1e-4 and abs(s["margin_pt"] - 5.97) < 0.01 and abs(s["E_typ"] - 78.03) < 0.01
    assert s["n_gates"] == 41 and s["n_safety_gates"] == 15


def test_design_compare_reproduces_review(ctx):
    _, cd = ctx
    rows = {r["key"]: r for r in cd["design"]["compare"]["rows"]}
    m, d1, d2 = rows["median"], rows["D1"], rows["D2"]
    assert abs(m["saving"][1] - 0.35598) < 1e-4 and abs(m["margin_pt"] - 6.717) < 1e-3       # v12.1 대표값
    assert abs(d1["saving"][1] - 0.3255) < 1e-4 and abs(d1["margin_pt"] - 3.06) < 0.01
    assert abs(d2["saving"][1] - 0.3498) < 1e-4 and d2["official"] and not d1["official"]
    assert not d1["ok"]["f0"] and not d1["ok"]["y2_no_slot"] and d2["ok"]["y2_no_slot"] and not d2["ok"]["f0"]
    assert abs(d1["alpha_star"] - 0.887) < 1e-3 and abs(d2["alpha_star"] - 0.801) < 1e-3
    assert [round(x) for x in d2["money_now"]] == [200, 260] and [round(x) for x in d2["money_nochange"]] == [302, 392]


def test_signal_table(ctx):
    _, cd = ctx
    rows = cd["design"]["signal"]["rows"]
    assert rows[0]["overall"] == "조건부 추천" and "1.200" in rows[0]["capacity"]
    assert rows[1]["overall"] == "전력만 충족" and "31.0%" in rows[1]["power"]
    assert "1.119" in rows[2]["capacity"]
    assert "1.176" in rows[4]["capacity"] and "1.188" in rows[4]["capacity"]
    assert "건조 1.000" in rows[7]["capacity"]


def test_money_cards(ctx):
    _, cd = ctx
    c = cd["design"]["money"]["cards"]
    assert c[0]["krw_eok"][0] < c[1]["krw_eok"][0]
    assert "78.0 pt" in c[0]["line"]


def test_for_fast_removal_drops_formation_capacity(ctx):
    _, cd = ctx
    r = next(x for x in cd["necessity"]["necessity"]["rows"] if x["lever_id"] == "FOR-FAST")
    assert abs(r["formation_cap_without"] - 1.0) < 1e-9
    assert "화성 처리능력(1.2배)" in r["axes_changed"] and "증산의 전제" in r["dual_role"]


def test_empty_conditions_not_accepted(ctx):
    v, _ = ctx
    rec, why = C.find_verification({**v, "kb_verifications": [{"candidate_id": "B1", "metric": "m", "value": 1.0, "conditions": {}}]},
                                   "B1", "m", {"solids": 0.65})
    assert rec is None and "조건 누락" in why
    rec, _ = C.find_verification({**v, "kb_verifications": [{"candidate_id": "B1", "metric": "m", "value": 1.0, "conditions": {"solids": 0.65}}]},
                                 "B1", "m", {"solids": 0.65})
    assert rec is not None


def test_switch_falls_back_to_b0(ctx):
    _, cd = ctx
    assert cd["switch"][0].startswith("B1 → B0")


def test_median_option_still_available(ctx):
    v, _ = ctx
    cd0 = C.evaluate({**v, "kb_effect_selection": {}, "_skip_design": True})
    assert abs(_sel(cd0)["saving"][1] - 0.35598) < 1e-4 and "design" not in cd0


def test_protocol_basis_text():
    v, _ = core.resolve_inputs(core.load_config())
    pb = design.compare({**v, "_skip_design": True}, options=[design.DEFAULT_OPTIONS[2]])["protocol_basis"]
    assert "EF-018" in pb and "3.9~4.2 V" in pb


def test_space_ledger(ctx):
    _, cd = ctx
    led = cd["roadmap"]["space"]["ledger"]
    assert [r["col"] for r in led] == ["필요 슬롯", "후보 슬롯", "제외 슬롯", "승인 슬롯"]
    assert "40분" in cd["roadmap"]["space"]["ledger_note"]
