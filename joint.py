"""동시 불확실성 - 문헌 효과 전이율 α와 미정량 관리 전력 P가 함께 나빠질 때의 성립 영역, 스트레스 시나리오.

실패 경계표(78%, 6.72 pt)는 다른 입력을 고정한 '단독 경계'다. 여기서는 두 입력을 동시에 바꾼다.
E(α, P) = a - b·α + P 는 α·P에 선형(건조 잔여부하 곱 포함)이므로 닫힌식 P_max(α) = 목표 - a + b·α 를 함께 낸다.
"""
from __future__ import annotations

import candidates as C
import evidence_engine as ee

A_GRID = [round(0.60 + 0.01 * i, 2) for i in range(51)]     # 0.60 ~ 1.10
P_GRID = [round(0.1 * i, 1) for i in range(101)]             # 0 ~ 10 pt


def _spec(values, cid):
    return next(s for s in (values.get("kb_candidates") or C.DEFAULT_CANDIDATES) if s["id"] == cid)


def _E(clean, eff, spec, lev, values, alpha, P=0.0):
    v = {**values, "kb_extra_burden_pt": (values.get("kb_extra_burden_pt") or 0.0) + P}
    return C.evaluate_candidate(clean, eff, spec, lev, v, alpha)["cases"]["typical"]["E_total"]


def region(values, clean, eff, cand):
    spec = _spec(values, cand["id"])
    lev = cand["levers"]
    tgt = 100.0 * values["q"] * values["target_intensity_ratio"]
    a = _E(clean, eff, spec, lev, values, 0.0)
    b = a - _E(clean, eff, spec, lev, values, 1.0)
    pmax = lambda al: tgt - a + b * al
    # 닫힌식과 직접 계산 일치 검사 (몇 점)
    checks = [abs(_E(clean, eff, spec, lev, values, al, P) - (a - b * al + P)) < 1e-9 for al, P in ((0.7, 1.0), (0.9, 4.0), (1.1, 0.0))]
    grid = [[(a - b * al + P) <= tgt + 1e-9 for P in P_GRID] for al in A_GRID]
    alpha_star = (a - tgt) / b if b else None
    return {"candidate": cand["id"], "a": a, "b": b, "target": tgt, "formula": f"E(α, P) = {a:.2f} - {b:.2f}·α + P",
            "alpha_star": alpha_star, "p_max": {al: pmax(al) for al in (1.0, 0.95, 0.9, 0.85, 0.8)},
            "alpha_grid": A_GRID, "p_grid": P_GRID, "ok_grid": grid, "closed_form_ok": all(checks),
            "note": "α = 문헌 절감 효과가 C사에서 재현되는 비율(1 = 대표값 그대로), P = 아직 정량화 안 된 관리 전력(pt). "
                    "단독 경계는 다른 하나를 고정한 값이라 둘이 함께 나빠지면 더 일찍 미달한다."}


STRESS = [
    ("S1", "문헌 효과 90% + 관리 전력 4 pt", {"alpha": 0.9, "P": 4.0}),
    ("S2", "문헌 효과 80% + 관리 전력 2 pt", {"alpha": 0.8, "P": 2.0}),
    ("S3", "고정부하 f 전부 0 (전부 비례)", {"f0": True}),
    ("S4", "f 전부 0 + 문헌 효과 95%", {"f0": True, "alpha": 0.95}),
    ("S5", "드라이룸 재생열 가스·스팀", {"heat": {"드라이룸": False}}),
]


def stress(values, clean, cand):
    spec = _spec(values, cand["id"])
    rows = []
    for sid, lab, o in STRESS:
        v = dict(values)
        if o.get("f0"):
            v["f"] = [0.0] * len(values["f"])
        if o.get("P"):
            v["kb_extra_burden_pt"] = (values.get("kb_extra_burden_pt") or 0.0) + o["P"]
        if o.get("heat"):
            v["kb_electric_heating"] = {**ee.DEFAULT_ELECTRIC_HEATING, **(values.get("kb_electric_heating") or {}), **o["heat"]}
        eff = ee.classify_effects(clean, v["w"], {**ee.DEFAULT_ELECTRIC_HEATING, **(v.get("kb_electric_heating") or {})},
                                  bool(v.get("kb_allow_cross_share")), ee.plant_basis(clean, v))
        eff = ee.apply_effect_selection(eff, v.get("kb_effect_selection"))
        c = C.evaluate_candidate(clean, eff, spec, cand["levers"], v, o.get("alpha", 1.0))
        t = c["cases"]["typical"]
        rows.append({"id": sid, "scenario": lab, "saving": t["saving"], "E": t["E_total"], "margin_pt": -t["gap"],
                     "ok": t["plant_ok"], "verdict": "충족" if t["plant_ok"] else "미달"})
    return {"candidate": cand["id"], "rows": rows,
            "note": "결정적 스트레스 시나리오(확률 아님). 하나라도 미달이면 '보수에서도 충족'이라고 쓰지 않는다."}


def analyze(values, run, clean):
    sel = next((c for c in run["candidates"] if c["id"] == run["selected"]), None)
    if sel is None:
        return None
    return {"region": region(values, clean, run["eff"], sel), "stress": stress(values, clean, sel)}
