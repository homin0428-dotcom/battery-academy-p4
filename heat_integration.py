"""공정 간 열 통합 지도 - 열원·열수요 온도 매칭 (판정 미반영).

레버를 계통별로만 보지 않고 공정 사이 열 연결 후보를 찾는다. 회수 가능 열량 근거가 없으므로 전력 절감은 0으로 고정하고,
effects.csv에 근거가 들어온 연결만 '계산 후보'로 표시한다. 온도 범위는 보고서 인용 범위(팀 가정) - 원문 확인 필요.
"""
from __future__ import annotations

import csv
from pathlib import Path

NODES = Path(__file__).resolve().parent / "data" / "kb" / "heat_nodes.csv"
DT_MIN = 10.0                                    # 최소 접근 온도차 °C (팀 가정)
# 같은 연결을 다루는 기존 레버
LINK_LEVER = {("S-DRY-EXH", "D-DRY-PRE"): "DRY-HX", ("S-NMP-COND", "D-DRY-PRE"): "DRY-HP", ("S-DRM-REG", "D-DRM-REG"): "DRM-HR"}
CALC_LEVERS = set()                              # 계통 기준 정량 근거가 있는 열 연결 레버 (현재 없음)


def load_nodes(path=None):
    rows = list(csv.DictReader(open(path or NODES, encoding="utf-8")))
    out = []
    for r in rows:
        lo, hi = float(r["T_lo"]), float(r["T_hi"])
        if lo > hi:
            raise ValueError(f"{r['node_id']}: T_lo > T_hi")
        if r["kind"] not in ("열원", "열수요"):
            raise ValueError(f"{r['node_id']}: kind는 열원/열수요")
        out.append({**r, "T_lo": lo, "T_hi": hi})
    return out


def match(nodes, dt=DT_MIN, effects_levers=None):
    src = [n for n in nodes if n["kind"] == "열원"]
    dem = [n for n in nodes if n["kind"] == "열수요"]
    calc = set(effects_levers or CALC_LEVERS)
    rows = []
    for s in src:
        for d in dem:
            if s["T_hi"] - dt >= d["T_lo"]:
                how = "직접 열교환 가능(열원 상단 온도 기준)" + (" - 전 범위 보장" if s["T_lo"] - dt >= d["T_lo"] else " - 열원 하단에서는 부족")
            else:
                how = f"히트펌프 필요(승온 {d['T_lo'] - (s['T_hi'] - dt):.0f}°C 이상, COP 근거 필요)"
            if d["T_lo"] - (s["T_hi"] - dt) > 80:
                how = "연결 불가(승온 폭 과대 - 현실적 히트펌프 범위 밖)"
            lever = LINK_LEVER.get((s["node_id"], d["node_id"]))
            rows.append({"source": s["node_id"], "source_name": s["name"], "demand": d["node_id"], "demand_name": d["name"],
                         "cross_process": s["system"] != d["system"], "how": how, "lever": lever or "-",
                         "contaminant": s.get("contaminant") or "-",
                         "calc_candidate": bool(lever and lever in calc), "power_effect_pt": 0.0})
    rows.sort(key=lambda r: (r["how"].startswith("연결 불가"), not r["cross_process"], r["source"]))
    return rows


def analyze(values, path=None):
    nodes = load_nodes(path)
    rows = match(nodes)
    return {"nodes": nodes, "matches": rows, "dt_min": DT_MIN,
            "n_cross": sum(r["cross_process"] and not r["how"].startswith("연결 불가") for r in rows),
            "label": "검증 통과 시 추가 이득 - 기본 결론 미반영 (전력 절감 0으로 고정)",
            "note": "온도 범위는 보고서가 인용한 범위·팀 가정이며 C사 계측이 필요하다. 회수 가능 열량 근거가 effects.csv에 들어온 연결만 계산 후보가 된다."}
