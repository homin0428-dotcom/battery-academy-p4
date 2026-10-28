"""경제성·로드맵 - 레버별 연 절감액(한계 기여) · 손익분기 투자비 · 전개 일정(간트) · 로드맵 검사.

CAPEX 견적이 없으므로 '이 금액 이하면 3년/5년 안에 회수'라는 손익분기 투자비를 낸다(할인·정지 손실·OPEX 제외).
견적(capex_eok)이 들어오면 단순 회수기간을 계산한다. 전개 일정은 입력(rollout)이 없으면 변경 유형 기준 팀 가정.
"""
from __future__ import annotations

import evidence_engine as ee

# 변경 유형별 기본 일정(분기) - 팀 가정. 1분기 = 3개월, 1년차 = Q1~Q4
DEFAULT_SCHEDULE = {"운영변경": (1, 3, "파일럿 1라인 → 전 라인"), "설비개조": (4, 4, "1라인 개조 → 순차 확대"),
                    "설비교체": (8, 4, "노후 설비 교체 주기에 맞춰"), "공정전환": (12, 0, "3년 범위 밖")}


def lever_economics(values, ev_plant, nec, capex=None):
    """레버별 한계 기여 Δpt(제거 시 감소)를 연 전력·금액으로. 합계는 총액과 다를 수 있다(상호작용)."""
    q = values["q"]
    price = values.get("electricity_price_krw_per_kwh") or 100.0
    years = values.get("payback_years") or [3, 5]
    capex = capex or values.get("capex_eok") or {}
    rows = []
    for r in nec["rows"]:
        pt = r["delta_pp"] / 100 * (100 * q)            # %p → pt (기준 공장 100 대비)
        if ev_plant is None:
            krw = None
        else:
            krw = (pt / 100 * ev_plant["gwh_lo"] * 1e6 * price / 1e8, pt / 100 * ev_plant["gwh_hi"] * 1e6 * price / 1e8)
        cx = capex.get(r["lever_id"])
        payback = None
        if cx and krw and krw[0] > 0:
            payback = (cx[0] / krw[1], cx[1] / krw[0])        # 가장 짧은 ~ 가장 긴
        rows.append({"lever_id": r["lever_id"], "name": r["name"], "class": r["class"], "delta_pp": r["delta_pp"], "pt": pt,
                     "krw_eok": krw, "breakeven_eok": {n: (krw[0] * n, krw[1] * n) for n in years} if krw else None,
                     "capex_eok": cx, "payback_years": payback,
                     "status": ("견적 있음 - 단순 회수기간 계산" if payback else
                                "견적 없음 - 손익분기 투자비만" if pt > 1e-9 else "전력 기여 0 - 경제성 근거 없음(품질·처리능력 목적이면 별도 판단)")})
    rows.sort(key=lambda x: -x["pt"])
    return {"rows": rows, "price": price, "years": years,
            "note": "한계 기여 = 그 레버 하나를 뺄 때 줄어드는 절감(다른 레버 유지). 레버 간 상호작용 때문에 합계 ≠ 총액. "
                    "손익분기 투자비 = 연 절감 × 연수(할인·설치비·정지 손실·추가 OPEX 제외) - 견적이 아니라 상한 참고치."}


def rollout(values, clean, cand, nec):
    """레버별 전개 일정. 입력이 있으면 그대로, 없으면 변경 유형 기준 팀 가정."""
    contrib = {r["lever_id"]: r for r in nec["rows"]}
    given = values.get("rollout")
    rows = []
    if given:
        for g in given:
            rows.append({**g, "source": "입력"})
    else:
        for l in cand["levers"]:
            lv = ee._lever(clean, l)
            if lv["exclusive_group"] == "BASE":
                continue
            ct = lv.get("change_type") or "운영변경"
            st, du, scope = DEFAULT_SCHEDULE.get(ct, (1, 3, "-"))
            c = contrib.get(l, {})
            core = c.get("class", "").startswith(("핵심", "처리능력"))
            rows.append({"lever_id": l, "name": lv["name_ko"], "change_type": ct, "start_q": st, "duration_q": du, "scope": scope,
                         "downtime_days": None, "gate": "; ".join(f["quality_gate"][:40] for f in clean["fmea"]
                                                                  if f["lever_id"] == l and f.get("quality_gate"))[:120] or "-",
                         "target_pp": round(c.get("delta_pp", 0.0), 2) if core else None,
                         "role": "핵심" if core else "실측 후 편입 후보(목표 없음)", "source": "팀 가정(변경 유형 기준)"})
    rows.sort(key=lambda r: (r["start_q"], r["lever_id"]))
    # 로드맵 검사: 계산 기여 0 레버에 절감 목표가 붙어 있으면 경고
    warn = []
    for r in rows:
        c = contrib.get(r["lever_id"])
        if c and c["delta_pp"] < 1e-9 and (r.get("target_pp") or 0) > 0:
            warn.append(f"{r['lever_id']}: 계산 기여 0인데 절감 목표 {r['target_pp']}%p가 붙어 있음 - 목표 삭제 또는 upside로 이동")
        if r.get("downtime_days") is None:
            r["downtime_days_text"] = "미확인"
    return {"rows": rows, "warnings": warn, "quarters": 12,
            "note": "일정은 팀 가정(견적·공정 계획 없음). 정지일수는 미확인. 기여 0 레버는 목표 없이 '실측 후 편입'으로만 둔다."}


def analyze(values, run, clean, ev_plant, nec_block):
    sel = next((c for c in run["candidates"] if c["id"] == run["selected"]), None)
    nec = (nec_block or {}).get("necessity")
    if sel is None or not nec:
        return None
    return {"levers": lever_economics(values, ev_plant, nec), "rollout": rollout(values, clean, sel, nec)}
