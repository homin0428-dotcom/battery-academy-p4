"""v12.2 설계 고정 - '근거를 설계에 맞추면' (조원 v12.1 두 검토서 통합 제안 반영).

  compare()       기술군 중앙값 / D1 / D2 를 같은 엔진·같은 기준선으로 재계산한 비교표 (방어 문장이 설계에 따라 깨지는지)
  signal_table()  같은 조건에서 전력 -30%와 생산능력 +20%를 함께 판정하는 두 목표 신호등 표
  money_cards()   '현재 전기요금 대비'와 '같은 증산의 무개선 대비' 두 기준의 연 금액
  design_spec()   기본 설계서 1장 (설계 고정 내용 · 계산 근거 · 시기 · 통과 기준)

공식 결과는 configs의 kb_effect_selection(팀이 고른 설계)로 계산된다. 이 모듈은 판정을 바꾸지 않는다.
"""
from __future__ import annotations

import candidates as C

DEFAULT_OPTIONS = [
    {"key": "median", "label": "기술군 중앙값(v12.1까지)", "selection": {}},
    {"key": "D1", "label": "D1 부분 국소화 + 고율 화성 + NIR",
     "selection": {"DRM-LOCAL": ["EF-003"], "FOR-FAST": ["EF-017"], "DRY-RAD": ["EF-006"]}},
    {"key": "D2", "label": "D2 부분 국소화 + 부분 사이클 화성 + NIR",
     "selection": {"DRM-LOCAL": ["EF-003"], "FOR-FAST": ["EF-018"], "DRY-RAD": ["EF-006"]}},
]
INTENSITY = (50, 65)         # kWh/kWh_cell (R12) → 현재 연 전력 500~650 GWh


def _sel(cd):
    return next((c for c in cd["candidates"] if c["id"] == cd["selected"]), None)


def _stress(cd, sid):
    return next((r for r in ((cd.get("joint") or {}).get("stress") or {}).get("rows", []) if r["id"] == sid), None)


def _heat(cd, case_prefix):
    sel = cd["selected"]
    return next((r for r in (cd.get("heat") or {}).get("rows", []) if r["candidate"] == sel and r["case"].startswith(case_prefix)), None)


def _money(values, E, E_ref):
    price = values.get("electricity_price_krw_per_kwh") or 181.9
    cap = values.get("baseline_capacity_gwh") or 10.0
    return [(E_ref - E) / 100 * I * cap * 1e6 * price / 1e8 for I in INTENSITY]


def summarize(values, cd):
    s = _sel(cd)
    t = s["cases"]["typical"]
    st = ((cd.get("capacity") or {}).get("stages") or {}).get("stages") or []
    y2 = st[1] if len(st) > 1 else None
    s1, s3 = _stress(cd, "S1"), _stress(cd, "S3")
    dr, dy = _heat(cd, "드라이룸"), _heat(cd, "건조")
    E0 = cd["baseline"]["E_q_no_change"]
    return {"candidate": s["id"], "saving": s["saving"], "margin_pt": s["margin_pt"], "E": s["E_typ"],
            "alpha_star": (cd.get("joint") or {}).get("region", {}).get("alpha_star"),
            "s1": s1 and s1["saving"], "f0": s3 and s3["saving"],
            "y2_no_slot": y2 and y2["at_q_t"]["saving"], "dryroom_gas": dr and dr["saving"][1], "drying_gas": dy and dy["saving"][1],
            "money_now": _money(values, s["E_typ"], 100.0), "money_nochange": _money(values, s["E_typ"], E0),
            "tech_pp": ((cd.get("baseline_model") or {}).get("waterfall") or {}).get("tech_pp"),
            "occupancy_h": t["occupancy_h"]}


def compare(values, options=None, official=None):
    options = options or values.get("kb_design_options") or DEFAULT_OPTIONS
    official = values.get("kb_effect_selection") or {}
    target = 1 - values["target_intensity_ratio"]
    rows = []
    for o in options:
        cd = C.evaluate({**values, "kb_effect_selection": o["selection"], "_skip_design": True})
        r = summarize(values, cd)
        rows.append({"key": o["key"], "label": o["label"], "selection": o["selection"],
                     "official": o["selection"] == official, **r})
    ok = lambda x: None if x is None else x >= target - 1e-12
    for r in rows:
        r["ok"] = {k: ok(r[k]) for k in ("s1", "f0", "y2_no_slot", "dryroom_gas", "drying_gas")}
        r["ok"]["base"] = ok(r["saving"][1])
    return {"rows": rows, "target": target,
            "note": "같은 엔진·같은 기준선에서 레버별 근거만 설계에 맞춰 고른 값. 근거를 하나씩만 쓰면 보수~낙관 범위가 좁아지는데, "
                    "불확실성이 줄어서가 아니라 근거가 하나라서다 - 불확실성은 α–P 영역과 스트레스 표로 본다.",
            "protocol_basis": ("화성 시간 근거 Weng 2021(R3)의 고속 화성 = Wood 등(R2) 프로토콜: 1C로 3.9 V까지 충전 후 "
                               "3.9~4.2 V 사이 C/5 부분 사이클 5회(R3 보충자료 Fast formation protocol). 상단 SOC 부분 사이클을 포함하므로 "
                               "Degen Table 1의 '부분 사이클 적응형 화성'(EF-018)에 대응시킨다(D2). 다만 Weng 프로토콜은 셀 상태에 따라 "
                               "조정하는 '적응형' 제어가 아니므로 '고율 화성'(EF-017, D1)을 보수 설계로 함께 보인다.")}


def signal_table(values, cd, clean):
    """같은 조건에서 두 목표를 함께 판정. 수율 행은 단순 모델(전 공정 동일 상대 수율)."""
    s = _sel(cd)
    q = values["q"]
    target = 1 - values["target_intensity_ratio"]
    cp = (cd.get("capacity") or {}).get("plant") or {}
    caps = dict(cp.get("caps") or {})
    cu, pu = values["current_utilization"], values["planned_utilization"]
    ag = next(a for a in s["axes"] if a["axis"].startswith("에이징"))
    need = ag["required_slot_gain"]
    age_cap = lambda g: (1 + g) * pu / cu
    st = ((cd.get("capacity") or {}).get("stages") or {}).get("stages") or []
    y2 = st[1] if len(st) > 1 else None
    fh, fh0 = values["formation_h"], values["baseline_formation_h"]
    c_, u, yy = values["channel_ratio"], values["availability_ratio"], values["yield_ratio"]
    occ40 = 40 / 60
    cap_for40 = c_ * u * yy * fh0 / (fh + s["cases"]["typical"]["occupancy_h"] + occ40)
    yl = (cd.get("capacity") or {}).get("yield") or {}
    y = yl.get("y", 0.95)
    s1, dr = _stress(cd, "S1"), _heat(cd, "드라이룸")
    # 기존 고형분이 이미 65%(목표 65% 고정): B1 고형분 레버가 무효
    spec = dict(next(x for x in (values.get("kb_candidates") or C.DEFAULT_CANDIDATES) if x["id"] == s["id"]))
    spec["solids"] = 0.65
    spec.pop("solids_rule", None)
    v65 = {**values, "solids_old": 0.65}
    run65 = C.run_candidates(v65, clean, specs=[spec])
    c65 = next(x for x in run65["candidates"] if x["id"] == s["id"])
    b0 = next((x for x in cd["candidates"] if x["id"] == "B0"), None)
    pw = lambda x: f"{x * 100:.1f}% " + ("충족" if x >= target - 1e-12 else "미달")
    cp_txt = lambda d: f"{min(d.values()):.3f} (" + " · ".join(f"{k} {v:.3f}" for k, v in d.items()) + ") " + \
        ("충족" if min(d.values()) >= q - 1e-9 else "미달")
    base_caps = {**caps, "에이징": age_cap(need)}
    rows = [
        {"cond": f"기본 설계 + 승인 슬롯 +{need * 100:.2f}%", "power": pw(s["saving"][1]), "capacity": cp_txt(base_caps), "overall": "조건부 추천"},
        {"cond": "같은 설계, 에이징 공간 미확보", "power": pw(y2["at_q_t"]["saving"]) if y2 else "-",
         "capacity": f"{cp.get('plant', 0):.3f} (병목 {cp.get('bottleneck')}) 미달",
         "overall": "전력만 충족" if y2 and y2["at_q_t"]["saving"] >= target else "둘 다 미달 - 공간이 두 목표의 공통 열쇠"},
        {"cond": "승인 슬롯 +6%", "power": pw(s["saving"][1]), "capacity": f"에이징 {age_cap(0.06):.3f} 미달 → C안(13일 + 조기 선별)",
         "overall": "C 검토"},
        {"cond": "화성 검사 추가 점유 40분", "power": pw(s["saving"][1]),
         "capacity": f"화성 {cap_for40:.3f} (여유 {cap_for40 - q:+.3f}), 화성 랙 여유 {(1 - q * (fh + occ40) / fh0) * 100:.0f}%로 소멸",
         "overall": "경계"},
        {"cond": f"양품 수율 {y:g} (단순 모델)", "power": (f"{yl['saving'] * 100:.1f}% 통과" if yl.get("ok") else f"{yl.get('saving', 0) * 100:.1f}% 미달"),
         "capacity": f"양품 기준 건조 {caps.get('건조', 0) * y:.3f} · 화성 {caps.get('화성', 0) * y:.3f} 미달",
         "overall": "생산 미달 - 전력 통과 ≠ 종합 통과"},
        {"cond": "문헌 효과 90% + 관리 전력 4 pt", "power": pw(s1["saving"]) if s1 else "-", "capacity": "변화 없음",
         "overall": "전력 미달" if s1 and s1["saving"] < target else "충족"},
        {"cond": "드라이룸 재생 가스·스팀", "power": pw(dr["saving"][1]) if dr else "-", "capacity": "변화 없음",
         "overall": "전력 미달" if dr and dr["saving"][1] < target else "충족"},
        {"cond": "기존 고형분이 이미 65% (목표 65% 고정)", "power": pw(c65["saving"][1]) + (" (B0와 같은 값)" if b0 and abs(b0["saving"][1] - c65["saving"][1]) < 5e-4 else ""),
         "capacity": f"건조 {1 / c65['mass_balance']['solvent_per_solid_ratio']:.3f} 미달", "overall": "고형분 레버 무효 - 기존 고형분 확인이 증산의 전제"},
    ]
    return {"candidate": s["id"], "rows": rows,
            "note": "수율 행은 전 공정 동일 상대 수율의 단순 모델이며 '수율이 생산능력의 숨은 변수'라는 메시지로만 쓴다. "
                    "평균 처리능력이 1.2배를 넘어도 대기열 소멸이 보장되지는 않는다(변동·고장)."}


def money_cards(values, cd):
    s = _sel(cd)
    E0 = cd["baseline"]["E_q_no_change"]
    now, nc = _money(values, s["E_typ"], 100.0), _money(values, s["E_typ"], E0)
    return {"cards": [
        {"title": "현재 전기요금 대비", "krw_eok": now, "line": f"생산을 20% 늘리고도 공장 전기요금 총액이 지금보다 줄어든다 (총전력 100 → {s['E_typ']:.1f} pt)"},
        {"title": "같은 증산의 무개선 대비", "krw_eok": nc, "line": f"개선 투자로 피하는 전력비 ({E0:.1f} → {s['E_typ']:.1f} pt) - 손익분기 투자비의 기준"}],
        "note": f"현재 연 전력 = 문헌 원단위 {INTENSITY[0]}~{INTENSITY[1]} kWh/kWh셀(R12) × 10 GWh, 단가 {values.get('electricity_price_krw_per_kwh') or 181.9:g}원/kWh. "
                "원단위 20~47이면 비례해서 줄어든다. 순이익 아님(투자비·정지손실·운영비 제외)."}


def design_spec(values, sel_map):
    fh = values["formation_h"]
    pick = lambda l: ", ".join(sel_map.get(l) or ["전체 근거 중앙값"])
    return [
        {"lever": "고형분", "design": "60 → 65 wt% (NMC/PVDF/NMP, 같은 로딩)", "basis": "질량수지 + R22·R28·R18", "when": "단기",
         "pass": "점도·토출·잔류 NMP·접착 동등, 64.29% 이상"},
        {"lever": "NIR 복사건조", "design": "오븐 앞 정률 구간 부스터, 열풍 유지", "basis": f"{pick('DRY-RAD')} (Degen NIR)", "when": "중기",
         "pass": "구간 kWh/m² 실측, 재현율 α 영역 안, 점화원 관문"},
        {"lever": "드라이룸 부분 국소화", "design": "주액~밀봉 구간 미니환경, 나머지 공조 완화", "basis": f"{pick('DRM-LOCAL')} (Lechner 부분)", "when": "중기",
         "pass": "노출 구역 -40°C 이하, 전환 로트 품질 동등"},
        {"lever": "화성 프로토콜", "design": f"Weng 2021 계열 고속 화성 {fh:g} h (1C → 3.9 V, 3.9~4.2 V 부분 사이클)",
         "basis": f"시간 EF-019 / 전력 {pick('FOR-FAST')}", "when": "단기(파일럿 후)", "pass": "수명·초기효율 비열등, 추가 점유 40분 이내"},
        {"lever": "에이징 공간", "design": "14일 유지, 승인 순 슬롯 +13.68%", "basis": "공간 장부 + FM Global DS 7-112", "when": "중기", "pass": "방재 승인 순 슬롯"},
    ]


def analyze(values, cd, clean):
    if _sel(cd) is None:
        return None
    return {"compare": compare(values), "signal": signal_table(values, cd, clean), "money": money_cards(values, cd),
            "spec": design_spec(values, values.get("kb_effect_selection") or {}),
            "official_selection": values.get("kb_effect_selection") or {}}
