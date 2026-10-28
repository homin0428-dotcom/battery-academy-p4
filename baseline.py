"""기준선(베이스) 모듈 - 추천 후보의 절감률을 '고정부하 희석'과 '공정 개조'로 나누고, 기준선 가정을 흔들어 본다.

  decompose()     전부 비례 120 pt → 고정부하 희석 → 계통별 개조 절감 → 관리 전력 → E_new (pt와 %p 동시)
  sensitivity()   기준선 가정(f, 화성·에이징 분할, 기존 고형분, φ)을 하나씩 lo/hi로 바꿔 전체 후보 재계산 (토네이도)
  money_range()   공장 원단위 × 단가 격자의 연 절감액 (판정과 무관)
  baseline_card() 기준선 가정을 출제서 / 문헌 / 팀 가정 / 예시로 분류한 표
"""
from __future__ import annotations

import copy

import candidates as C
import kb_schema as S

DEFAULT_RANGES = {
    "f_all": {"label": "고정부하 비율 f (전 계통 배수)", "base": 1.0, "lo": 0.5, "hi": 1.25, "origin": "팀 가정"},
    "f_dryroom": {"label": "드라이룸 고정부하 f", "base": 0.8, "lo": 0.5, "hi": 1.0, "origin": "문헌 분류(R8 면적 비례·R23) · 수치 팀 가정"},
    "f_drying": {"label": "건조 고정부하 f", "base": 0.2, "lo": 0.1, "hi": 0.4, "origin": "팀 가정"},
    "split": {"label": "화성/에이징 분할(15% 중)", "base": [10, 5], "lo": [12, 3], "hi": [8, 7], "origin": "팀 가정(양산 사례 R26 10.56/4.44 → 35.75%)"},
    "solids_old": {"label": "기존 고형분 s0 (후보는 s0+Δ)", "base": 0.60, "lo": 0.50, "hi": 0.70, "origin": "문헌(R22 산업 50~60% · R27 40~70%)"},
    "phi": {"label": "용매 비례 부하 비중 φ", "base": 0.5, "lo": 0.3, "hi": 0.7, "origin": "가정 범위"},
}
MONEY_INTENSITY = [20, 30, 47, 50, 65]          # kWh/kWh_cell (20~47: 합산 문헌, 50~65: 전력 R12)
MONEY_PRICE = [168.17, 181.9]                   # 원/kWh (2024, 2025 산업용 평균)


def _sel(run):
    return next((c for c in run["candidates"] if c["id"] == run["selected"]), None)


def decompose(values, cand):
    """E_new = 전부 비례 기준(100q) - 고정부하 희석 - Σ계통 개조 절감 + 관리 전력. 합계 검산 포함."""
    q = values["q"]
    base = 100.0 * q
    B = C._B(values)
    t = cand["cases"]["typical"]
    dil = base - sum(B)
    steps = [{"item": "고정부하 희석(생산량이 늘어도 안 느는 부하)", "pt": dil, "kind": "희석"}]
    for j, s in enumerate(S.SYSTEMS):
        steps.append({"item": f"{s} 개조", "pt": B[j] * t["r"][j], "kind": "개조", "system": s})
    steps.append({"item": "관리 전력(FMEA 관리조치)", "pt": -t["p_add"], "kind": "부담"})
    for st in steps:
        st["pp"] = st["pt"] / base * 100          # 원단위 %p
    E = base - sum(st["pt"] for st in steps)
    saving = 1 - E / base
    tech = sum(st["pt"] for st in steps if st["kind"] == "개조")
    return {"candidate": cand["id"], "start_pt": base, "steps": steps, "E": E, "saving": saving,
            "dilution_pp": dil / base * 100, "tech_pp": tech / base * 100, "burden_pp": t["p_add"] / base * 100,
            "check": abs(E - t["E_total"]) < 1e-9 and abs(saving - t["saving"]) < 1e-12,
            "note": f"전부 비례({base:.0f} pt)에서 출발. 희석 {dil:.2f} pt는 고정부하 비율 f(팀 가정)에서 나오며 공정 개조 성과가 아니다."}


def _apply(values, key, val):
    v = copy.deepcopy(values)
    if key == "f_all":
        v["f"] = [min(1.0, x * val) for x in values["f"]]
    elif key == "f_dryroom":
        v["f"] = list(values["f"])
        v["f"][S.SYSTEMS.index("드라이룸")] = val
    elif key == "f_drying":
        v["f"] = list(values["f"])
        v["f"][S.SYSTEMS.index("건조")] = val
    elif key == "split":
        v["w"] = list(values["w"])
        v["w"][S.SYSTEMS.index("화성")], v["w"][S.SYSTEMS.index("에이징")] = val
    elif key == "solids_old":
        v["solids_old"] = val
    elif key == "phi":
        v["drying_solvent_load_share"] = [val, val, val]
    else:
        raise KeyError(key)
    return v


def sensitivity(values, clean, ranges=None, cand_id=None):
    """기준선 가정을 하나씩 lo/hi로 바꿔 전체 후보를 다시 계산 (다른 가정은 고정 - 단독 민감도)."""
    ranges = ranges or values.get("baseline_ranges") or DEFAULT_RANGES
    base_run = C.run_candidates(values, clean)
    cid = cand_id or base_run["selected"]
    b = next(c for c in base_run["candidates"] if c["id"] == cid)
    rows = []
    for key, r in ranges.items():
        out = {"key": key, "label": r["label"], "origin": r.get("origin", ""), "base": r.get("base")}
        for end in ("lo", "hi"):
            run = C.run_candidates(_apply(values, key, r[end]), clean)
            c = next(x for x in run["candidates"] if x["id"] == cid)
            out[end] = {"value": r[end], "saving": c["saving"][1], "margin_pt": c["margin_pt"], "label": c["label"],
                        "selected": run["selected"], "energy_state": c["axes"][0]["state"]}
        out["span_pp"] = abs(out["hi"]["saving"] - out["lo"]["saving"]) * 100
        out["flips"] = any(out[e]["energy_state"] != b["axes"][0]["state"] or out[e]["selected"] != cid for e in ("lo", "hi"))
        rows.append(out)
    rows.sort(key=lambda r: -r["span_pp"])
    return {"candidate": cid, "base_saving": b["saving"][1], "base_margin": b["margin_pt"], "rows": rows,
            "note": "한 번에 한 가정만 바꾼 단독 민감도. 고형분은 후보 규칙 s0+Δ로 함께 움직인다. "
                    "열원(가스·스팀)은 연속 범위가 아니라 이산 시나리오라 '열원 민감도' 표에 따로 있다."}


def money_range(values, cand):
    pt = cand["pt_saved"][1]
    cap = values.get("baseline_capacity_gwh") or 10.0
    rows = []
    for I in MONEY_INTENSITY:
        rows.append({"intensity": I, "annual_gwh": I * cap,
                     **{f"krw_eok_{p:g}": pt / 100 * I * cap * 1e6 * p / 1e8 for p in MONEY_PRICE}})
    return {"candidate": cand["id"], "pt_saved": pt, "rows": rows, "prices": MONEY_PRICE,
            "note": "연 절감액 = 감소 pt/100 × 현재 연간 전력(원단위 × 10 GWh) × 단가. 원단위·단가는 금액만 바꾸고 판정과 무관. "
                    "20~47은 열·전력 합산 문헌값이라 전력 금액으로는 하한 참고, 50~65가 전력 기준(R12)."}


LITERATURE_CASES = [
    {"key": "split_sun", "label": "화성/에이징 분할 10.56 / 4.44 (Sun 2020 양산 사례, R26)",
     "set": {"split": [10.56, 4.44]}, "source": "R26 (Jinasena 2021 Table 4 재인용)"},
    {"key": "split_sun_f0", "label": "분할 10.56 / 4.44 + 고정부하 f 전부 0 (최악)",
     "set": {"split": [10.56, 4.44], "f_all": 0.0}, "source": "R26 + 최악 가정"},
    {"key": "solids_55", "label": "기존 고형분 55% (목표 60%로 동반 이동)", "set": {"solids_old": 0.55}, "source": "R27 범위 안"},
    {"key": "solids_65", "label": "기존 고형분 65% (목표 70%로 동반 이동)", "set": {"solids_old": 0.65}, "source": "R27 범위 안"},
]


def literature_cases(values, clean, cases=None, cand_id=None):
    """조원 자료조사 값으로 입력만 바꿔 다시 계산. 대표값은 바꾸지 않고 '문헌 사례 적용 시' 한 줄로 쓴다."""
    base = C.run_candidates(values, clean)
    cid = cand_id or base["selected"]
    b = next(c for c in base["candidates"] if c["id"] == cid)
    rows = [{"key": "base", "label": "기준: 화성 10 / 에이징 5, f 팀 계수, 기존 고형분 60%", "source": "대표값",
             "saving": b["saving"][1], "margin_pt": b["margin_pt"], "selected": base["selected"], "energy_state": b["axes"][0]["state"]}]
    for case in cases or LITERATURE_CASES:
        v = values
        for k, val in case["set"].items():
            v = _apply(v, k, val)
        run = C.run_candidates(v, clean)
        c = next(x for x in run["candidates"] if x["id"] == cid)
        rows.append({"key": case["key"], "label": case["label"], "source": case["source"], "saving": c["saving"][1],
                     "margin_pt": c["margin_pt"], "selected": run["selected"], "energy_state": c["axes"][0]["state"]})
    return {"candidate": cid, "rows": rows,
            "note": "코드 그대로, 입력만 변경(공식 설계 고정 근거 그대로). 근거가 사례 1건이라 대표값은 그대로 두고 가정 카드에 '문헌 사례 분할 적용 시' 한 줄로 쓴다."}


def baseline_card(values):
    w, f = values["w"], values["f"]
    return [
        {"item": "계통 전력 비중 35/25/15/25", "value": "건조 35 · 드라이룸 25 · 화성·에이징 15 · 기타 25", "origin": "출제서", "source": "S0"},
        {"item": "생산량비 q, 목표 원단위", "value": f"{values['q']:g}배, {values['target_intensity_ratio']:g}", "origin": "출제서", "source": "S0"},
        {"item": "화성 10 / 에이징 5 분할", "value": f"{w[2]:g} / {w[3]:g}", "origin": "팀 가정(양산 사례와 모순 없음)",
         "source": "R26 Sun 2020: 화성 단독 10.56%(열 포함 총에너지 기준 - C사 전력 비중과 기준 다름). 10.56/4.44 → 35.75%"},
        {"item": "고정부하 비율 f", "value": " · ".join(f"{s} {x:g}" for s, x in zip(S.SYSTEMS, f)), "origin": "분류는 문헌 · 숫자는 팀 계수",
         "source": "R8 Lechner 2025 Table 2: 드라이룸·클린룸 면적당 상시 동력(24 h·365일) · R23 드라이룸 HVAC 처리량 무관 · "
                   "R1 Degen: 설비 전력∝처리량 · R24 조건 다름"},
        {"item": "기존 고형분 s0", "value": f"{C.solids_old(values):.2f}", "origin": "문헌 범위 안 대표값",
         "source": "R22 Reynolds 2022: 산업 양극 60 wt%(50~60%) · R27 Bryntesen 2023: 용매 대 분말 30~60%. C사 값 미공개"},
        {"item": "목표 고형분 s0 + 0.05", "value": f"{C.solids_old(values) + 0.05:.2f}", "origin": "문헌",
         "source": "R28 Lu 2023(Ouyang 2020 인용): 코팅 권장 64~66% · R18 Liu: 75%는 기존 슬롯다이 불가. 64.29% 미만이면 건조 처리능력 미성립"},
        {"item": "용매 비례 부하 비중 φ", "value": "/".join(f"{x:g}" for x in C.phi_range(values)), "origin": "가정 범위", "source": "구간 전력 계측 필요"},
        {"item": "슬롯 사용률 현재/상한", "value": f"{values['current_utilization']:g} / {values['planned_utilization']:g}", "origin": "팀 가정",
         "source": "보관 랙 통상 운영 여유. 승인 슬롯 +13.68%가 여기서 나옴"},
        {"item": "화성 16 h", "value": f"{values['formation_h']:g} h", "origin": "목표 사양(파일럿 후 적용)", "source": "문헌 시간비 범위 안(R2·R3·R9)"},
        {"item": "공장 전력 원단위", "value": "50~65 kWh/kWh_cell", "origin": "문헌", "source": "R12 Davidsson Kurland 2020"},
        {"item": "전기 단가", "value": f"{values.get('electricity_price_krw_per_kwh') or 100:g} 원/kWh", "origin": "통계", "source": "KEPCO 2025 산업용 평균"},
        {"item": "건조·드라이룸 열원", "value": "전기", "origin": "해석(미확인)", "source": "출제서가 '전력' 비중으로 제시 → 전기 가열로 해석. 열원 민감도 별도"},
    ]


def analyze(values, run, clean):
    cand = _sel(run)
    if cand is None:
        return None
    return {"waterfall": decompose(values, cand), "sensitivity": sensitivity(values, clean, cand_id=cand["id"]),
            "money": money_range(values, cand), "card": baseline_card(values),
            "literature_cases": literature_cases(values, clean, cand_id=cand["id"])}
