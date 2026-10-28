"""처리능력 통합 - 공장 처리능력 = min(건조, 화성, 에이징), 병목 공정, 필요 최소값, 양품 분모, 연차별 생산비 q_t.

건조 = β / 면적당 용매비 (β = 실측 증발속도비, 없으면 1 '가정'. 실측 라인속도 상한이 있으면 그 값)
화성 = 채널비·가동률·수율 × 20 / (16 + 추가 점유)
에이징 = (1 + 승인 슬롯) × 계획 상한/현재 사용률 × 14 / 후보 기간  (승인 슬롯 미확인이면 무증설 값 + '미확인')
"""
from __future__ import annotations

import candidates as C


def _spec(values, cid):
    return next(s for s in (values.get("kb_candidates") or C.DEFAULT_CANDIDATES) if s["id"] == cid)


def _ax(c, p):
    return next(a for a in c["axes"] if a["axis"].startswith(p))


def process_capacity(values, cand, levers=None, slots_assumed=None):
    """levers를 주면 그 레버 집합(단계별 누적)으로 판단. slots_assumed: 승인 슬롯 미확인일 때 가정값(None = 0)."""
    levers = levers if levers is not None else cand["levers"]
    q = values["q"]
    dry = _ax(cand, "건조")
    mb = dry["mass_balance"]
    sa = mb["solvent_per_solid_ratio"] if "DRY-HSC" in levers else 1.0
    beta = values.get("drying_evap_rate_ratio_verified")
    if dry.get("verified_speed") is not None:
        cap_dry, dry_basis = dry["verified_speed"], "실측 속도 상한"
    else:
        cap_dry = (beta if beta is not None else 1.0) / sa
        dry_basis = "실측 증발속도비 β" if beta is not None else "β = 1 가정(증발속도 동일)"
    t = cand["cases"]["typical"]
    fh = values["formation_h"] if "FOR-FAST" in levers else values["baseline_formation_h"]
    c_, u, y = values["channel_ratio"], values["availability_ratio"], values["yield_ratio"]
    cap_for = c_ * u * y * values["baseline_formation_h"] / (fh + t["occupancy_h"])
    ag = _ax(cand, "에이징")
    d0 = values.get("aging_days") or 14
    appr = ag["approved"]
    if appr is not None:
        slot_state = "승인값"
    elif "AGE-RACK" not in levers and not ag.get("shorten"):
        appr, slot_state = 0.0, "랙 전환 전 - 무증설"
    elif slots_assumed:
        appr, slot_state = slots_assumed, "승인 슬롯 가정값(승인 시)"
    else:
        appr, slot_state = 0.0, "승인 슬롯 미확인 - 무증설 값"
    days = ag["days"]
    cap_age = (1 + appr) * values["planned_utilization"] / values["current_utilization"] * d0 / days
    caps = {"건조": cap_dry, "화성": cap_for, "에이징": cap_age}
    bott = min(caps, key=caps.get)
    plant = caps[bott]
    need_beta = q * sa
    need_uy = q * (fh + t["occupancy_h"]) / (values["baseline_formation_h"] * c_)
    return {"candidate": cand["id"], "caps": caps, "bases": {"건조": dry_basis, "화성": f"{fh:g} h + 추가 점유 {t['occupancy_h']:.2f} h",
                                                             "에이징": slot_state},
            "plant": plant, "bottleneck": bott, "margin": plant - q, "ok": plant >= q - 1e-9,
            "required": {"β(증발속도비)": need_beta, "가동률×수율": need_uy,
                         "가동률×수율(추가 15분)": q * (fh + t["occupancy_h"] + 0.25) / (values["baseline_formation_h"] * c_),
                         "승인 슬롯": ag["required_slot_gain"]},
            "note": "공장 처리능력은 가장 약한 공정으로 정해진다. 조립 등 다른 공정은 계산 범위 밖(동일 가정)."}


def yield_scenario(values, clean, eff, cand, y=0.95):
    """양품 출하 1.2배를 유지하려면 투입 부하는 q/y. 원단위 분모는 양품(q_good)."""
    spec = _spec(values, cand["id"])
    q = values["q"]
    v = {**values, "q": q / y, "q_good": q}
    c = C.evaluate_candidate(clean, eff, spec, cand["levers"], v)
    t = c["cases"]["typical"]
    return {"y": y, "q_good": q, "q_load": q / y, "E": t["E_total"], "saving": t["saving"], "ok": t["plant_ok"],
            "margin_pt": -t["gap"], "note": "수율 y는 별도 시나리오(기본 결과는 y = 1). 불량분만큼 설비 부하가 늘어난다."}


STAGE_OF = C.STAGE_OF


def stage_table(values, clean, eff, cand, nec=None):
    """v11.1 단계 누적에 ① 연차별 q_t(= min(1.2, 그 시점 처리능력)) ② 희석/개조 분리 ③ 레버 기여를 붙인다."""
    sp = C.stage_progress(values, clean, eff, cand)
    spec = _spec(values, cand["id"])
    contrib = {r["lever_id"]: r for r in (nec or {}).get("rows", [])}
    q = values["q"]
    out = []
    for st in sp["stages"]:
        lev = st["levers"]
        cs = C.evaluate_candidate(clean, eff, {**spec, "id": cand["id"]}, lev, values)
        cap = process_capacity(values, cs, lev, slots_assumed=None)
        cap_ok = process_capacity(values, cs, lev, slots_assumed=_ax(cs, "에이징")["required_slot_gain"]) if "AGE-RACK" in lev else cap
        q_t = min(q, cap["plant"])
        q_t_appr = min(q, cap_ok["plant"])
        res = {}
        for lab, qq in (("q_t", q_t), ("q_t_if_slots", q_t_appr), ("q_12", q)):
            c = C.evaluate_candidate(clean, eff, {**spec, "id": cand["id"]}, lev, {**values, "q": qq})
            B = C._B({**values, "q": qq})
            res[lab] = {"q": qq, "saving": c["saving"][1], "dilution_pp": (100 * qq - sum(B)) / (100 * qq) * 100,
                        "ok": c["cases"]["typical"]["plant_ok"]}
        out.append({"stage": st["stage"], "added": st["added"], "levers": lev, "capacity": cap["plant"], "bottleneck": cap["bottleneck"],
                    "q_t": q_t, "q_t_if_slots": q_t_appr, "at_q_t": res["q_t"], "at_q_if_slots": res["q_t_if_slots"], "at_q12": res["q_12"],
                    "contrib": [{"lever_id": l, "delta_pp": contrib[l]["delta_pp"], "class": contrib[l]["class"]}
                                for l in st["added"] if l in contrib],
                    "zero_contrib": [l for l in st["added"] if l in contrib and contrib[l]["delta_pp"] < 1e-9
                                     and not contrib[l]["class"].startswith(("핵심", "처리능력"))]})
    return {"candidate": cand["id"], "stages": out,
            "note": "q_t = 그 단계까지의 레버로 낼 수 있는 생산비(공장 처리능력, 1.2 상한). '12 GWh 도달 시'(q = 1.2) 열은 v11.1과 같다. "
                    "1년차에는 에이징 공간이 아직 없어 생산비가 묶이므로 고정부하 희석도 작다. 기여 0 레버에는 절감 목표를 붙이지 않는다."}


def analyze(values, run, clean, nec=None):
    sel = next((c for c in run["candidates"] if c["id"] == run["selected"]), None)
    if sel is None:
        return None
    eff = run["eff"]
    return {"plant": process_capacity(values, sel),
            "by_candidate": {c["id"]: process_capacity(values, c) for c in run["candidates"]},
            "yield": yield_scenario(values, clean, eff, sel), "stages": stage_table(values, clean, eff, sel, nec)}
