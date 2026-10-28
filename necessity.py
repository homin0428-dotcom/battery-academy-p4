"""후보 재구성 분석 - 레버 필요성 · B2 요구 성능 역산 · 건조 구조 가정(M1/M2/M3).

'B1의 레버가 다 필요한가', 'B1에 고형분이 왜 필요한가', 'B2는 왜 지는가'에 계산으로 답한다.
근거 없는 레버는 삭제하지 않고 '계산 기여 0 - 1년차 실측 후 편입 후보'로 분류한다.
"""
from __future__ import annotations

import candidates as C
import evidence_engine as ee


def _spec(values, cid):
    specs = values.get("kb_candidates") or C.DEFAULT_CANDIDATES
    return next(s for s in specs if s["id"] == cid)


def _ax(c, prefix):
    return next(a for a in c["axes"] if a["axis"].startswith(prefix))


def lever_necessity(values, clean, eff, cand):
    spec = dict(_spec(values, cand["id"]))
    base_dry = _ax(cand, "건조")
    rows = []
    for l in cand["levers"]:
        lv = ee._lever(clean, l)
        if lv["exclusive_group"] == "BASE":
            continue
        rest = [x for x in cand["levers"] if x != l]
        c2 = C.evaluate_candidate(clean, eff, spec, rest, values)
        d = (cand["saving"][1] - c2["saving"][1]) * 100
        changed = [a["axis"] for a, b in zip(cand["axes"], c2["axes"]) if a["state"] != b["state"]]
        d2 = _ax(c2, "건조")
        dry_basis = base_dry["calc_ok"] != d2["calc_ok"]
        has_ev = ee.lever_saving(eff, l) is not None or l == "DRY-HSC"
        if d >= 1.0 - 1e-9 or "전력 원단위(-30%)" in changed:
            cls = "핵심"
        elif dry_basis or changed:
            cls = "처리능력 기여"
        elif lv["system"] == "에이징":
            cls = "처리능력 기여(에이징 공간·기간 확보 수단 - 승인 슬롯으로 판정)"
        elif not has_ev:
            cls = "계산 기여 0 - 근거 미확보(1년차 실측 후 편입 후보)"
        else:
            cls = "계산 기여 0"
        rows.append({"lever_id": l, "name": lv["name_ko"], "system": lv["system"], "change_type": lv.get("change_type") or "-",
                     "delta_pp": d, "label_without": c2["label"], "axes_changed": changed + (["건조 근거(질량수지→D등급)"] if dry_basis else []),
                     "gates_delta": cand["n_gates"] - c2["n_gates"], "class": cls,
                     "formation_cap_without": c2["cases"]["typical"]["capacity"],
                     "dual_role": (f"전력 -{d:.2f}%p + 증산의 전제(화성 처리능력 {c2['cases']['typical']['capacity']:.2f} → "
                                   f"{cand['cases']['typical']['capacity']:.2f}배)") if l == "FOR-FAST" else None,
                     "quality_function": lv["exclusive_group"] == "FOR-QC"})
    rows.sort(key=lambda r: (-r["delta_pp"], r["lever_id"]))
    core_lev = [r["lever_id"] for r in rows if r["class"] == "핵심" or r["class"].startswith("처리능력 기여")]
    core_lev += [l for l in cand["levers"] if ee._lever(clean, l)["exclusive_group"] == "BASE"]
    cc = C.evaluate_candidate(clean, eff, spec, core_lev, values)
    return {"candidate": cand["id"], "rows": rows,
            "core": {"levers": core_lev, "saving": cc["saving"], "margin_pt": cc["margin_pt"], "n_gates": cc["n_gates"],
                     "n_safety_gates": cc["n_safety_gates"], "label": cc["label"]},
            "full": {"saving": cand["saving"], "n_gates": cand["n_gates"], "n_safety_gates": cand["n_safety_gates"]},
            "note": "레버 하나씩 뺀 한계 기여(다른 레버 유지). 합계가 총 절감과 다를 수 있다. 기여 0 레버는 근거가 없어 0으로 계산된 것이며 "
                    "효과가 없다는 뜻이 아니다 - 1년차 실측으로 근거를 만들면 편입. 품질 기능 레버(예: 화성 데이터 판정)는 전력 기여와 무관하게 유지 가능."}


def b2_required(values, clean, eff, run):
    """B2가 목표에 닿으려면 배기열 회수가 '고형분 후 남은 건조 부하'를 얼마나 줄여야 하는가."""
    import core
    b2 = next((c for c in run["candidates"] if c["id"] == "B2"), None)
    if b2 is None:
        return None
    t = b2["cases"]["typical"]
    pt = t["plant"]
    j = C.DI
    r_req = core.required_reduction(sum(pt["E"]) - pt["E"][j], pt["P_add"], pt["target_energy"], pt["B"][j])
    rho = b2["drying_residual"]["typical"] if b2["drying_residual"] else 1.0
    h_req = 1 - (1 - r_req) / rho
    hx = ee.lever_saving(eff, "DRY-HX")
    return {"r_dry_required": r_req, "rho": rho, "hx_required": h_req,
            "hx_evidence": None if hx is None else hx["typ"],
            "text": (f"배기열 회수(DRY-HX)는 계통 기준 근거가 없어 0으로 계산(하한). 목표 도달에는 고형분 후 남은 건조 부하의 "
                     f"{h_req * 100:.1f}% 이상을 추가로 줄여야 함 (건조 계통 전체 {r_req * 100:.1f}%)")}


def structure(values, clean, eff, cand, hs=(1.0, 0.8, 0.7, 0.6, 0.5)):
    """건조 구조 가정. M1=현행(잔여부하 × 건조 레버 효과) / M2=건조 레버 효과가 열 관련 비중 h에만 / M3=고형분 전력 효과 0."""
    if "DRY-HSC" not in cand["levers"]:
        return None
    spec = _spec(values, cand["id"])

    def run_mode(mode, h=1.0):
        return C.evaluate_candidate(clean, eff, spec, cand["levers"], {**values, "drying_structure": {"mode": mode, "h": h}})

    m2 = [{"h": h, "saving": run_mode("M2", h)["saving"][1], "ok": run_mode("M2", h)["cases"]["typical"]["plant_ok"]} for h in hs]
    lo, hi = 0.0, 1.0
    if run_mode("M2", 1.0)["cases"]["typical"]["plant_ok"] and not run_mode("M2", 0.0)["cases"]["typical"]["plant_ok"]:
        for _ in range(60):
            mid = (lo + hi) / 2
            if run_mode("M2", mid)["cases"]["typical"]["plant_ok"]:
                hi = mid
            else:
                lo = mid
        h_star = hi
    else:
        h_star = None
    m3 = run_mode("M3")
    return {"candidate": cand["id"], "M1": cand["saving"][1], "M2": m2, "h_star": h_star, "M3": m3["saving"][1],
            "M3_label": m3["label"],
            "note": "M2의 h는 건조 계통 전력 중 복사·열회수 같은 '가열 기술'이 줄일 수 있는 열 관련 비중(팬·대기 등 제외). "
                    f"h가 {h_star:.3f} 아래면 전력 목표 미달." if h_star else "M2 전 범위에서 판정 불변."}


def analyze(values, run, clean):
    eff = run["eff"]
    sel = next((c for c in run["candidates"] if c["id"] == run["selected"]), None)
    if sel is None:
        return None
    return {"necessity": lever_necessity(values, clean, eff, sel), "b2": b2_required(values, clean, eff, run),
            "structure": structure(values, clean, eff, sel)}
