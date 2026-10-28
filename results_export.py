"""숫자의 원본을 하나로 - results.json 생성 + results.json ↔ CSV ↔ PDF 숫자 일치 검사.

보고서·PPT·브리핑은 results.json의 숫자만 옮겨 쓴다. 일치 검사가 실패하면 run.py 종료코드 1.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

VERSION = "v12.2"


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items() if k not in ("clean", "eff")}
    if isinstance(o, (list, tuple)):
        return [_clean(x) for x in o]
    if isinstance(o, float):
        return round(o, 6)
    return o


def build(res):
    ev = res["evidence"]
    cd = ev["candidates"]
    sel = next(c for c in cd["candidates"] if c["id"] == cd["selected"])
    bl = cd.get("baseline_model") or {}
    wf = bl.get("waterfall") or {}
    jt = cd.get("joint") or {}
    cp = cd.get("capacity") or {}
    nc = cd.get("necessity") or {}
    up = cd.get("upside") or {}
    rm = cd.get("roadmap") if isinstance(cd.get("roadmap"), dict) and "error" not in cd.get("roadmap") else {}
    dz = cd.get("design") if isinstance(cd.get("design"), dict) and "error" not in cd.get("design") else {}
    head = {"candidate": sel["id"], "name": sel["name"], "status": cd["status"], "label": sel["label"],
            "saving": {"conservative": sel["saving"][0], "typical": sel["saving"][1], "optimistic": sel["saving"][2]},
            "E_pt": sel["E_typ"], "margin_pt": sel["margin_pt"], "target_pt": cd["baseline"]["target"],
            "baseline_no_change_pt": cd["baseline"]["E_q_no_change"],
            "tech_pp": wf.get("tech_pp"), "dilution_pp": wf.get("dilution_pp"),
            "annual_krw_eok": sel["money_typ"]["krw_eok"] if sel["money_typ"] else None,
            "unconfirmed": [a["axis"] for a in sel["axes"] if a["state"] == "미확인"],
            "plant_capacity": (cp.get("plant") or {}).get("plant"), "bottleneck": (cp.get("plant") or {}).get("bottleneck"),
            "design_selection": dz.get("official_selection"),
            "money_vs_now_krw_eok": ((dz.get("money") or {}).get("cards") or [{}])[0].get("krw_eok"),
            "aging_slot_need": (rm.get("space") or {}).get("slot_need"), "aging_area_upper": (rm.get("space") or {}).get("area_upper")}
    out = {"version": VERSION, "scenario": res["scenario"], "config_hash": res["config_hash"], "official_candidate": sel["id"],
           "headline": head,
           "candidates": [{"id": c["id"], "name": c["name"], "role": c["role"], "eligible": c["eligible"], "why_not": c["why_not"],
                           "levers": c["levers"], "solids": c["solids"], "saving": c["saving"], "E_pt": c["E_typ"],
                           "margin_pt": c["margin_pt"], "annual_krw_eok": c["money_typ"]["krw_eok"] if c["money_typ"] else None,
                           "axes": {a["axis"]: a["state"] for a in c["axes"]}, "label": c["label"],
                           "gates": c["n_gates"], "safety_gates": c["n_safety_gates"]} for c in cd["candidates"]],
           "waterfall": wf, "sensitivity": (bl.get("sensitivity") or {}).get("rows"), "money_range": bl.get("money"),
           "baseline_card": bl.get("card"), "literature_cases": (bl.get("literature_cases") or {}).get("rows"),
           "space_plan": rm.get("space"), "reach": rm.get("reach"), "horizon": rm.get("horizon"), "impact_matrix": rm.get("impact"),
           "capacity_kpi": rm.get("kpi"), "design_compare": dz.get("compare"), "signal_table": dz.get("signal"),
           "money_cards": dz.get("money"), "design_spec": dz.get("spec"), "departments": rm.get("departments"),
           "joint": {k: v for k, v in (jt.get("region") or {}).items() if k not in ("ok_grid", "alpha_grid", "p_grid")},
           "stress": (jt.get("stress") or {}).get("rows"),
           "capacity": cp.get("plant"), "capacity_by_candidate": cp.get("by_candidate"), "yield_scenario": cp.get("yield"),
           "stages": (cp.get("stages") or {}).get("stages"),
           "necessity": (nc.get("necessity") or {}), "b2_required": nc.get("b2"), "drying_structure": nc.get("structure"),
           "heat_sensitivity": (cd.get("heat") or {}).get("rows"), "reverse_models": cd.get("reverse_models"),
           "boundaries": cd["boundaries"], "switch": cd["switch"],
           "priority": [{"priority": t["priority"], "id": t["id"], "question": t["question"], "impact": t["impact"]}
                        for t in cd["priority"]["tests"]],
           "shadow_mode": up.get("shadow"), "upside": up.get("whatif"),
           "economics": cd.get("economics"), "heat_map": cd.get("heat_map"), "package_mode": cd.get("package_mode"),
           "effect_selection": ev.get("effect_selection"),
           "detection": cd["detection"], "n_for_1pct": cd["n_for_1pct"],
           "errors": {k: v["error"] for k, v in cd.items() if isinstance(v, dict) and "error" in v}}
    return _clean(out)


def check(results, out_dir):
    """results.json ↔ kb_candidates.csv ↔ evidence_report.pdf 본문(부록 A 이전) 핵심 숫자 일치."""
    out_dir = Path(out_dir)
    h = results["headline"]
    checks = []
    with open(out_dir / "kb_candidates.csv", encoding="utf-8-sig") as fh:
        row = next(r for r in csv.DictReader(fh) if r["candidate"] == h["candidate"])
    for key, csv_key in (("typical", "saving_typical"), ("conservative", "saving_conservative"), ("optimistic", "saving_optimistic")):
        checks.append({"item": f"CSV 절감({key})", "ok": abs(float(row[csv_key]) - h["saving"][key]) < 1e-6})
    checks.append({"item": "CSV E_new", "ok": abs(float(row["E_typ_pt"]) - h["E_pt"]) < 1e-6})
    checks.append({"item": "CSV 여유", "ok": abs(float(row["margin_pt"]) - h["margin_pt"]) < 1e-6})
    pdf = out_dir / "evidence_report.pdf"
    try:
        from pypdf import PdfReader
        pages = [p.extract_text() or "" for p in PdfReader(str(pdf)).pages]
    except Exception as e:  # noqa: BLE001
        checks.append({"item": f"PDF 읽기 실패: {e}", "ok": False})
        pages = []
    if pages:
        idx = next((i for i, t in enumerate(pages) if "부록 A" in t), len(pages))
        main = " ".join(pages[:idx]).replace("\n", " ")
        first = pages[0].replace("\n", " ")
        want = [("PDF 1쪽 절감", f"{h['saving']['typical'] * 100:.1f}%"), ("PDF 1쪽 E_new", f"{h['E_pt']:.2f} pt"),
                ("PDF 1쪽 여유", f"{h['margin_pt']:+.2f} pt")]
        if h.get("tech_pp") is not None:
            want += [("PDF 1쪽 개조 %p", f"{h['tech_pp']:.2f}%p"), ("PDF 1쪽 희석 %p", f"{h['dilution_pp']:.2f}%p")]
        for item, s in want:
            checks.append({"item": item, "ok": s in first, "expect": s})
        checks.append({"item": "본문에 이전 모델 '추천 조합(+DRY-RAD + AGE-EARLY)' 표기 없음",
                       "ok": "AGE-EARLY): 수치" not in main and "추천 조합(+DRY-RAD" not in main})
        if h.get("plant_capacity") is not None:
            s_ = f"공장 처리능력 {h['plant_capacity']:.3f}배"
            checks.append({"item": "PDF 1쪽 처리능력 카드", "ok": s_ in first, "expect": s_})
        if h.get("aging_slot_need") is not None:
            s_ = f"+{h['aging_slot_need'] * 100:.2f}%"
            checks.append({"item": "PDF 본문 에이징 슬롯", "ok": s_ in main, "expect": s_})
        checks.append({"item": "본문에 '5,000 ppm' 에이징 불량률 표기 없음", "ok": "5,000 ppm" not in main and "5000 ppm" not in main})
        checks.append({"item": "부록 A가 본문 뒤에 있음", "ok": idx > 0 and idx < len(pages)})
    return {"ok": all(c["ok"] for c in checks), "checks": checks}


def export(res, out_dir):
    out_dir = Path(out_dir)
    results = build(res)
    chk = check(results, out_dir)
    results["consistency_check"] = chk
    (out_dir / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return chk
