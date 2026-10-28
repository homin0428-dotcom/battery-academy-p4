"""근거 기반 자동 판정 보고서 - 그래프 2개 · CSV 4종 · PDF.

계산은 core.run_scenario()의 res["evidence"](evidence_engine 결과)만 사용한다.
기존 4쪽 결과 보고서(result_report.pdf)와 별도 파일(evidence_report.pdf)로 만든다.
"""
from __future__ import annotations

import csv
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import kb_schema as S
import reporting as R   # 폰트·색상·PDF 부품 공유
from candidates import sys_change

AMBER, RED = "#B7791F", "#B23A3A"
pct = lambda x, n=1: "-" if x is None else f"{x * 100:.{n}f}%"
# NanumGothic에 없는 글리프 → 같은 뜻의 있는 글리프 (빈칸으로 사라지면 '−0.8%p'가 '0.8%p'로 뜻이 바뀜)
GLYPH_MAP = {"∅": "직경 ", "−": "-", "µ": "μ", "∙": "·", "–": "-", "—": "-", "Ö": "O"}


def short_prod(v):
    """비교표용 짧은 증산 판정 표기."""
    if not v:
        return "-"
    return {"증산 미완결 - 에이징 보관능력 미확보": "미완결\n(에이징 보관)",
            "증산 미달 - 화성 처리능력 부족": "미달\n(화성 능력)"}.get(v, v.replace("증산 ", ""))


def safe_text(s):
    s = str(s)
    for a, b in GLYPH_MAP.items():
        s = s.replace(a, b)
    return s


# ------------------------------------------------------------------ 그래프
def fig_systems(res):
    """계통별 근거 범위(보수~낙관, 대표 점) vs v10 가정(×) vs 목표 도달 단독 요구(◇)."""
    ev = res["evidence"]
    fig, ax = plt.subplots(figsize=(6.6, 2.9))
    ys = list(range(len(S.SYSTEMS)))[::-1]
    req = {r["system"]: r["required"] for r in ev["reverse"]}
    for y, s in zip(ys, S.SYSTEMS):
        sr = ev["systems"][s]
        has = sr["status"] not in ("변경 없음", "근거 없음")
        if has:
            ax.plot([sr["lo"] * 100, sr["hi"] * 100], [y, y], color=R.TEAL, lw=7, solid_capstyle="butt", alpha=0.55)
            ax.plot([sr["typ"] * 100], [y], "o", color=R.NAVY, ms=6)
        else:
            ax.text(1, y, "근거 없음" if sr["status"] == "근거 없음" else "선택 레버 없음", va="center", fontsize=7.5,
                    color=RED if sr["status"] == "근거 없음" else R.GRAY)
        a = res["inputs"]["r"][S.SYSTEMS.index(s)]
        if a > 0:
            ax.plot([a * 100], [y], "x", color=RED, ms=8, mew=2)
        q = req.get(s)
        if q is not None and 0 < q <= 1:
            ax.plot([q * 100], [y], "D", mfc="white", mec=AMBER, mew=1.6, ms=6)
    ax.set_yticks(ys)
    ax.set_yticklabels(S.SYSTEMS)
    ax.set_xlim(0, 100)
    ax.set_xlabel("계통 전력 절감률 (%)")
    from matplotlib.lines import Line2D
    h = [Line2D([], [], color=R.TEAL, lw=7, alpha=0.55, label="근거 범위(보수~낙관)"),
         Line2D([], [], marker="o", ls="", color=R.NAVY, label="근거 대표값"),
         Line2D([], [], marker="x", ls="", color=RED, mew=2, label="v10 가정"),
         Line2D([], [], marker="D", ls="", mfc="white", mec=AMBER, label="단독 보완 요구값")]
    # 범례는 그림 위쪽 바깥에 둔다 (아래쪽 계통 행을 가리지 않게)
    ax.legend(handles=h, fontsize=7, frameon=False, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=4,
              borderaxespad=0.2, handletextpad=0.4, columnspacing=1.2)
    ax.grid(axis="x", alpha=0.25, lw=0.5)
    fig.tight_layout()
    return fig


def fig_cases(res):
    """원단위 절감: v10 가정 결과 vs 근거 기반(선택 조합) vs 근거 기반 최선 추가 조합 - 보수·대표·낙관."""
    ev = res["evidence"]
    rows = [("v10 가정\n(수동 r)", None, res["plant"].get("saving_ratio"), None)]
    c = ev["cases"]
    rows.append(("근거 기반\n선택 조합", c["conservative"]["saving"], c["typical"]["saving"], c["optimistic"]["saving"]))
    ok = [x for x in ev["combos"]["results"] if x["verdict"] != "근거상 미달"]
    if ok:
        b = ok[0]
        rows.append(("근거 기반\n+" + "+".join(b["add"]), b["conservative"], b["typical"], b["optimistic"]))
    fig, ax = plt.subplots(figsize=(6.6, 2.6))
    for i, (lab, lo, typ, hi) in enumerate(rows):
        if lo is not None:
            ax.plot([i, i], [lo * 100, hi * 100], color=R.TEAL, lw=10, solid_capstyle="butt", alpha=0.45)
        ax.plot([i], [typ * 100], "o", color=R.NAVY if lo is not None else RED, ms=8)
        ax.annotate(f"{typ * 100:.1f}%", (i, typ * 100), textcoords="offset points", xytext=(12, -3), fontsize=8, color=R.NAVY)
    tgt = ev["cases"]["typical"]["plant"]["target_saving_ratio"] * 100
    ax.axhline(tgt, color=AMBER, lw=1.4, ls="--")
    ax.text(-0.45, tgt + 0.6, f"목표 {tgt:.0f}%", color=AMBER, fontsize=8, ha="left")   # 왼쪽 끝 - 값 주석과 겹치지 않게
    ax.set_xticks(range(len(rows)))
    ax.set_xticklabels([r[0] for r in rows], fontsize=8)
    ax.set_xlim(-0.5, len(rows) - 0.4)
    ax.set_ylabel("원단위 절감률 (%)")
    ax.grid(axis="y", alpha=0.25, lw=0.5)
    fig.tight_layout()
    return fig


def fig_sensitivity(res):
    """결합 이득 유지율 κ × 추가 관리 전력 P 격자의 대표 절감률. 목표선(30%) 경계와 현재 가정점(κ=1, P=0)을 표시."""
    import numpy as np
    sv = res["evidence"]["sensitivity"]
    K, Pg = sv["kappa_grid"], sv["p_grid"]
    Z = np.array(sv["saving_typ"]) * 100
    tgt = sv["target"] * 100
    fig, ax = plt.subplots(figsize=(6.6, 2.9))
    from matplotlib.colors import TwoSlopeNorm
    norm = TwoSlopeNorm(vmin=min(Z.min(), tgt - 0.1), vcenter=tgt, vmax=max(Z.max(), tgt + 0.1))
    im = ax.pcolormesh(Pg, K, Z, shading="nearest", cmap="RdYlGn", norm=norm, alpha=0.85)
    cs = ax.contour(Pg, K, Z, levels=[tgt], colors=[R.NAVY], linewidths=1.6)
    ax.clabel(cs, fmt={tgt: f"목표 {tgt:.0f}%"}, fontsize=7.5)
    ax.plot([0], [1.0], marker="o", color=R.NAVY, ms=7)
    ax.annotate("현재 가정(독립 결합, 추가 부담 0)", (0, 1.0), textcoords="offset points", xytext=(8, -12), fontsize=7.5, color=R.NAVY)
    ax.set_xlabel("추가 미정량 관리 전력 P (pt, 기준 공장 100 대비)")
    ax.set_ylabel("결합 이득 유지율 κ")
    cb = fig.colorbar(im, ax=ax, pad=0.02)
    cb.set_label("대표 원단위 절감률 (%)", fontsize=8)
    cb.ax.tick_params(labelsize=7)
    fig.tight_layout()
    return fig


def fig_candidates(res):
    """A/B/C 동일 기준 비교(왼쪽)와 고형분-용매-건조 체류 경계(오른쪽)."""
    import numpy as np
    cd = res["evidence"]["candidates"]
    cands = cd["candidates"]
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(6.8, 2.8), gridspec_kw={"width_ratios": [1.05, 1]})
    for i, c in enumerate(cands):
        lo, typ, hi = c["saving"]
        col = R.NAVY if c["id"] == cd["selected"] else (R.GRAY if not c["eligible"] else R.TEAL)
        ax.plot([i, i], [lo * 100, hi * 100], color=col, lw=9, solid_capstyle="butt", alpha=0.45)
        ax.plot([i], [typ * 100], "o", color=col, ms=6)
        ax.annotate(f"{typ * 100:.1f}%", (i, typ * 100), textcoords="offset points", xytext=(7, -3), fontsize=7, color=R.NAVY)
    tgt = (1 - res["inputs"]["target_intensity_ratio"]) * 100
    ax.axhline(tgt, color=AMBER, lw=1.2, ls="--")
    ax.text(-0.45, tgt + 0.8, f"목표 {tgt:.0f}%", color=AMBER, fontsize=7)
    ax.set_xticks(range(len(cands)))
    ax.set_xticklabels([c["id"] + ("\n(대기)" if not c["eligible"] else "") for c in cands], fontsize=7.5)
    ax.set_xlim(-0.5, len(cands) - 0.3)
    ax.set_ylabel("원단위 절감률 (%)", fontsize=8)
    ax.set_title("같은 기준선 111.2 pt 대비 (보수~낙관, 점=대표)", fontsize=7.5)
    ax.tick_params(labelsize=7)
    ax.grid(axis="y", alpha=0.25, lw=0.5)
    v = res["inputs"]
    q, s0 = v["q"], v.get("solids_old") or 0.60
    s = np.linspace(0.55, 0.75, 201)
    sa = ((1 - s) / s) / ((1 - s0) / s0)
    bx.plot(s * 100, q * sa, color=R.TEAL, lw=1.6, label="총 용매량 (기존 10 GWh=1)")
    bx.plot(s * 100, sa, color=R.NAVY, lw=1.6, label="필요 건조시간 (증발속도 동일)")
    bx.axhline(1.0, color=R.GRAY, lw=0.8, ls=":")
    bx.axhline(1 / q, color=AMBER, lw=1.2, ls="--")
    bx.text(55.3, 1 / q - 0.06, f"가능 체류 {1 / q:.3f} (속도 {q:g}배)", fontsize=6.8, color=AMBER)
    smin = q * s0 / (1 + (q - 1) * s0)
    bx.axvline(smin * 100, color=RED, lw=1, ls="--")
    bx.text(smin * 100 + 0.3, 1.15, f"{smin * 100:.2f}%", fontsize=6.8, color=RED)
    for c in cands:
        if c["solids_changed"]:
            bx.plot([c["solids"] * 100], [c["mass_balance"]["solvent_vs_base"]], "o", color=R.NAVY, ms=4)
    bx.set_xlabel("고형분 (wt%)", fontsize=8)
    bx.set_ylabel("비율", fontsize=8)
    bx.set_title("고형분 경계: 용매량 유지 = 체류 안 건조", fontsize=7.5)
    bx.tick_params(labelsize=7)
    bx.legend(fontsize=6.3, frameon=False, loc="upper right")
    bx.grid(alpha=0.25, lw=0.5)
    fig.tight_layout()
    return fig


def fig_waterfall(res):
    wf = res["evidence"]["candidates"]["baseline_model"]["waterfall"]
    fig, ax = plt.subplots(figsize=(6.6, 2.7))
    labels, vals, kinds = [], [], []
    for stp in wf["steps"]:
        if abs(stp["pt"]) < 1e-9:
            continue
        labels.append(stp["item"].replace("(생산량이 늘어도 안 느는 부하)", "").replace("(FMEA 관리조치)", ""))
        vals.append(stp["pt"])
        kinds.append(stp["kind"])
    x = 0
    cur = wf["start_pt"]
    ax.bar(x, cur, color=R.GRAY, width=0.6)
    ax.text(x, cur + 1, f"{cur:.1f}", ha="center", fontsize=7.5)
    names = ["전부 비례"]
    for lab, v, k in zip(labels, vals, kinds):
        x += 1
        col = AMBER if k == "희석" else (R.TEAL if k == "개조" else RED)
        ax.bar(x, -v, bottom=cur, color=col, width=0.6)
        ax.text(x, cur + 1, f"-{v:.2f} pt\n({v / wf['start_pt'] * 100:.2f}%p)", ha="center", fontsize=6.8)
        cur -= v
        names.append(lab)
    x += 1
    ax.bar(x, cur, color=R.NAVY, width=0.6)
    ax.text(x, cur + 1, f"{cur:.2f}", ha="center", fontsize=7.5)
    names.append("E_new")
    tgt = res["evidence"]["candidates"]["baseline"]["target"]
    ax.axhline(tgt, color=RED, ls="--", lw=1)
    ax.text(-0.45, tgt + 1, f"목표 {tgt:.0f} pt", color=RED, fontsize=7, ha="left")
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, fontsize=7)
    ax.set_ylim(60, wf["start_pt"] + 10)
    ax.set_ylabel("12 GWh 총전력 (pt)", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.grid(axis="y", alpha=0.25, lw=0.5)
    fig.tight_layout()
    return fig


def fig_tornado(res):
    sv = res["evidence"]["candidates"]["baseline_model"]["sensitivity"]
    rows = sv["rows"][::-1]
    base = sv["base_saving"] * 100
    fig, ax = plt.subplots(figsize=(6.6, 2.2))
    for i, r in enumerate(rows):
        lo, hi = r["lo"]["saving"] * 100, r["hi"]["saving"] * 100
        ax.barh(i, lo - base, left=base, color=R.TEAL, alpha=0.7, height=0.55)
        ax.barh(i, hi - base, left=base, color=AMBER, alpha=0.7, height=0.55)
        ax.text(min(lo, hi) - 0.15, i, f"{min(lo, hi):.2f}", va="center", ha="right", fontsize=6.8)
        ax.text(max(lo, hi) + 0.15, i, f"{max(lo, hi):.2f}", va="center", ha="left", fontsize=6.8)
    ax.axvline(base, color=R.NAVY, lw=1)
    ax.axvline(30, color=RED, ls="--", lw=1)
    ax.text(30.1, len(rows) - 0.4, "목표 30%", color=RED, fontsize=7)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r["label"] for r in rows], fontsize=7)
    ax.set_xlabel("원단위 절감률 (%) — 청록 = 하한 값, 주황 = 상한 값", fontsize=7.5)
    ax.set_xlim(29, max(r["hi"]["saving"] * 100 for r in rows) + 1.5)
    ax.tick_params(labelsize=7)
    fig.tight_layout()
    return fig


def fig_joint(res):
    import numpy as np
    jt = res["evidence"]["candidates"]["joint"]
    rg, ss = jt["region"], jt["stress"]
    A, Pg = np.array(rg["alpha_grid"]), np.array(rg["p_grid"])
    Z = np.array(rg["ok_grid"], dtype=float)
    fig, ax = plt.subplots(figsize=(6.6, 2.8))
    ax.contourf(Pg, A, Z, levels=[-0.5, 0.5, 1.5], colors=["#F3D9D9", "#D7ECE6"])
    pl = rg["target"] - rg["a"] + rg["b"] * A
    ax.plot(pl, A, color=R.NAVY, lw=1.5)
    ax.axhline(rg["alpha_star"], color=R.GRAY, ls=":", lw=1)
    ax.axvline(rg["p_max"][1.0], color=R.GRAY, ls=":", lw=1)
    ax.text(0.15, rg["alpha_star"] - 0.03, f"단독 경계 α* {rg['alpha_star']:.3f}", fontsize=6.8, color=R.GRAY)
    ax.text(rg["p_max"][1.0] + 0.1, 0.62, f"단독 경계 P {rg['p_max'][1.0]:.2f}", fontsize=6.8, color=R.GRAY)
    ax.plot([0], [1.0], "o", color=R.NAVY)
    ax.annotate("현재 가정", (0, 1.0), textcoords="offset points", xytext=(6, 4), fontsize=7, color=R.NAVY)
    for sid, a_, p_ in (("S1", 0.9, 4.0), ("S2", 0.8, 2.0)):
        ax.plot([p_], [a_], "x", color=RED, mew=2)
        ax.annotate(sid, (p_, a_), textcoords="offset points", xytext=(5, 3), fontsize=7, color=RED)
    ax.text(7.5, 1.05, "성립", fontsize=8, color=R.TEAL)
    ax.text(7.5, 0.66, "미달", fontsize=8, color=RED)
    ax.set_xlabel("미정량 관리 전력 P (pt)", fontsize=8)
    ax.set_ylabel("문헌 효과 전이율 α", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.set_xlim(0, 10)
    ax.set_ylim(A.min(), A.max())
    fig.tight_layout()
    return fig


def fig_heatmap(res):
    hm = res["evidence"]["candidates"]["heat_map"]
    nodes = hm["nodes"]
    fig, ax = plt.subplots(figsize=(6.6, 2.6))
    xs = {}
    for i, n in enumerate(nodes):
        col = RED if n["kind"] == "열원" else R.TEAL
        ax.plot([i, i], [n["T_lo"], n["T_hi"]], color=col, lw=9, solid_capstyle="butt", alpha=0.6)
        ax.text(i, n["T_hi"] + 4, f"{n['T_lo']:.0f}~{n['T_hi']:.0f}", ha="center", fontsize=6.3)
        xs[n["node_id"]] = (i, n)
    for m_ in hm["matches"]:
        if m_["how"].startswith("직접"):
            (x1, s), (x2, d) = xs[m_["source"]], xs[m_["demand"]]
            ax.annotate("", xy=(x2, d["T_lo"]), xytext=(x1, s["T_hi"] - 5),
                        arrowprops=dict(arrowstyle="->", color=R.NAVY, lw=0.8, alpha=0.7))
    ax.set_xticks(range(len(nodes)))
    ax.set_xticklabels([("열원\n" if n["kind"] == "열원" else "수요\n") + n["system"] for n in nodes], fontsize=6.5)
    ax.set_ylabel("온도 (°C)", fontsize=8)
    ax.set_ylim(0, 200)
    ax.tick_params(labelsize=7)
    ax.grid(axis="y", alpha=0.25, lw=0.5)
    ax.set_title("빨강 = 열원, 청록 = 열수요, 화살표 = 직접 열교환 후보(열원 상단 - 10°C ≥ 수요 하단)", fontsize=7)
    fig.tight_layout()
    return fig


def fig_gantt(res):
    ro = res["evidence"]["candidates"]["economics"]["rollout"]
    rows = ro["rows"][::-1]
    fig, ax = plt.subplots(figsize=(6.6, 3.0))
    for i, r in enumerate(rows):
        core = r.get("role") == "핵심"
        ax.barh(i, max(r["duration_q"], 0.3), left=r["start_q"] - 1, color=R.NAVY if core else R.GRAY, alpha=0.8 if core else 0.45, height=0.6)
        ax.text(r["start_q"] - 1 + max(r["duration_q"], 0.3) + 0.1, i,
                (f"목표 {r['target_pp']:.2f}%p" if r.get("target_pp") else "처리능력 수단(승인 슬롯)" if core else "실측 후 편입"),
                va="center", fontsize=6.3)
    for y in (4, 8):
        ax.axvline(y, color=R.GRAY, ls=":", lw=0.8)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r["lever_id"] for r in rows], fontsize=7)
    ax.set_xticks([0, 2, 4, 6, 8, 10, 12])
    ax.set_xticklabels(["시작", "6개월", "1년", "1.5년", "2년", "2.5년", "3년"], fontsize=7)
    ax.set_xlim(0, 13.5)
    ax.set_title("남색 = 핵심 레버(절감 목표 있음), 회색 = 근거 미확보(목표 없음)", fontsize=7)
    fig.tight_layout()
    return fig


def fig_reach(res):
    rc = res["evidence"]["candidates"]["roadmap"]["reach"]
    rows = rc["rows"]
    labs = [r["stage"].replace(" ", "\n", 1) for r in rows]
    x = range(len(rows))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.6, 2.6))
    w = 0.38
    a1.bar([i - w / 2 for i in x], [r["power_no_slot"] * 100 for r in rows], w, color=R.GRAY, alpha=0.6, label="에이징 공간 미확보")
    a1.bar([i + w / 2 for i in x], [r["power_if_slot"] * 100 for r in rows], w, color=R.NAVY, hatch="//", edgecolor="white",
           label="승인 슬롯 확보 시(조건부)")
    a1.axhline(rc["target_power"] * 100, color=RED, ls="--", lw=1)
    a1.text(-0.45, rc["target_power"] * 100 + 0.8, "목표 30%", color=RED, fontsize=6.5, ha="left")
    for i, r in enumerate(rows):
        a1.text(i - w / 2, r["power_no_slot"] * 100 + 0.5, f"{r['power_no_slot'] * 100:.1f}", ha="center", fontsize=6)
        a1.text(i + w / 2, r["power_if_slot"] * 100 + 0.5, f"{r['power_if_slot'] * 100:.1f}", ha="center", fontsize=6)
    a1.set_xticks(list(x)); a1.set_xticklabels(labs, fontsize=6.5); a1.set_ylim(0, 48)
    a1.set_title("전력 원단위 절감(%) - 그 시점 생산비 기준", fontsize=7); a1.legend(fontsize=5.8, loc="upper left", ncol=2)
    a2.bar([i - w / 2 for i in x], [r["q_no_slot"] for r in rows], w, color=R.GRAY, alpha=0.6)
    a2.bar([i + w / 2 for i in x], [r["q_if_slot"] for r in rows], w, color=R.NAVY, hatch="//", edgecolor="white")
    a2.axhline(rc["target_q"], color=RED, ls="--", lw=1)
    a2.text(-0.45, rc["target_q"] + 0.008, f"목표 {rc['target_q']:g}배", color=RED, fontsize=6.5, ha="left")
    for i, r in enumerate(rows):
        a2.text(i - w / 2, r["q_no_slot"] + 0.004, f"{r['q_no_slot']:.3f}", ha="center", fontsize=6)
        a2.text(i + w / 2, r["q_if_slot"] + 0.004, f"{r['q_if_slot']:.3f}", ha="center", fontsize=6)
    a2.set_xticks(list(x)); a2.set_xticklabels(labs, fontsize=6.5); a2.set_ylim(1.0, 1.27)
    a2.set_title("생산비 q_t (공장 처리능력, 1.2 상한)", fontsize=7)
    for a in (a1, a2):
        a.tick_params(labelsize=6.5)
    fig.tight_layout()
    return fig


def write_figures(res, out):
    out = Path(out)
    figs = [("evidence_systems.png", fig_systems), ("evidence_cases.png", fig_cases)]
    cd = res["evidence"].get("candidates")
    if cd:
        figs.append(("evidence_candidates.png", fig_candidates))
        if isinstance(cd.get("baseline_model"), dict) and "waterfall" in cd["baseline_model"]:
            figs += [("v12_waterfall.png", fig_waterfall), ("v12_tornado.png", fig_tornado)]
        if isinstance(cd.get("joint"), dict) and "region" in cd["joint"]:
            figs.append(("v12_joint.png", fig_joint))
        if isinstance(cd.get("heat_map"), dict) and "nodes" in cd["heat_map"]:
            figs.append(("v12_heatmap.png", fig_heatmap))
        if isinstance(cd.get("economics"), dict) and "rollout" in cd["economics"]:
            figs.append(("v12_gantt.png", fig_gantt))
        if isinstance(cd.get("roadmap"), dict) and "reach" in cd["roadmap"]:
            figs.append(("v12_reach.png", fig_reach))
    if res["evidence"].get("sensitivity"):
        figs.append(("evidence_sensitivity.png", fig_sensitivity))
    for name, fn in figs:
        fig = fn(res)
        fig.savefig(out / name, dpi=300, facecolor="white")
        plt.close(fig)


# ------------------------------------------------------------------ CSV
def _w(path, rows, fields):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_csvs(res, out):
    ev, out = res["evidence"], Path(out)
    cases = []
    for k in ("conservative", "typical", "optimistic"):
        c = ev["cases"][k]
        cases.append({"case": k, "case_ko": {"conservative": "보수", "typical": "대표", "optimistic": "낙관"}[k],
                      **{f"r_{s}": c["r"][i] for i, s in enumerate(S.SYSTEMS)}, "p_add_pt": c["p_add"],
                      "occupancy_h": c["occupancy_h"], "E_total": c["E_total"], "saving_ratio": c["saving"],
                      "gap_pt": c["gap"], "plant_ok": c["plant_ok"], "capacity_ratio": c["capacity"],
                      "capacity_upper_bound": c.get("capacity_upper_bound"), "verdict": ev["verdict"]})
    _w(out / "kb_cases.csv", cases, list(cases[0]))
    lev = [{"lever_id": l["lever_id"], "name": l["name"], "system": l["system"], "selected": l["selected"],
            "v10_adopted": l["v10_adopted"], "judge": l["judge"],
            "saving_lo": l["range"][0] if l["range"] else None, "saving_typ": l["range"][1] if l["range"] else None,
            "saving_hi": l["range"][2] if l["range"] else None, "n_calc": l["n_calc"], "n_ref": l["n_ref"],
            "best_grade": l["best_grade"], "failure_modes": "; ".join(l["failure_modes"]), "quality_gates": l["gates"],
            "pending_burdens": "; ".join(l["pending"]), "effect_ids": "; ".join(l["ids"]), "next_actions": "; ".join(l["todo"])}
           for l in ev["levers"]]
    _w(out / "kb_lever_judgement.csv", lev, list(lev[0]))
    tr = [{"effect_id": e["effect_id"], "lever_id": e["lever_id"], "system": e["system"], "metric": e["metric"],
           "raw_lo": e["raw"][0], "raw_typ": e["raw"][1], "raw_hi": e["raw"][2], "boundary": e["boundary"],
           "conversion": e["how"], "sys_lo": e["lo"], "sys_typ": e["typ"], "sys_hi": e["hi"], "use": e["use"],
           "transfer": e["transfer"], "transfer_reasons": "; ".join(e["transfer_reasons"]), "flags": "; ".join(e["flags"]),
           "source_id": e["source_id"], "locator": e["locator"], "grade": e["grade"], "verification": e["verification"],
           "excerpt": e["excerpt"]} for e in ev["effects"]]
    _w(out / "kb_effect_trace.csv", tr, list(tr[0]))
    cb = [{"add": "+".join(x["add"]), "names": " + ".join(x["names"]), "verdict": x["verdict"],
           "conservative": x["conservative"], "typical": x["typical"], "optimistic": x["optimistic"],
           "gap_typical_pt": x["gap_typical"]} for x in ev["combos"]["results"]]
    _w(out / "kb_combos.csv", cb or [{"add": "", "verdict": "후보 없음"}],
       ["add", "names", "verdict", "conservative", "typical", "optimistic", "gap_typical_pt"])
    yrs = ev["options"]["payback_years"]
    op = []
    for r in ev["options"]["rows"]:
        m = r["money_typ"]
        row = {"option": r["option"], "levers": "+".join(r["levers"]), "verdict": r["verdict"],
               "saving_conservative": r["saving"][0], "saving_typical": r["saving"][1], "saving_optimistic": r["saving"][2],
               "gap_typical_pt": r["gap_typ"], "pt_saved_typical": r["pt_saved_typ"],
               "annual_gwh_lo": m["gwh"][0] if m else None, "annual_gwh_hi": m["gwh"][1] if m else None,
               "annual_krw_eok_lo": m["krw_eok"][0] if m else None, "annual_krw_eok_hi": m["krw_eok"][1] if m else None,
               "production": r["production"], "fmea_risks": r["risks"], "safety_risks": r["safety_risks"],
               "max_change_type": r["difficulty"], "evidence": r["evidence"]}
        for n in yrs:
            row[f"allowed_invest_{n}y_eok_lo"] = m["invest_eok"][n][0] if m else None
            row[f"allowed_invest_{n}y_eok_hi"] = m["invest_eok"][n][1] if m else None
        op.append(row)
    _w(out / "kb_options.csv", op, list(op[0]))
    _w(out / "kb_thresholds.csv", ev["thresholds"], ["kind", "system", "value", "margin", "text"])
    sv = ev.get("sensitivity")
    if sv:
        db = [{"kappa": k, "extra_burden_pt": p, "saving_typical": sv["saving_typ"][i][j],
               "meets_target_typical": sv["saving_typ"][i][j] >= sv["target"] - 1e-12, "levers": "+".join(sv["levers"])}
              for i, k in enumerate(sv["kappa_grid"]) for j, p in enumerate(sv["p_grid"])]
        _w(out / "kb_decision_boundary.csv", db, list(db[0]))
    cd = ev.get("candidates")
    if cd:
        yrs = ev["options"]["payback_years"]
        rows = []
        for c in cd["candidates"]:
            m = c["money_typ"]
            row = {"candidate": c["id"], "name": c["name"], "role": c["role"], "selected": c["id"] == cd["selected"],
                   "eligible": c["eligible"], "why_not": c["why_not"], "levers": "+".join(c["levers"]), "solids": c["solids"],
                   "quality_gates": c["n_gates"], "safety_gates": c["n_safety_gates"],
                   "solvent_vs_base": c["mass_balance"]["solvent_vs_base"],
                   "solvent_per_area_ratio": c["mass_balance"]["solvent_per_solid_ratio"],
                   "r_drying_typ": c["r_drying"][1], "saving_conservative": c["saving"][0], "saving_typical": c["saving"][1],
                   "saving_optimistic": c["saving"][2], "E_typ_pt": c["E_typ"], "E0_pt": c["E0"], "margin_pt": c["margin_pt"],
                   "annual_krw_eok_lo": m["krw_eok"][0] if m else None, "annual_krw_eok_hi": m["krw_eok"][1] if m else None,
                   **{a["axis"]: f"{a['state']} | {a['status']}" for a in c["axes"]}, "overall": c["label"],
                   "shortfall": (c["shortfall"] or {}).get("text", "")}
            for n in yrs:
                row[f"allowed_invest_{n}y_eok_lo"] = m["invest_eok"][n][0] if m else None
                row[f"allowed_invest_{n}y_eok_hi"] = m["invest_eok"][n][1] if m else None
            rows.append(row)
        _w(out / "kb_candidates.csv", rows, list(rows[0]))
        if cd.get("heat"):
            _w(out / "kb_heat_sensitivity.csv",
               [{"case": r["case"], "candidate": r["candidate"], "selected": r["selected"], "saving_conservative": r["saving"][0],
                 "saving_typical": r["saving"][1], "saving_optimistic": r["saving"][2], "margin_pt": r["margin_pt"],
                 "r_drying_typ": r["r_drying"], "r_dryroom_typ": r["r_dryroom"], "energy_state": r["energy_state"],
                 "overall": r["label"]} for r in cd["heat"]["rows"]],
               ["case", "candidate", "selected", "saving_conservative", "saving_typical", "saving_optimistic", "margin_pt",
                "r_drying_typ", "r_dryroom_typ", "energy_state", "overall"])
        if cd.get("stages"):
            _w(out / "kb_stage_progress.csv",
               [{"candidate": cd["stages"]["candidate"], "stage": x["stage"], "added": "+".join(x["added"]), "levers": "+".join(x["levers"]),
                 "solids": x["solids"], "saving_conservative": x["saving"][0], "saving_typical": x["saving"][1],
                 "saving_optimistic": x["saving"][2], "margin_pt": x["margin_pt"], "overall": x["label"]} for x in cd["stages"]["stages"]],
               ["candidate", "stage", "added", "levers", "solids", "saving_conservative", "saving_typical", "saving_optimistic",
                "margin_pt", "overall"])
        if cd.get("reverse_models"):
            _w(out / "kb_reverse_models.csv", cd["reverse_models"]["rows"],
               ["system", "w", "f", "B_linear", "B_engine", "linear", "engine", "after_A"])
        eco = cd.get("economics") if isinstance(cd.get("economics"), dict) and "levers" in cd.get("economics", {}) else None
        if eco:
            _w(out / "kb_lever_economics.csv",
               [{"lever_id": r["lever_id"], "name": r["name"], "class": r["class"], "delta_pp": r["delta_pp"], "pt": r["pt"],
                 "annual_krw_eok_lo": r["krw_eok"][0] if r["krw_eok"] else None, "annual_krw_eok_hi": r["krw_eok"][1] if r["krw_eok"] else None,
                 "capex_eok": r["capex_eok"], "status": r["status"]} for r in eco["levers"]["rows"]],
               ["lever_id", "name", "class", "delta_pp", "pt", "annual_krw_eok_lo", "annual_krw_eok_hi", "capex_eok", "status"])
            _w(out / "kb_rollout.csv", eco["rollout"]["rows"],
               ["lever_id", "name", "change_type", "start_q", "duration_q", "scope", "downtime_days", "target_pp", "role", "gate", "source"])
        rm = cd.get("roadmap") if isinstance(cd.get("roadmap"), dict) and "space" in cd.get("roadmap", {}) else None
        if rm:
            _w(out / "kb_space_plan.csv", rm["space"]["options"], ["no", "name", "how", "depends", "when", "basis"])
            _w(out / "kb_reach.csv", rm["reach"]["rows"], ["stage", "power_no_slot", "power_if_slot", "q_no_slot", "q_if_slot",
                                                          "cap_reach_no_slot", "cap_reach_if_slot", "power_ok_no_slot", "power_ok_if_slot"])
            _w(out / "kb_horizon.csv", rm["horizon"]["rows"], ["lever_id", "name", "delta_pp", "power_grade", "nature", "horizon", "when", "method", "pass"])
            _w(out / "kb_impact_matrix.csv", rm["impact"]["rows"],
               ["lever_id", "name", "capacity", "power", "capex", "difficulty", "quality", "safety", "horizon"])
        lc = ((cd.get("baseline_model") or {}).get("literature_cases") or {}).get("rows") if isinstance(cd.get("baseline_model"), dict) else None
        if lc:
            _w(out / "kb_literature_cases.csv", lc, ["key", "label", "source", "saving", "margin_pt", "selected", "energy_state"])
        hm = cd.get("heat_map") if isinstance(cd.get("heat_map"), dict) and "matches" in cd.get("heat_map", {}) else None
        if hm:
            _w(out / "kb_heat_matches.csv", hm["matches"],
               ["source", "source_name", "demand", "demand_name", "cross_process", "how", "lever", "contaminant", "calc_candidate", "power_effect_pt"])
        _w(out / "kb_boundaries.csv", [{**b, "candidate": cd["selected"]} for b in cd["boundaries"]],
           ["candidate", "kind", "value", "unit", "current", "text"])
        _w(out / "kb_verification_priority.csv",
           [{"priority": t["priority"], "id": t["id"], "question": t["question"], "how": t["how"], "impact": t["impact"],
             "cost_assumed": t["cost"], "period_assumed": t["period"], "outcomes": t["text"]} for t in cd["priority"]["tests"]],
           ["priority", "id", "question", "how", "impact", "cost_assumed", "period_assumed", "outcomes"])
    ov = ev.get("overall")
    if ov:
        _w(out / "kb_overall.csv", [{"scope": "추천 조합", "overall": ov["label"], **{a["axis"]: f"{a['state']} | {a['status']}" for a in ov["axes"]}},
                                    {"scope": "현재 선택", "overall": ev["overall_selected"]["label"],
                                     **{a["axis"]: f"{a['state']} | {a['status']}" for a in ev["overall_selected"]["axes"]}}],
           ["scope", "overall"] + [a["axis"] for a in ov["axes"]])
    q = ev.get("quality")
    if q and q["rows"]:
        _w(out / "kb_quality_gates.csv", [{**r, "changed": "; ".join(r["changed"])} for r in q["rows"]],
           ["fmea_id", "lever_id", "failure_mode", "gate", "status", "changed", "memo"])
    rm = [{"stage": st_["year"], "title": st_["title"], "lever_id": l["lever_id"], "name": l["name"],
           "change_type": l["change_type"], "has_evidence": l["has_evidence"], "quality_gates": " | ".join(l["gates"]),
           "stage_exit": st_["exit"]} for st_ in ev["roadmap"] for l in st_["levers"]]
    _w(out / "kb_roadmap.csv", rm or [{"stage": "-"}],
       ["stage", "title", "lever_id", "name", "change_type", "has_evidence", "quality_gates", "stage_exit"])


# ------------------------------------------------------------------ A/B/C 후보 페이지
def _nm(clean, lid):
    lv = next((l for l in clean["levers"] if l["lever_id"] == lid), None)
    return f"{lv['name_ko']}({lid})" if lv else lid


def candidate_pages(res, cd, st, P, table, m, W, esc, Paragraph, Spacer, mm, colors, Table, TableStyle, light, teal):
    """v12 본문 - 숫자는 모두 res['evidence']['candidates'](= results.json 원본)에서만 읽는다."""
    ev = res["evidence"]
    clean = ev["clean"]
    cands = cd["candidates"]
    sel = next((c for c in cands if c["id"] == cd["selected"]), None)
    yrs = ev["options"]["payback_years"]
    eok = lambda mm_, k="krw_eok": "-" if not mm_ else f"{mm_[k][0]:.0f}~{mm_[k][1]:.0f}"
    img = lambda n, wr, hr: m["Image"](str(Path(res["_fig_dir"]) / n), width=W * mm, height=W * mm * hr / wr)
    fmt = lambda b: "-" if b["value"] is None else (f"{b['value'] * 100:.2f}%" if b["unit"] in ("질량분율", "비율") else
                                                    f"{b['value'] * 100:.0f}%" if b["unit"] == "×대표값" else f"{b['value']:.3g} {b['unit']}")
    bl, nc, jt, cp, up = (cd.get(k) if isinstance(cd.get(k), dict) and "error" not in cd.get(k) else None
                          for k in ("baseline_model", "necessity", "joint", "capacity", "upside"))
    out = []

    # ---- 1쪽: 조건부 추천 + 핵심 숫자 + 워터폴 + 확인 조건
    out += [Paragraph(f"조건부 추천 {sel['id'] if sel else '-'} — {sel['name'] if sel else ''}", st["title"]),
            P("같은 기준선(현재 공장 100 pt → 12 GWh 무개선 " f"{cd['baseline']['E_q_no_change']:.1f} pt, 목표 {cd['baseline']['target']:.0f} pt)·"
              "같은 근거·같은 열원(전기) 가정. 상태는 검증 완료 / 가정하 수치 충족 / 미확인 / 미달 네 가지이며 미확인은 통과가 아니다.", "sub"),
            Spacer(1, 3 * mm)]
    if sel:
        wf = (bl or {}).get("waterfall")
        kpis = [("원단위 절감 (대표)", pct(sel["saving"][1]), f"보수 {pct(sel['saving'][0])} ~ 낙관 {pct(sel['saving'][2])}"),
                ("12 GWh 총전력", f"{sel['E_typ']:.2f} pt", f"목표 {cd['baseline']['target']:.0f} pt 이하"),
                ("목표 여유", f"{sel['margin_pt']:+.2f} pt", "미정량 관리 전력이 이보다 크면 미달"),
                ("절감 구성", f"개조 {wf['tech_pp']:.2f}%p" if wf else "-", f"+ 고정부하 희석 {wf['dilution_pp']:.2f}%p (팀 가정 f)" if wf else "")]
        kt = Table([[[P(a, "kt"), P(b, "kv"), P(d, "ks")] for a, b, d in kpis]], colWidths=[W / 4 * mm] * 4)
        kt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), light), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LINEAFTER", (0, 0), (-2, -1), 2, colors.white), ("LINEABOVE", (0, 0), (-1, 0), 2, teal),
                                ("LEFTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        out.append(kt)
        rk = (cd.get("roadmap") or {}).get("kpi") if isinstance(cd.get("roadmap"), dict) else None
        if rk:
            ct = Table([[[P(rk["title"], "kt"), P(" · ".join(rk["lines"]), "ks")]]], colWidths=[W * mm])
            ct.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), light), ("LINEABOVE", (0, 0), (-1, 0), 2, colors.HexColor(AMBER)),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 3),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
            out += [Spacer(1, 1.5 * mm), ct]
        if wf:
            out.append(Paragraph(f"{pct(sel['saving'][1])}는 어디서 나오나 — 전부 비례 120 pt에서 E_new까지", st["h2"]))
            out.append(img("v12_waterfall.png", 6.6, 2.7))
            out.append(P(wf["note"] + " 원단위 %p = pt / 120.", "note"))
        out.append(Paragraph(f"조건부 추천을 현장에서 굳히려면 확인할 조건 ({sel['n_unk']}개)", st["h2"]))
        out.append(table(["축", "현재 상태", "확인 방법·통과 조건"], [[a["axis"], a["state"], a["status"]] for a in sel["axes"] if a["state"] != "가정하 수치 충족"],
                         [32, 20, 124]))
    out.append(m["PageBreak"]())

    # ---- 1-2쪽: 두 목표 신호등 · 금액 카드 · 기본 설계서 (v12.2)
    dz = cd.get("design") if isinstance(cd.get("design"), dict) and "error" not in cd.get("design") else None
    if dz:
        sg, mc = dz["signal"], dz["money"]
        out.append(Paragraph("두 목표 신호등 — 같은 조건에서 전력 -30%와 생산능력 +20%를 함께 판정", st["h2"]))
        out.append(table(["조건", "전력 -30%", "생산능력 +20%", "종합"], [[r["cond"], r["power"], r["capacity"], r["overall"]] for r in sg["rows"]],
                         [46, 26, 70, 34]))
        out.append(P(sg["note"], "note"))
        out.append(Paragraph("금액 카드 — 비교 기준 두 가지", st["h2"]))
        mt = Table([[[P(c["title"], "kt"), P(f"연 {c['krw_eok'][0]:.0f}~{c['krw_eok'][1]:.0f}억 원", "kv"), P(c["line"], "ks")] for c in mc["cards"]]],
                   colWidths=[W / 2 * mm] * 2)
        mt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), light), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LINEAFTER", (0, 0), (-2, -1), 2, colors.white), ("LINEABOVE", (0, 0), (-1, 0), 2, teal),
                                ("LEFTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        out += [mt, P(mc["note"], "note")]
        out.append(Paragraph("기본 설계서 — 계산 근거를 실제 고른 설계에 맞춤", st["h2"]))
        out.append(table(["개선안", "설계 고정 내용", "계산 근거", "시기", "통과 기준"], [[r["lever"], r["design"], r["basis"], r["when"], r["pass"]] for r in dz["spec"]],
                         [26, 52, 34, 18, 46]))
        out.append(P(dz["compare"]["protocol_basis"], "note"))
        out.append(m["PageBreak"]())

    # ---- 2쪽: 후보 비교
    out.append(Paragraph("A·B0·B1·B2·C 후보 비교 — 같은 기준선·같은 근거", st["h2"]))
    head = ["항목"] + [f"{c['id']}{' ★' if c['id'] == cd['selected'] else ''}\n{c['name']}" for c in cands]

    def row(lab, fn):
        return [lab] + [fn(c) for c in cands]
    rows = [
        row("역할 / 후보 여부", lambda c: c["role"] + ("" if c["eligible"] else f"\n(대기: {c['why_not']})")),
        row("고형분 → 총 용매량\n(기존 10 GWh=1)", lambda c: f"{c['solids'] * 100:.1f}% → {c['mass_balance']['solvent_vs_base']:.3f}"),
        row("건조 계통 절감(대표)", lambda c: pct(c["r_drying"][1])),
        row("원단위 절감\n대표(보수~낙관)", lambda c: f"{pct(c['saving'][1])}\n({pct(c['saving'][0])}~{pct(c['saving'][2])})"),
        row("E_new / 여유(대표)", lambda c: f"{c['E_typ']:.2f} pt\n{c['margin_pt']:+.2f} pt"),
        row("연 전력비 절감(대표)", lambda c: eok(c["money_typ"]) + " 억원"),
        row(f"허용 투자비 {'/'.join(str(n) + '년' for n in yrs)}", lambda c: "\n".join(eok(c["money_typ"] and {"krw_eok": c["money_typ"]["invest_eok"][n]}) for n in yrs) + " 억원"),
    ]
    for i, a in enumerate(cands[0]["axes"]):
        rows.append(row(a["axis"], lambda c, i=i: c["axes"][i]["state"] + (" (D등급 근거만)" if i == 1 and c["axes"][1].get("weak_ok") else "")))
    rows.append(row("품질 관문 수(안전)", lambda c: f"{c['n_gates']}건 (안전 {c['n_safety_gates']})"))
    rows.append(row("종합", lambda c: c["label"]))
    wc = (W - 26) / len(cands)
    out.append(table(head, rows, [26] + [wc] * len(cands)))
    b2 = (nc or {}).get("b2")
    _hsc = next((r["delta_pp"] for r in ((nc or {}).get("necessity") or {}).get("rows", []) if r["lever_id"] == "DRY-HSC"), None)
    out.append(P(f"차이는 건조 기술: B0(복사건조만)와 B1(고형분+복사건조)의 전력 차이는 {_hsc if _hsc is not None else 0:.2f}%p뿐이고, 고형분의 핵심 역할은 건조 처리능력"
                 "(질량수지만으로 체류 0.833배 안 건조 성립). B0는 등급 D 시간비 근거에서만 성립해 순위가 밀린다."
                 + (" " + b2["text"] + "." if b2 else ""), "body"))
    out.append(P(cd["note"] + f" 단가 {ev['options']['price_krw_per_kwh']:g}원/kWh. 허용 투자비 = 연 절감 × 연수(할인·설치비·정지손실·추가 OPEX 제외, 순편익 아님).", "note"))
    out.append(img("evidence_candidates.png", 6.8, 2.8))
    out.append(m["PageBreak"]())

    # ---- 3쪽: 기준선 카드 + 토네이도 + 금액
    if bl:
        out.append(Paragraph("기준선 카드 — 결론을 받치는 가정과 출처", st["h2"]))
        out.append(table(["가정", "값", "구분", "출처·대응"], [[r["item"], r["value"], r["origin"], r["source"]] for r in bl["card"]], [42, 56, 18, 60]))
        sv = bl["sensitivity"]
        out.append(Paragraph(f"기준선 민감도 — 가정을 하나씩 흔들 때 {sv['candidate']} 절감률 (기준 {pct(sv['base_saving'])})", st["h2"]))
        out.append(img("v12_tornado.png", 6.6, 2.2))
        out.append(m["PageBreak"]())
        out.append(Paragraph(f"기준선 민감도 표 · 문헌 사례 재계산 — {sv['candidate']}", st["h2"]))
        out.append(table(["가정", "구분", "하한 → 절감 / 추천", "상한 → 절감 / 추천", "판정 변화"],
                         [[r["label"], r["origin"], f"{r['lo']['value']} → {pct(r['lo']['saving'])} / {r['lo']['selected']}",
                           f"{r['hi']['value']} → {pct(r['hi']['saving'])} / {r['hi']['selected']}", "있음" if r["flips"] else "없음"]
                          for r in sv["rows"]], [44, 18, 46, 46, 22]))
        out.append(P(sv["note"] + " 고정부하 f를 전부 0으로 두는 극단은 스트레스 시나리오 S3(다음 쪽). 연 절감 금액 범위는 경제성 쪽.", "note"))
        lc = bl.get("literature_cases")
        if lc:
            out.append(Paragraph("조원 자료조사 값으로 다시 계산 (코드 그대로, 입력만 변경)", st["h2"]))
            out.append(table(["입력 변경", "출처", f"{lc['candidate']} 절감", "여유", "추천"],
                             [[r["label"], r["source"], pct(r["saving"], 2), f"{r['margin_pt']:+.2f} pt", r["selected"]] for r in lc["rows"]],
                             [78, 40, 20, 20, 18], num_cols=(2, 3)))
            out.append(P(lc["note"], "note"))

        out.append(m["PageBreak"]())

    # ---- 4쪽: 동시 불확실성 + 스트레스 + 단독 경계
    if jt:
        rg, ss = jt["region"], jt["stress"]
        out.append(Paragraph("동시 불확실성 — 문헌 효과 α와 관리 전력 P가 함께 나빠질 때", st["h2"]))
        out.append(img("v12_joint.png", 6.6, 2.8))
        out.append(P(f"{rg['formula']} (pt). 목표 {rg['target']:.0f} pt → 성립 조건 P ≤ {rg['target'] - rg['a']:.2f} + {rg['b']:.2f}·α. "
                     "P 허용치: " + " · ".join(f"α {a:g} → {p:.2f} pt" for a, p in rg["p_max"].items()) + ". " + rg["note"], "note"))
        out.append(Paragraph("스트레스 시나리오", st["h2"]))
        out.append(table(["ID", "시나리오", "원단위 절감", "E (pt)", "여유 (pt)", "판정"],
                         [[r["id"], r["scenario"], pct(r["saving"], 2), f"{r['E']:.2f}", f"{r['margin_pt']:+.2f}", r["verdict"]] for r in ss["rows"]],
                         [10, 66, 24, 22, 24, 20], num_cols=(2, 3, 4)))
        out.append(P(ss["note"], "note"))
    out.append(Paragraph(f"단독 실패 경계 — {cd['selected']} (다른 입력 고정)", st["h2"]))
    out.append(table(["경계", "값", "의미"], [[b["kind"], fmt(b), b["text"]] for b in cd["boundaries"]], [34, 20, 122]))
    out.append(Paragraph("추천 전환 조건", st["h2"]))
    for t in cd["switch"]:
        out.append(P("· " + t, "cell"))
    out.append(m["PageBreak"]())

    # ---- 5쪽: 처리능력 통합 + 레버 필요성
    if cp:
        pl = cp["plant"]
        out.append(Paragraph(f"공장 처리능력 = 가장 약한 공정 — {pl['candidate']}: {pl['plant']:.3f}배 (병목: {pl['bottleneck']})", st["h2"]))
        out.append(table(["공정", "처리능력(배)", "근거"], [[k, f"{v:.3f}", pl["bases"][k]] for k, v in pl["caps"].items()]
                         + [["공장", f"{pl['plant']:.3f}", f"목표 {res['inputs']['q']:g}배 대비 {pl['margin']:+.3f}"]], [30, 30, 116], num_cols=(1,)))
        out.append(table(["필요 최소값", "값"], [[k, f"{v * 100:.2f}%" if k == "승인 슬롯" else f"{v:.3f}"] for k, v in pl["required"].items()], [80, 96]))
        y = cp["yield"]
        out.append(P(f"후보별 공장 처리능력: " + " · ".join(f"{k} {v['plant']:.3f}({v['bottleneck']})" for k, v in cp["by_candidate"].items())
                     + f". 수율 {y['y']:g} 시나리오: 양품 {y['q_good']:g}배 출하에 투입 {y['q_load']:.3f}배 → 절감 {pct(y['saving'], 2)}, 여유 {y['margin_pt']:+.2f} pt. "
                     + pl["note"], "note"))
    if nc:
        ne = nc["necessity"]
        out.append(Paragraph(f"레버 필요성 — {ne['candidate']}에서 하나씩 뺄 때", st["h2"]))
        out.append(table(["레버", "변경 유형", "빼면 절감 감소", "바뀌는 축", "관문 수 감소", "분류"],
                         [[_nm(clean, r["lever_id"]), r["change_type"], f"{r['delta_pp']:.2f}%p", ", ".join(r["axes_changed"]) or "-",
                           str(r["gates_delta"]), r["class"]] for r in ne["rows"]], [48, 16, 18, 32, 14, 48]))
        dr_ = [r["dual_role"] for r in ne["rows"] if r.get("dual_role")]
        if dr_:
            out.append(P("화성 단축의 이중 역할: " + dr_[0] + ". 화성 단축 없이는 +20% 증산이 불가능하다.", "body"))
        co = ne["core"]
        out.append(P(f"핵심+처리능력 레버만({', '.join(_nm(clean, l) for l in co['levers'])}): 절감 {pct(co['saving'][1])}, 관문 {co['n_gates']}건(안전 {co['n_safety_gates']}) "
                     f"vs 전체 {pct(ne['full']['saving'][1])}, 관문 {ne['full']['n_gates']}건. " + ne["note"], "note"))
        stc = nc.get("structure")
        if stc:
            out.append(P("건조 구조 가정: M1(기본) " + pct(stc["M1"]) + " / M2(복사 효과가 열 관련 비중 h에만) "
                         + " · ".join(f"h {x['h']:g} → {pct(x['saving'])}" for x in stc["M2"])
                         + (f", 판정 경계 h* = {stc['h_star']:.3f}" if stc["h_star"] else "") + f" / M3(고형분 전력 효과 0) {pct(stc['M3'])}.", "note"))
    out.append(m["PageBreak"]())

    # ---- 6쪽: 열원 + 단계별(q_t) + 역산
    hs = cd.get("heat")
    if hs:
        out.append(Paragraph("열원 민감도 — 후보별로 자기 구성 그대로 열원만 바꿔 재계산", st["h2"]))
        idx = {(r["case"], r["candidate"]): r for r in hs["rows"]}
        hrows = []
        for c in cands:
            cells = [c["id"]]
            for case in hs["cases"]:
                r = idx.get((case, c["id"]))
                cells.append("-" if not r else
                             f"{pct(r['saving'][1])}{' ★' if r['selected'] else ''} [{r['energy_state']}]\n"
                             f"건조 {sys_change(r['r_drying'])}\n드라이룸 {sys_change(r['r_dryroom'])}")
            hrows.append(cells)
        out.append(table(["후보"] + hs["cases"], hrows, [14] + [(W - 14) / len(hs["cases"])] * len(hs["cases"])))
        out.append(P(hs["note"] + " ★ = 그 열원 조건의 추천 후보.", "note"))
    stt = (cp or {}).get("stages")
    if stt:
        out.append(Paragraph(f"단계별 누적 — 연차별 생산비 q_t 반영 ({stt['candidate']})", st["h2"]))
        out.append(table(["단계", "추가 레버", "공장 처리능력\n(병목)", "q_t에서 절감\n(희석 %p)", "승인 슬롯 시", "12 GWh 도달 시", "기여 0 레버"],
                         [[x["stage"], ", ".join(_nm(clean, l) for l in x["added"]) or "-", f"{x['capacity']:.3f}\n({x['bottleneck']})",
                           f"{pct(x['at_q_t']['saving'], 2)} (q {x['q_t']:.3f})\n희석 {x['at_q_t']['dilution_pp']:.2f}%p",
                           f"{pct(x['at_q_if_slots']['saving'], 2)} (q {x['q_t_if_slots']:.3f})", pct(x["at_q12"]["saving"], 2),
                           ", ".join(x["zero_contrib"]) or "-"] for x in stt["stages"]], [20, 46, 18, 28, 22, 16, 26]))
        out.append(P(stt["note"], "note"))
    rv = cd.get("reverse_models")
    if rv:
        out.append(Paragraph("단일 계통 역산 — 세 모델 구분", st["h2"]))
        f1 = lambda x: "-" if x is None else f"{x * 100:.1f}%" + (" (불가)" if x > 1 else "")
        out.append(table(["계통", "w / f", f"① 전부 비례 ({rv['gap_linear']:.2f} pt)", f"② 엔진 무개선 ({rv['gap_engine']:.2f} pt)",
                          "③ 후보 A 후 (" + (f"{rv['gap_after_A']:.2f} pt)" if rv["gap_after_A"] is not None else "-)")],
                         [[r["system"], f"{r['w']:g}% / {r['f']:g}", f1(r["linear"]), f1(r["engine"]), f1(r["after_A"])] for r in rv["rows"]],
                         [24, 28, 42, 42, 40], num_cols=(2, 3, 4)))
        out.append(P(rv["note"], "note"))
    out.append(m["PageBreak"]())

    # ---- 7쪽: 검증 우선순위 + 관문 + 검출력
    out.append(Paragraph("무엇을 먼저 확인하는가 — 검증 우선순위 (시험 결과별 판정)", st["h2"]))
    pr = cd["priority"]
    out.append(table(["순위", "확인할 질문", "판정 영향", "시험(기간·비용 가정)", "시험 결과별 판정 (나쁠 때 / 좋을 때)"],
                     [[str(t["priority"]) if t["impact_rank"] < 9 else "-", t["question"], t["impact"], f"{t['how']}\n({t['period']} · {t['cost']})", t["text"]]
                      for t in pr["tests"]], [9, 38, 24, 34, 71]))
    out.append(P(pr["note"], "note"))
    mand = pr["mandatory"]
    if mand:
        n_s = sum(x["safety"] for x in mand)
        out.append(Paragraph(f"판정 영향과 무관하게 먼저 하는 안전·품질 관문 ({len(mand)}건, 안전 관련 {n_s}건) — 상위 6건(전체 목록 kb_quality_gates.csv)", st["h2"]))
        out.append(table(["FMEA", "레버", "안전", "관문", "상태"],
                         [[x["fmea_id"], _nm(clean, x["lever_id"]), "예" if x["safety"] else "-", x["gate"], x["status"]] for x in mand[:6]],
                         [16, 34, 10, 98, 18]))
    out.append(table(["독립 결함 양성 표본 n (미검출 0건)", *[str(d["n_defect_samples"]) for d in cd["detection"]]],
                     [["미검출 확률 단측 95% 상한", *[f"{d['miss_upper'] * 100:.2f}%" for d in cd["detection"]]]],
                     [56] + [24] * len(cd["detection"])))
    out.append(P(f"상한 = 1 - 0.05^(1/n) (정확 이항). 상한 1%를 보이려면 결함 양성 표본 {cd['n_for_1pct']}개. 정상 셀 수가 아니라 결함 양성 셀 수다.", "note"))
    out.append(m["PageBreak"]())

    # ---- 8쪽: 판정 미반영 추가 여유 (섀도 모드·what-if)
    if up:
        sh, wi = up["shadow"], up["whatif"]
        out.append(Paragraph("검증 통과 시 추가 이득 — 기본 결론 미반영", st["h2"]))
        out.append(Paragraph("에이징 섀도 모드 — 14일 출하 판정은 유지하고 조기 측정을 병행해 단축 근거를 무위험으로 축적", st["h2"]))
        out.append(table(["단계", "운영", "다음 단계 진입 관문"], [[x["stage"], x["what"], x["gate"]] for x in sh["stages"]], [30, 80, 66]))
        if sh.get("n_note"):
            out.append(P(sh["n_note"], "note"))
        out.append(table(["판정 기간(일)", "필요 슬롯", "리드타임(화성+에이징)", "슬롯 무증설 가능"],
                         [[f"{x['days']:g}", f"{x['slot_need'] * 100:+.2f}%", f"{x['lead_time_h']:.0f} h", "예" if x["no_slot_ok"] else "아니오"] for x in sh["rows"]],
                         [36, 40, 56, 44], num_cols=(1, 2)))
        ex = sh.get("natural_example")
        ptab = sh.get("period_table")
        if ptab:
            out.append(table([f"불량률 p (하루 {ptab['cells_per_day'][0]:,}~{ptab['cells_per_day'][1]:,}셀)", "결함 양성 299개 확보 기간", "구분"],
                             [[r["label"], f"{r['days'][0]:.1f}~{r['days'][1]:.1f}일", r["kind"]] for r in ptab["rows"]], [66, 60, 50]))
            out.append(P(f"{ptab['formula']}. 하루 셀 수: {ptab['source']}. {ptab['note']}", "note"))
            ex = None
        if ex:
            out.append(P(f"자연 결함만으로 모으면: 결함률 {ex['defect_rate'][0] * 1e6:g}~{ex['defect_rate'][1] * 1e6:g} ppm({ex['source']}), "
                         f"하루 {ex['cells_per_day']:,}셀{'(계산 예시 - C사 값 아님)' if ex['is_example'] else ''} → {ex['weeks_natural'][0]:.0f}~{ex['weeks_natural'][1]:.0f}주. "
                         f"(약 {ex['weeks_natural'][0] / 52:.1f}~{ex['weeks_natural'][1] / 52:.1f}년) - 3년 로드맵 안에서 불확실하므로 인위 내부단락 셀"
                         "(NREL/NASA 내부단락 유발 장치 등)로 결함 양성 표본을 병행 확보한다.", "body"))
        out.append(P(f"필요 결함 양성 표본 {sh['n_required']}개(미검출률 상한 {sh['target'] * 100:g}%). 현재 리드타임 {sh['base_lead_time_h']:.0f} h. "
                     + (f"축적 기간 약 {sh['weeks']:.1f}주." if sh["weeks"] else "축적 기간 계산에 필요한 입력: " + "; ".join(sh["need_inputs"]) + ".")
                     + " " + sh["note"], "note"))
        out.append(Paragraph("근거가 생기면 추가되는 여유 (what-if)", st["h2"]))
        out.append(table(["항목", "추가 여유 (pt)", "원단위 (%p)", "편입 방법"], [[r["item"], f"{r['pt']:.2f}", f"{r['pp']:.2f}", r["how"]] for r in wi["rows"]],
                         [70, 22, 22, 62], num_cols=(1, 2)))
        out.append(P("계통별 1%p 절감당 여유: " + " · ".join(f"{r['system']} {r['pt_per_pp']:.3f} pt" for r in wi["per_point"]) + ". " + wi["label"] + ".", "note"))
    hm = cd.get("heat_map") if isinstance(cd.get("heat_map"), dict) and "error" not in cd.get("heat_map") else None
    if hm:
        if up:
            out.append(m["PageBreak"]())
        out.append(Paragraph("공정 간 열 통합 지도 — 열원·열수요 온도 매칭 (전력 절감 0으로 고정)", st["h2"]))
        out.append(img("v12_heatmap.png", 6.6, 2.6))
        out.append(table(["열원", "열수요", "공정 간", "판정", "기존 레버", "오염"],
                         [[r["source_name"], r["demand_name"], "예" if r["cross_process"] else "-", r["how"], r["lever"], r["contaminant"]]
                          for r in hm["matches"] if not r["how"].startswith("연결 불가")], [40, 34, 12, 56, 16, 18]))
        out.append(P(f"최소 접근 온도차 {hm['dt_min']:g}°C(팀 가정). " + hm["note"] + " " + hm["label"] + ".", "note"))
    if up or hm:
        out.append(m["PageBreak"]())
    eco = cd.get("economics") if isinstance(cd.get("economics"), dict) and "error" not in cd.get("economics") else None
    if eco:
        le, ro = eco["levers"], eco["rollout"]
        out.append(Paragraph("레버별 경제성 — 한계 기여와 손익분기 투자비 (견적 없음)", st["h2"]))
        e2 = lambda t: "-" if not t else f"{t[0]:.0f}~{t[1]:.0f}"
        out.append(table(["레버", "기여(%p / pt)", "연 절감(억원)", f"손익분기 {le['years'][0]}년 / {le['years'][-1]}년(억원)", "상태"],
                         [[_nm(clean, r["lever_id"]), f"{r['delta_pp']:.2f} / {r['pt']:.2f}", e2(r["krw_eok"]),
                           (f"{e2(r['breakeven_eok'][le['years'][0]])} / {e2(r['breakeven_eok'][le['years'][-1]])}" if r["breakeven_eok"] and r["pt"] > 1e-9 else "-"),
                           r["status"] + (f" (회수 {r['payback_years'][0]:.1f}~{r['payback_years'][1]:.1f}년)" if r["payback_years"] else "")]
                          for r in le["rows"]], [52, 22, 22, 36, 44], num_cols=(1, 2, 3)))
        out.append(P(le["note"] + f" 단가 {le['price']:g}원/kWh, 연간 전력 500~650 GWh.", "note"))
        if bl:
            mr = bl["money"]
            out.append(Paragraph("연 전력비 절감 범위 (판정과 무관)", st["h2"]))
            out.append(table(["공장 원단위 kWh/kWh_cell", "연간 전력 GWh"] + [f"{p:g}원/kWh" for p in mr["prices"]],
                             [[str(r["intensity"]), f"{r['annual_gwh']:.0f}"] + [f"{r[f'krw_eok_{p:g}']:.0f} 억원" for p in mr["prices"]] for r in mr["rows"]],
                             [44, 36, 48, 48], num_cols=(1, 2, 3)))
            out.append(P(mr["note"], "note"))
        out.append(m["PageBreak"]())
        out.append(Paragraph("3년 전개 일정 (간트) — 변경 유형 기준 팀 가정", st["h2"]))
        out.append(img("v12_gantt.png", 6.6, 3.0))
        out.append(P(ro["note"] + (" 로드맵 검사 경고 " + str(len(ro["warnings"])) + "건: " + "; ".join(ro["warnings"]) if ro["warnings"]
                                   else " 로드맵 검사: 기여 0 레버에 절감 목표가 붙은 경우 0건."), "note"))
        out.append(m["PageBreak"]())
    rm = cd.get("roadmap") if isinstance(cd.get("roadmap"), dict) and "error" not in cd.get("roadmap") else None
    if rm:
        sp, rc = rm["space"], rm["reach"]
        out.append(Paragraph("생산능력 +20% — 남은 병목은 에이징 보관 공간 하나 (공간 수지)", st["h2"]))
        out.append(P(sp["sentence"], "body"))
        out.append(table(["항목", "값", "계산·근거"],
                         [["필요 승인 슬롯", f"+{sp['slot_need'] * 100:.2f}%", sp["formula"] + " (현재 사용률·계획 상한은 팀 가정)"],
                          ["공장 면적 상한", f"약 {sp['area_upper'] * 100:.1f}%", sp["area_note"]],
                          ["화성 동시 재공(16 h)", f"{sp['formation_wip']:.2f}배", f"리틀의 법칙 → 화성 구역 {sp['formation_spare'] * 100:.0f}% 여유"]],
                         [34, 24, 118]))
        out.append(table(["", "확보 후보", "원리", "전제 조건", "시기", "근거·제약"],
                         [[o["no"], o["name"], o["how"], o["depends"], o["when"], o["basis"]] for o in sp["options"]],
                         [6, 26, 56, 26, 16, 46]))
        out.append(P(sp["fallback"] + ". " + sp["note"], "note"))
        if sp.get("ledger"):
            out.append(table(["공간 장부", "값", "무엇으로 정하나", "상태"], [[r["col"], r["value"], r["how"], r["status"]] for r in sp["ledger"]],
                             [22, 24, 104, 26]))
            out.append(P(sp["ledger_note"], "note"))
        out.append(Paragraph("연차별 두 목표 도달도 — 전력 원단위와 생산비", st["h2"]))
        out.append(img("v12_reach.png", 6.6, 2.6))
        out.append(table(["단계", "전력 절감 (공간 미확보 / 확보 시)", "생산비 q_t (미확보 / 확보 시)", "+20% 대비 도달 (미확보 / 확보 시)"],
                         [[r["stage"], f"{pct(r['power_no_slot'], 2)} / {pct(r['power_if_slot'], 2)}", f"{r['q_no_slot']:.3f} / {r['q_if_slot']:.3f}",
                           f"{r['cap_reach_no_slot'] * 100:.0f}% / {r['cap_reach_if_slot'] * 100:.0f}%"] for r in rc["rows"]], [30, 52, 48, 46]))
        out.append(P(rc["note"], "note"))
        out.append(m["PageBreak"]())
        hz, im = rm["horizon"], rm["impact"]
        out.append(Paragraph("단기·중기·장기 — 근거의 성격대로 분류, 검증 방법·통과 기준", st["h2"]))
        out.append(table(["개선안", "한계 기여", "근거 성격", "분류 · 시기", "검증 방법", "통과 기준"],
                         [[r["name"], "-" if not r["delta_pp"] else f"{r['delta_pp']:.2f}%p", r["nature"], f"{r['horizon']}\n{r['when']}", r["method"], r["pass"]]
                          for r in hz["rows"]], [24, 14, 34, 30, 38, 36]))
        out.append(P(hz["note"] + " 적용 순서: " + " → ".join(hz["order"]) + ".", "note"))
        out.append(Paragraph("신규라인·신기술 중장기 트랙 (계산 미반영, 정성)", st["h2"]))
        out.append(table(["기술", "무엇이 달라지나", "팀 KB 근거", "C사 적용 조건"], [[r["tech"], r["change"], r["kb"], r["cond"]] for r in hz["newline"]],
                         [32, 56, 46, 42]))
        out.append(m["PageBreak"]())
        out.append(Paragraph("영향평가 매트릭스 — 상·중·하 (수행과제 4)", st["h2"]))
        out.append(table(["개선안", "생산능력", "전력(한계 기여)", "투자 규모", "적용 난이도", "수명·검출력 위험", "안전 위험", "시기"],
                         [[r["name"], r["capacity"], r["power"], r["capex"], r["difficulty"], r["quality"], r["safety"], r["horizon"]] for r in im["rows"]],
                         [24, 18, 18, 44, 16, 20, 16, 20]))
        out.append(P(im["rule"] + " " + im["note"], "note"))
        dp = rm.get("departments")
        if dp:
            out.append(Paragraph("4개 부서 요구에 대한 답", st["h2"]))
            out.append(table(["부서", "요구", "제안의 답", "근거 위치"], [[r["dept"], r["ask"], r["answer"], r["where"]] for r in dp["rows"]],
                             [18, 36, 96, 26]))
            out.append(P(dp["note"], "note"))
        out.append(m["PageBreak"]())
    if dz:
        cmp_ = dz["compare"]
        out.append(Paragraph("설계 고정 — 기술군 중앙값과 무엇이 달라지나 (왜 숫자를 낮췄나)", st["h2"]))
        rows_ = cmp_["rows"]
        okm = lambda r, k, x: f"{pct(x, 2)} {'충족' if r['ok'][k] else '미달'}"
        spec_rows = [
            ("기본 (보수~낙관)", lambda r: f"{pct(r['saving'][1], 2)} · 여유 {r['margin_pt']:+.2f} pt\n({pct(r['saving'][0])}~{pct(r['saving'][2])})"),
            ("문헌 효과 경계 α*", lambda r: f"{r['alpha_star']:.3f}"),
            ("문헌 90% + 관리 전력 4 pt", lambda r: okm(r, "s1", r["s1"])),
            ("고정부하 f 전부 0", lambda r: okm(r, "f0", r["f0"])),
            ("2·3년차, 공간 미확보(q 1.056)", lambda r: okm(r, "y2_no_slot", r["y2_no_slot"])),
            ("드라이룸 재생 가스", lambda r: okm(r, "dryroom_gas", r["dryroom_gas"])),
            ("건조 가스", lambda r: okm(r, "drying_gas", r["drying_gas"])),
            ("12 GWh 총전력 E", lambda r: f"{r['E']:.2f} pt"),
            ("연 전력비: 현재 대비 / 무개선 대비", lambda r: f"{r['money_now'][0]:.0f}~{r['money_now'][1]:.0f} / {r['money_nochange'][0]:.0f}~{r['money_nochange'][1]:.0f}억"),
        ]
        out.append(table(["조건 (" + (rows_[0]["candidate"] if rows_ else "") + ")"] + [r["label"] + (" ★공식" if r["official"] else "") for r in rows_],
                         [[lab] + [fn(r) for r in rows_] for lab, fn in spec_rows], [44] + [(W - 44) / max(len(rows_), 1)] * len(rows_)))
        out.append(P(cmp_["note"], "note"))
        out.append(P(cmp_["protocol_basis"], "note"))
        out.append(P("선택 규칙: 서로 다른 기술의 중앙값 대신 팀이 실제로 고른 설계(부분 국소화 · Weng 계열 화성 · NIR)의 근거만 쓴다. "
                     "숫자보다 설계와 근거의 일치를 택한 것이며, 기술군 중앙값은 이 표에서만 비교용으로 남긴다.", "body"))
        out.append(m["PageBreak"]())
    return out


# ------------------------------------------------------------------ PDF
def build_pdf(res, out_path, fig_dir, run_info):
    m = R._pdf_imports()
    colors, mm, A4 = m["colors"], m["mm"], m["A4"]
    Paragraph, Spacer, Table, TableStyle = m["Paragraph"], m["Spacer"], m["Table"], m["TableStyle"]
    PS = m["ParagraphStyle"]
    pdfmetrics = m["pdfmetrics"]
    pdfmetrics.registerFont(m["TTFont"]("NG", str(R.FONT_REG)))
    pdfmetrics.registerFont(m["TTFont"]("NG-B", str(R.FONT_BOLD)))
    pdfmetrics.registerFontFamily("NG", normal="NG", bold="NG-B", italic="NG", boldItalic="NG-B")
    navy, teal, light = colors.HexColor(R.NAVY), colors.HexColor(R.TEAL), colors.HexColor(R.LIGHT)
    st = {
        "title": PS("t", fontName="NG-B", fontSize=20, leading=25, textColor=navy, spaceAfter=2),
        "sub": PS("s", fontName="NG", fontSize=9.5, leading=13, textColor=colors.HexColor(R.GRAY)),
        "h2": PS("h", fontName="NG-B", fontSize=12, leading=16, textColor=navy, spaceBefore=6, spaceAfter=3),
        "body": PS("b", fontName="NG", fontSize=9.5, leading=13.5),
        "cell": PS("c", fontName="NG", fontSize=8, leading=10.3),
        "cellb": PS("cb", fontName="NG-B", fontSize=8, leading=10.3, textColor=colors.white),
        "num": PS("n", fontName="NG", fontSize=8, leading=10.3, alignment=m["TA_RIGHT"]),
        "numh": PS("nh", fontName="NG-B", fontSize=8, leading=10.3, textColor=colors.white, alignment=m["TA_RIGHT"]),
        "note": PS("f", fontName="NG", fontSize=8, leading=10.6, textColor=colors.HexColor(R.GRAY)),
        "kt": PS("kt", fontName="NG", fontSize=8.5, leading=11, textColor=colors.HexColor(R.GRAY)),
        "kv": PS("kv", fontName="NG-B", fontSize=14, leading=18, textColor=navy),
        "ks": PS("ks", fontName="NG", fontSize=8.2, leading=10.6),
    }
    esc = lambda s: escape(safe_text(s))
    P = lambda s, k="cell": Paragraph(esc(s).replace(chr(10), "<br/>"), st[k])
    W = 210 - 34

    def table(head, rows, widths, num_cols=()):
        data = [[Paragraph(esc(h), st["numh"] if i in num_cols else st["cellb"]) for i, h in enumerate(head)]]
        for r in rows:
            data.append([Paragraph(esc(c).replace(chr(10), "<br/>"), st["num"] if i in num_cols else st["cell"])
                         for i, c in enumerate(r)])
        t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1, splitByRow=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), navy), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, light]),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#C9D6D8")),
            ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
        return t

    ev = res["evidence"]
    res = {**res, "_fig_dir": fig_dir}
    c = ev["cases"]
    opts = ev["options"]
    rec = next((r for r in opts["rows"] if r["add"] == ev["recommended"]["add"] and r["option"] != "v10 가정 경로(근거 미검증)"), None)
    eok = lambda m, k="krw_eok": "-" if not m else f"{m[k][0]:.0f}~{m[k][1]:.0f}"
    story = []
    cd = ev.get("candidates")
    if cd:
        story += candidate_pages(res, cd, st, P, table, m, W, esc, Paragraph, Spacer, mm, colors, Table, TableStyle, light, teal)
    story += [Paragraph("부록 A. 이전 모델 — 기존 레버 조합 엔진 출력", st["title"]),
              P("참고용 기록. 고형분을 문헌 절감률로 곱하던 이전 방식과 레버 조합 탐색 결과로, 본문(A·B0·B1·B2·C 후보 모델) 수치를 대체하지 않는다. "
                "보고서·PPT 숫자는 본문과 results.json에서만 가져온다.", "sub"),
             P(f"근거 FMEA 데이터셋 {ev['counts']['sources']}개 자료 · 정량효과 {ev['counts']['effects']}건"
               f"(계산 사용 {ev['counts']['calc']} · 참고 {ev['counts']['ref']} · 제외 {ev['counts']['excl']}) · 근거FMEA {ev['counts']['fmea']}건. "
               "문헌 수치를 명시된 환산·결합 가정으로 비교 (가정 기반 조건부 결과)", "sub"),
             Spacer(1, 4 * mm)]
    prod = ev.get("production_rec") or ev["production"]
    ov = ev.get("overall") or {"label": ev["recommended"]["verdict"]}
    _adds = ev["recommended"]["add"] + (ev["recommended"].get("production_add") or [])
    add_txt = "+" + " + ".join(_adds) if _adds else "추가 레버 없음"
    kpis = [("종합 판정 (추천 조합)", ov["label"].split(" - ")[0],
             (ov["label"].split(" - ")[1] + " · " if " - " in ov["label"] else "") + add_txt),
            ("원단위 절감 (추천·대표)", pct(rec["saving"][1]) if rec else "-",
             (f"{ev['recommended']['verdict']} · 보수 {pct(rec['saving'][0])} ~ 낙관 {pct(rec['saving'][2])}") if rec else ""),
            ("증산 +20% 판정", prod["verdict"].split(" - ")[0], prod["verdict"].split(" - ")[1] if " - " in prod["verdict"] else prod["aging_status"]),
            ("연간 전력비 절감 (추천·대표)", (eok(rec["money_typ"]) + " 억원") if rec else "-", f"단가 {opts['price_krw_per_kwh']:g}원/kWh(입력값)")]
    kt = Table([[[P(a, "kt"), P(b, "kv"), P(d, "ks")] for a, b, d in kpis]], colWidths=[W / 4 * mm] * 4)
    kt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), light), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LINEAFTER", (0, 0), (-2, -1), 2, colors.white), ("LINEABOVE", (0, 0), (-1, 0), 2, teal),
                            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story += [kt, Paragraph("결론", st["h2"]), Paragraph(esc(ev["conclusion"]), st["body"])]
    story.append(Paragraph("개선안 비교표 (같은 기준·같은 근거 데이터셋)", st["h2"]))
    yrs = opts["payback_years"]
    crow = []
    for r in opts["rows"]:
        sv = r["saving"]
        crow.append([r["option"].replace("근거: ", ""), r["verdict"],
                     pct(sv[1]) if sv[0] is None else f"{pct(sv[1])}\n({pct(sv[0])}~{pct(sv[2])})",
                     eok(r["money_typ"]), " / ".join(eok(r["money_typ"] and {"krw_eok": r["money_typ"]["invest_eok"][n]}) for n in yrs),
                     short_prod(r["production"]), "-" if r["risks"] is None else f"{r['risks']}(안전 {r['safety_risks']})",
                     r["difficulty"], r["evidence"]])
    story.append(table(["개선안", "전력 판정", "원단위 절감\n대표(보수~낙관)", "연 절감\n(억원)",
                        f"허용 투자비\n{'/'.join(str(n) + '년' for n in yrs)}(억원)", "증산", "품질 위험\n(FMEA)", "최대 변경", "근거"],
                       crow, [27, 20, 21, 17, 27, 20, 14, 13, 17], num_cols=(3, 4)))
    pe = opts["plant"]
    story.append(P(opts["note"] + (f" 공장 연간 전력 {pe['gwh_lo']:.0f}~{pe['gwh_hi']:.0f} GWh = 전력 원단위 {pe['intensity_lo']:g}~{pe['intensity_hi']:g} kWh/kWh "
                                   f"({', '.join(pe['ids'])}) × {pe['capacity_gwh']:g} GWh." if pe else " 공장 전력 원단위 근거 없음 - 금액 환산 생략."), "note"))
    story.append(m["PageBreak"]())
    if ev.get("overall"):
        story.append(Paragraph("기존 레버 조합의 종합 판정 — 5개 축, 4상태 (미확인은 통과가 아님)", st["h2"]))
        ax_rows = []
        for a_rec, a_sel in zip(ev["overall"]["axes"], ev["overall_selected"]["axes"]):
            ax_rows.append([a_rec["axis"], f"[{a_sel['state']}] {a_sel['status']}", f"[{a_rec['state']}] {a_rec['status']}"])
        ax_rows.append(["종합", ev["overall_selected"]["label"], ev["overall"]["label"]])
        story.append(table(["축", "현재 선택(v10 레버)", "추천 조합(+" + "+".join(_adds) + ")"], ax_rows, [30, 70, 76]))
        story.append(P("상태: 검증 완료(실측·승인) / 가정하 수치 충족(문헌·가정 범위에서 계산상 충족) / 미확인 / 미달. "
                       "판정 우선순위: 품질 불합격 → 에너지 → 건조 → 화성 → 에이징 → 미확인(건조 속도·품질) → 조건부. "
                       "품질 관문은 확인 당시 공정 조건과 현재 입력이 다르면 '재검증 필요'로 돌린다.", "note"))
    story.append(Paragraph("추천이 바뀌는 조건 (결정적 역산)", st["h2"]))
    story.append(table(["구분", "계통", "조건"], [[t["kind"], t["system"], t["text"]] for t in ev["thresholds"]], [32, 16, 128]))
    story.append(Paragraph("3년 적용 순서 (변경 유형으로 단계 구분, 근거FMEA 품질 관문을 다음 단계 진입 조건으로 사용)", st["h2"]))
    rm = []
    for stg in ev["roadmap"]:
        lv = "\n".join(f"{l['lever_id']} {l['name']}" + ("" if l["has_evidence"] else " [근거 없음]") for l in stg["levers"]) or "-"
        gates = "\n".join(f"· {g}" for l in stg["levers"] for g in l["gates"][:1]) or "-"
        rm.append([f"{stg['year']}\n{stg['title']}", lv, "\n".join(f"· {a}" for a in stg["actions"]), gates, stg["exit"]])
    story.append(table(["단계", "적용 레버", "주요 활동", "품질 관문(레버별 대표)", "다음 단계 진입 조건"], rm, [24, 38, 44, 42, 28]))
    story.append(P(f"증산 점검: {prod['note']}", "note"))
    story.append(m["PageBreak"]())
    sv = ev.get("sensitivity")
    if sv:
        story.append(Paragraph("그림 E3 — 결합 효과·관리부담 경계도 (추천 조합)", st["h2"]))
        story.append(m["Image"](str(Path(fig_dir) / "evidence_sensitivity.png"), width=W * mm, height=W * mm * 2.9 / 6.6))
        f = lambda x: "-" if x is None else f"{x * 100:.0f}%"
        g = lambda x: "-(κ에서 이미 미달)" if x is None else f"{x:.2f} pt"
        story.append(table(["항목", "값", "해석"], [
            ["결합 계통", ", ".join(sv["multi_systems"]) or "없음", "한 계통에서 서로 다른 그룹 레버를 함께 쓰는 곳 (κ가 작용하는 곳)"],
            ["대표 기준 최소 κ", f(sv["kappa_min_typ"]), "결합 추가 이득이 이 비율 이상 남아야 대표값으로 목표 충족 (P=0)"],
            ["보수 기준 최소 κ", f(sv["kappa_min_cons"]), "보수값(근거 하한+부담 상한)으로도 충족하려면 필요한 κ"],
            ["허용 추가 부담 (κ=1)", g(sv["p_max"][1.0]), "독립 결합일 때 대표 기준을 지키는 최대 미정량 관리 전력"],
            ["허용 추가 부담 (κ=0.75)", g(sv["p_max"][0.75]), "결합 이득이 4분의 1 줄어들 때"],
            ["허용 추가 부담 (κ=0.5)", g(sv["p_max"][0.5]), "결합 이득이 절반만 남을 때"]], [38, 28, 110]))
        story.append(P(sv["note"] + " 색은 계산상 절감률이며 확률·신뢰구간이 아니다. 격자 데이터: kb_decision_boundary.csv.", "note"))
        story.append(m["PageBreak"]())
    story.append(Paragraph("그림 E1 — 계통별 근거 범위 vs v10 가정 vs 단독 보완 요구", st["h2"]))
    img = lambda n, h=2.9: m["Image"](str(Path(fig_dir) / n), width=W * mm, height=W * mm * h / 6.6)
    story += [img("evidence_systems.png"),
              P("근거 범위는 데이터셋의 계산 사용 행만으로 만든 보수(최솟값)~낙관(최댓값)이며 확보된 성능이 아니다. "
                "같은 중복방지그룹 레버는 곱하지 않고 가장 큰 단일 값만 쓰며, 다른 그룹은 독립 가정으로 곱한다.", "note")]
    rows = [[r["system"], pct(r["v10_r"], 0), "-" if r["status"].startswith("변경") else f"{pct(r['lo'])} ~ {pct(r['hi'])}",
             "-" if r["status"].startswith("변경") else pct(r["typ"]), r["status"]] for r in ev["v10_check"]]
    story += [Paragraph("v10 가정 검증", st["h2"]),
              table(["계통", "v10 가정 r", "근거 범위", "근거 대표", "판정"], rows, [22, 22, 40, 22, 70], num_cols=(1, 3)),
              m["PageBreak"]()]

    # ---- 2쪽: 경우별 결과·조합 탐색·레버 판정표
    story.append(Paragraph("경우별 결과 (보수: 근거 하한+부담 상한 / 대표 / 낙관: 근거 상한+부담 하한)", st["h2"]))
    rows = [[{"conservative": "보수", "typical": "대표", "optimistic": "낙관"}[k], *[pct(c[k]["r"][i], 1) for i in range(5)],
             f"{c[k]['p_add']:.2f}", f"{c[k]['E_total']:.2f}", pct(c[k]["saving"], 2), f"{c[k]['gap']:+.2f}",
             ("≤" if c[k].get("capacity_upper_bound") else "") + f"{c[k]['capacity']:.3f}"]
            for k in ("conservative", "typical", "optimistic")]
    story.append(table(["경우", *S.SYSTEMS, "P_add", "총전력", "절감", "격차", "화성능력"], rows,
                       [12, 14, 15, 13, 14, 13, 13, 16, 16, 14, 18], num_cols=tuple(range(1, 11))))
    if ev["holds"]:
        story.append(P("판정 유보: " + " / ".join(ev["holds"]), "note"))
    story.append(Paragraph("그림 E2 — 원단위 절감: v10 가정 vs 근거 기반 vs 근거 기반 추가 조합", st["h2"]))
    story += [img("evidence_cases.png", 2.6)]
    cb = ev["combos"]["results"][:6]
    story.append(Paragraph(f"근거 있는 레버 추가 조합 탐색 (3년 내 레버 {len(ev['combos']['candidates'])}개, 조합 {ev['combos']['n_evaluated']}개 결정적 열거)", st["h2"]))
    if cb:
        story.append(table(["추가 레버", "판정", "보수", "대표", "낙관", "대표 격차(pt)"],
                           [[" + ".join(x["names"]), x["verdict"], pct(x["conservative"]), pct(x["typical"]),
                             pct(x["optimistic"]), f"{x['gap_typical']:+.2f}"] for x in cb],
                           [62, 38, 18, 18, 18, 22], num_cols=(2, 3, 4, 5)))
    else:
        story.append(P("근거가 있는 추가 후보 레버가 없음", "note"))
    if ev["combos"]["long_term_excluded"]:
        story.append(P("장기 레버(3년 내 적용 어려움)는 탐색에서 제외: " + ", ".join(ev["combos"]["long_term_excluded"]), "note"))
    story.append(m["PageBreak"]())

    story.append(Paragraph("레버별 근거 판정표 (점수 없이 범주로만 판정)", st["h2"]))
    lv = [[f"{l['lever_id']}\n{l['name']}", l["system"], "선택" if l["selected"] else "-", l["judge"],
           "-" if not l["range"] else f"{pct(l['range'][0])}~{pct(l['range'][2])}\n(대표 {pct(l['range'][1])})",
           f"{l['n_calc']}/{l['n_ref']}", l["best_grade"], "; ".join(l["failure_modes"][:2]) or "-", "; ".join(l["todo"]) or "-"]
          for l in ev["levers"]]
    story.append(table(["레버", "계통", "선택", "판정", "계통 기준 절감", "계산/참고", "등급", "주요 고장모드", "다음 조치"], lv,
                       [32, 15, 10, 16, 23, 13, 9, 29, 29]))
    story.append(P("판정 기준 - 근거 충분: 계산 사용 근거 2건 이상이고 그중 등급 C 이상 포함 / 근거 약함: 계산 사용 1건 또는 D·E만 / "
                   "참고 근거만: 경계가 달라 환산 불가한 근거만 있음 / 근거 없음.", "note"))
    gates = ev["burdens"]["gates"]
    if gates:
        story.append(Paragraph("선택 레버의 품질 관문 (적용 전 통과 조건)", st["h2"]))
        story.append(table(["FMEA", "레버", "고장모드", "품질 관문", "등급"],
                           [[g["fmea_id"], g["lever_id"], g["failure_mode"], g["gate"], g["grade"]] for g in gates],
                           [14, 20, 36, 96, 10]))
    tm = ev["time"]
    if tm.get("status") != "근거 없음":
        story.append(P(f"화성시간 점검: 목표 {res['inputs']['formation_h']:g}h/기준 {res['inputs']['baseline_formation_h']:g}h = "
                       f"{tm['target_ratio']:.2f}, 문헌 시간비 {tm['evidence_lo']:.2f}~{tm['evidence_hi']:.2f}({', '.join(tm['ids'])}) → {tm['status']}. {tm['note']}", "note"))
    for p in ev["params"]:
        story.append(P(f"파라미터 점검: {p['param']} 가정 {p['assumed']:g} vs 근거 {p['lo']:g}~{p['hi']:g}({', '.join(p['ids'])}) → {p['status']}", "note"))
    story.append(m["PageBreak"]())

    story.append(Paragraph("근거 추적표 — 수치 → 근거 (모든 정량효과 행)", st["h2"]))
    tr = []
    for e in ev["effects"]:
        rv = e["raw"]
        rawtxt = f"{rv[1]:.3g}" if rv[0] == rv[2] else f"{rv[0]:.3g}~{rv[2]:.3g}"
        sysv = "-" if e["typ"] is None or e["role"] != "saving" else (
            pct(e["typ"]) if e["lo"] == e["hi"] else f"{pct(e['lo'])}~{pct(e['hi'])}")
        tr.append([e["effect_id"], e["lever_id"], rawtxt, e["boundary"], e["how"], sysv, e["use"],
                   f"{e['source_id']} {e['locator']}", f"{e['grade']}/{e['verification']}"])
    story.append(table(["ID", "레버", "원값", "측정범위", "환산", "계통 기준", "사용", "근거·위치", "등급/확인"], tr,
                       [13, 19, 13, 14, 42, 18, 13, 30, 14]))
    story.append(P("원값의 단위: 절감·비중은 비율(0~1), 시간은 변경/기존 비, 파라미터는 원 단위. 전·후 값 행은 계산된 비율. "
                   "'참고 전용'은 측정 경계가 달라 계통 절감률로 바꿀 수 없어 판정에 쓰지 않은 근거, '제외'는 적용 조건 불일치·미확인.", "note"))
    srcs = {s["source_id"]: s for s in ev["clean"]["sources"]}
    used = sorted({e["source_id"] for e in ev["effects"]} | {g["source_id"] for g in ev["clean"]["fmea"]},
                  key=lambda x: (x[0], int("".join(ch for ch in x if ch.isdigit()) or 0)))
    story.append(Paragraph("근거 자료", st["h2"]))
    story.append(table(["ID", "서지", "DOI", "확인범위"],
                       [[k, srcs[k]["citation"], srcs[k].get("doi") or "-", srcs[k]["access"]] for k in used if k in srcs],
                       [12, 110, 40, 14]))
    story.append(P("이 보고서는 근거 데이터셋만으로 만든 자동 판정이며, 수명·불량률·확률·RPN을 생성하지 않는다. "
                   "원문 확인 '2차 인용'·'초록 확인' 행과 '조건부' 적용 행은 원문 대조와 대상 공장 실측 전까지 조건부 결과다.", "note"))

    total = {"n": 0}

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("NG", 8.5)
        canvas.setFillColor(colors.HexColor(R.GRAY))
        canvas.drawString(17 * mm, 285 * mm, "BATTERY ACADEMY 2026 / 문제 4 / 근거 기반 자동 판정")
        canvas.setStrokeColor(teal)
        canvas.line(17 * mm, 13 * mm, 193 * mm, 13 * mm)
        canvas.drawString(17 * mm, 8.5 * mm, f"근거 FMEA 데이터셋 판정  |  v12.2 설계 고정 판정({res['evidence'].get('candidates', {}).get('selected') or '-'})  |  {run_info['timestamp']}")
        canvas.drawRightString(193 * mm, 8.5 * mm, f"{doc.page}")
        canvas.restoreState()

    doc = m["BaseDocTemplate"](str(out_path), pagesize=A4, title="근거 기반 자동 판정 보고서", author="battery_v10",
                               leftMargin=17 * mm, rightMargin=17 * mm, topMargin=17 * mm, bottomMargin=17 * mm)
    frame = m["Frame"](17 * mm, 17 * mm, W * mm, (297 - 34 - 4) * mm, id="f", leftPadding=0, rightPadding=0,
                       topPadding=0, bottomPadding=0)
    doc.addPageTemplates([m["PageTemplate"](id="p", frames=[frame], onPage=on_page)])
    doc.build(story)
    from pypdf import PdfReader
    return len(PdfReader(str(out_path)).pages)


def export(res, out, run_info):
    """근거 판정 산출물 전체. res['evidence']가 오류 상태면 아무것도 만들지 않고 None."""
    ev = res.get("evidence") or {}
    if ev.get("status") != "충족":
        return None
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    write_figures(res, out)
    write_csvs(res, out)
    pages = build_pdf(res, out / "evidence_report.pdf", out, run_info)
    return {"pages": pages}
