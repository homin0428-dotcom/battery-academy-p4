"""CSV · 그래프 · 4쪽 PDF · manifest 생성. 계산은 core 결과만 사용한다."""
from __future__ import annotations

import csv
import hashlib
import json
import platform
import sys
from datetime import datetime
from importlib import metadata
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager

import core

BASE_DIR = Path(__file__).resolve().parent
FONT_REG = BASE_DIR / "assets" / "fonts" / "NanumGothic.ttf"
FONT_BOLD = BASE_DIR / "assets" / "fonts" / "NanumGothicBold.ttf"
FONT_LICENSE = BASE_DIR / "assets" / "fonts" / "OFL.txt"
FONT_LICENSE_TEXT = ("NanumGothic Regular/Bold 임베딩, SIL Open Font License 1.1 (assets/fonts/OFL.txt), "
                     "Copyright © 2011 NHN Corporation")
NAVY, TEAL, LIGHT, GRAY = "#173B50", "#237B80", "#EDF4F4", "#5F6F77"
USED_REFS = ["R1", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "R11"]  # 본문·PFMEA에서 실제 인용된 문헌
PACKAGES = ["numpy", "pandas", "matplotlib", "streamlit", "reportlab", "pytest", "pypdf"]

font_manager.fontManager.addfont(str(FONT_REG))
font_manager.fontManager.addfont(str(FONT_BOLD))
plt.rcParams.update({"font.family": "NanumGothic", "axes.unicode_minus": False,
                     "axes.spines.top": False, "axes.spines.right": False})


# ------------------------------------------------------------------ CSV
def _write_csv(path, rows, fields):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        wr.writeheader()
        wr.writerows(rows)


def drying_b_rows(b):
    """건조 모드 B 경계 상태(제한 요인·열원 한계·경고)를 requirements.csv 행으로 만든다."""
    if b["status"] != core.NUM_OK:
        return [{"kind": "건조 모드 B 경계", "item": "모드 B 상태", "interpretation": b["status"]}]
    rows = [{"kind": "건조 모드 B 경계", "item": "Qh 제한 요인", "interpretation": b["limit_by"]},
            {"kind": "건조 모드 B 경계", "item": "열원 한계 Qsource/(1-1/COP_h)", "value": b["source_limit_kwth"], "unit": "kWth",
             "interpretation": "열원 한계 초과로 상한 처리됨" if b["source_limited"] else "열원 한계 이내"},
            {"kind": "건조 모드 B 경계", "item": "열원 부족으로 미공급된 HP 요구", "value": b["unmet_hp_kwth"], "unit": "kWth",
             "interpretation": "보조 가열로 처리"}]
    rows += [{"kind": "건조 모드 B 경고", "item": "열원 한계 초과", "interpretation": w} for w in b["warnings"]]
    return rows


def aging_zone_rows(ag):
    if ag.get("status") != core.NUM_OK or not ag.get("zone_mode"):
        return []
    rows = []
    for z in ag["zones"]:
        for item, key, unit in (("freed_area", "freed_area_m2", "m2"),
                                ("전환 가능 슬롯(조건부)", "convertible_slots", "slot")):
            rows.append({"kind": "에이징 구역", "item": f"{z['name']} {item}", "value": z[key], "unit": unit,
                         "interpretation": f"{z['space_status']} | {z['space_note']}".rstrip(" |")})
    return rows


def write_csvs(res, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rows = [{"table": "비교 조건", **r} for r in res["comparison"]]
    rows += [{"table": "관리조치 전후", "id": f"BA{i}", "condition": b["stage"],
              "capacity_ratio": b["capacity_ratio"], "E_total": b["E_total"],
              "saving_ratio": b["saving_ratio"], "gap": b["gap"], "basis": b["note"]}
             for i, b in enumerate(res["before_after"], 1)]
    _write_csv(out / "scenario_comparison.csv", rows,
               ["table", "id", "group", "condition", "basis", "formation_h", "added_occupancy_h",
                "channel_ratio", "capacity_ratio", "status", "E_total", "saving_ratio", "gap"])
    req = [{"kind": "공장 계통 역산", "item": x["system"], "B_j": x["B_j"], "r_input": x["r_input"],
            "r_required": x["r_required"], "diff": x["diff"], "interpretation": x["interpretation"]}
           for x in res["reverse"]]
    req += [{"kind": "보완 요구", "item": x["item"], "r_input": x["current"], "r_required": x["required"],
             "interpretation": f"{x['unit']} | {x['note']}"} for x in res["requirements"]]
    req += drying_b_rows(res["drying_b"]) + aging_zone_rows(res["aging"])
    _write_csv(out / "requirements.csv", req,
               ["kind", "item", "B_j", "r_input", "r_required", "diff", "interpretation", "value", "unit"])
    fields = ["risk_id", "action_id", "process_change", "failure_path", "control_action", "evidence_id",
              "applicability_note", "quality_status", "impact_parameter", "impact_value", "impact_unit",
              "accounting_location", "calc_target", "calc_status", "missing_evidence", "next_check"]
    _write_csv(out / "pfmea_summary.csv", res["pfmea"].get("rows", []), fields)
    ev = core.load_csv(core.DEFAULT_EVIDENCE)
    for e in ev:
        e["used_in_report"] = "Y" if e["evidence_id"] in USED_REFS else "N"
    _write_csv(out / "evidence.csv", ev, list(ev[0].keys()))


# ------------------------------------------------------------------ 그래프
def fig_formation(res):
    v = res["inputs"]
    data = core.formation_boundary_data(v)
    fig, ax = plt.subplots(figsize=(6.6, 2.75))
    for ch, color in ((1.00, NAVY), (1.08, TEAL)):
        xs = np.array([d["formation_h"] for d in data if d["channel_ratio"] == ch])
        ys = np.array([d["allowed_added_h"] for d in data if d["channel_ratio"] == ch])
        ax.plot(xs, ys, color=color, lw=1.8, label=f"채널비 {ch:.2f} 목표 경계")
        ax.fill_between(xs, np.maximum(ys, 0), 0, where=ys > 0, interpolate=True, color=color, alpha=0.07)
    ax.plot([16], [0.25], "o", color=NAVY, ms=7, label="목표 사양 16h+0.25h")
    ax.plot([16], [2.0], "o", mfc="white", mec=TEAL, mew=1.8, ms=7, label="비교 가정 16h+2h")
    ax.set_xlim(14, 20)
    ax.set_ylim(0, 4.3)
    ax.set_xlabel("화성 본공정 시간 (h)")
    ax.set_ylabel("추가 점유시간 (h)")
    ax.legend(fontsize=7.5, frameon=False, loc="upper right")
    ax.grid(alpha=0.25, lw=0.5)
    fig.tight_layout()
    return fig


def fig_energy(res):
    v = res["inputs"]
    r_eff = res["r_effective"] if res["r_effective"][0] is not None else v["r"]
    pa = res["p_add"]["value"] if res["p_add"]["value"] is not None else 2.0
    data = core.energy_boundary_data(v, r_eff, [pa])
    fig, ax = plt.subplots(figsize=(6.6, 2.75))
    ax.axhspan(36, 42, color=TEAL, alpha=0.12, label="v10 단순화 시나리오 건조 36~42%")
    ax.plot([d["r_dryroom"] * 100 for d in data], [d["r_drying_required"] * 100 for d in data],
            color=TEAL, lw=1.8, label=f"필요한 건조 절감률 (P_add={pa:g} pt)")
    rep = [d for d in data if abs(d["r_dryroom"] - r_eff[1]) < 1e-9]
    if rep:
        x0, y0 = rep[0]["r_dryroom"] * 100, rep[0]["r_drying_required"] * 100
        ax.plot([x0], [y0], "o", color=NAVY, ms=7)
        ax.annotate(f"드라이룸 {x0:.0f}%일 때 건조 {y0:.1f}% 필요", (x0, y0), textcoords="offset points",
                    xytext=(8, 8), fontsize=7.5, color=NAVY)
    dr = [x for x in res["reverse"] if x["system"] == "드라이룸"]
    if dr and dr[0]["r_required"] is not None:
        x1, y1 = dr[0]["r_required"] * 100, r_eff[0] * 100
        ax.plot([x1], [y1], "o", color=NAVY, ms=7)
        ax.annotate(f"드라이룸 {core.fmt_pct_up(dr[0]['r_required'])}, 건조 {y1:.0f}%", (x1, y1),
                    textcoords="offset points", xytext=(-8, -14), fontsize=7.5, color=NAVY, ha="right")
    ax.set_xlim(10, 50)
    ax.set_ylim(25, 60)
    ax.set_xlabel("드라이룸 절감률 (%)")
    ax.set_ylabel("필요한 건조 절감률 (%)")
    ax.legend(fontsize=7.5, frameon=False, loc="upper right")
    ax.grid(alpha=0.25, lw=0.5)
    fig.tight_layout()
    return fig


def drying_b_text(b):
    if b["status"] != core.NUM_OK:
        return f"상태: {b['status']} (필수 입력 {len(b.get('missing', []))}건 미확인 - 모드 A 값으로 채우지 않음)"
    t = (f"절감률 {core.fmt_pct(b['saving_ratio'], 2)}, Qh {b['Qh']:.2f} kWth, 제한 요인: {b['limit_by']} "
         f"(열원 한계 {b['source_limit_kwth']:.2f} kWth).")
    if b["source_limited"]:   # 전문은 UI·requirements.csv·manifest에 있고 PDF에는 요약만 싣는다(4쪽 유지)
        t += (f" 경고: {'·'.join(b['exceeded'])}가 열원 한계를 초과하여 Qh를 {b['Qh']:.2f} kWth로 제한, "
              f"열원 부족 미공급 HP 요구 {b['unmet_hp_kwth']:.2f} kWth는 보조 가열로 처리.")
    return t


def aging_zone_text(ag, limit=4):
    parts = [f"{z['name']} {core.fmt_pct(z['additional_slot_ratio'], 1)}/{z['space_status']}" for z in ag["zones"][:limit]]
    more = f" 외 {len(ag['zones']) - limit}개(requirements.csv)" if len(ag["zones"]) > limit else ""
    return (f"추가 슬롯비/공간 - " + "; ".join(parts) + more + f". 합계 {ag['space_status']}. 구역 간 상쇄 없음, 14일 유지")


def energy_caption(res):
    v, r = res["inputs"], res["r_effective"]
    pa = res["p_add"]["value"]
    return (f"고정 조건: q={v['q']:g}, f={v['f']}, 화성 {r[2] * 100:.0f}%·에이징 {r[3] * 100:.0f}%·기타 {r[4] * 100:.0f}% 절감 고정, "
            f"P_add={pa if pa is not None else '미확인'} pt. 가정값에서 역산한 설계 경계이며 확보된 성능이 아니다. 음영은 v10 단순화 시나리오의 건조 36~42% 범위로 품질·설비 가능성을 보장하지 않는다.")


def formation_caption(res):
    v = res["inputs"]
    return (f"고정 조건: 기존 {v['baseline_formation_h']:g}h, 목표 처리능력비 {v['target_capacity_ratio']:g}, "
            f"가동률 {v['availability_ratio']:g}·수율 {v['yield_ratio']:g} 동일 유지 가정. "
            "목표 사양(0.25h)과 비교 가정(2h)은 현장 측정값이 아니다.")


def write_figures(res, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name, fn in (("formation_boundary.png", fig_formation), ("energy_boundary.png", fig_energy)):
        fig = fn(res)
        fig.savefig(out / name, dpi=300, facecolor="white")
        plt.close(fig)


# ------------------------------------------------------------------ PDF
def _pdf_imports():
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (BaseDocTemplate, Frame, Image, PageBreak, PageTemplate,
                                    Paragraph, Spacer, Table, TableStyle)
    return locals()


def build_pdf(res, out_path, fig_dir, run_info, checks):
    m = _pdf_imports()
    colors, mm, A4 = m["colors"], m["mm"], m["A4"]
    Paragraph, Spacer, Table, TableStyle = m["Paragraph"], m["Spacer"], m["Table"], m["TableStyle"]
    PS = m["ParagraphStyle"]
    pdfmetrics = m["pdfmetrics"]
    pdfmetrics.registerFont(m["TTFont"]("NG", str(FONT_REG)))
    pdfmetrics.registerFont(m["TTFont"]("NG-B", str(FONT_BOLD)))
    pdfmetrics.registerFontFamily("NG", normal="NG", bold="NG-B", italic="NG", boldItalic="NG-B")
    navy, teal, light = colors.HexColor(NAVY), colors.HexColor(TEAL), colors.HexColor(LIGHT)

    st = {
        "title": PS("t", fontName="NG-B", fontSize=22, leading=27, textColor=navy, spaceAfter=2),
        "sub": PS("s", fontName="NG", fontSize=10.5, leading=14, textColor=colors.HexColor(GRAY)),
        "h2": PS("h", fontName="NG-B", fontSize=13, leading=17, textColor=navy, spaceBefore=7, spaceAfter=3),
        "body": PS("b", fontName="NG", fontSize=10, leading=14.2),
        "cell": PS("c", fontName="NG", fontSize=9, leading=11.6),
        "cellb": PS("cb", fontName="NG-B", fontSize=9, leading=11.6, textColor=colors.white),
        "num": PS("n", fontName="NG", fontSize=9, leading=11.6, alignment=m["TA_RIGHT"]),
        "numh": PS("nh", fontName="NG-B", fontSize=9, leading=11.6, textColor=colors.white, alignment=m["TA_RIGHT"]),
        "note": PS("f", fontName="NG", fontSize=8.5, leading=11.2, textColor=colors.HexColor(GRAY)),
        "kt": PS("kt", fontName="NG", fontSize=8.5, leading=11, textColor=colors.HexColor(GRAY)),
        "kv": PS("kv", fontName="NG-B", fontSize=17, leading=21, textColor=navy),
        "ks": PS("ks", fontName="NG", fontSize=8.5, leading=11),
        "kl": PS("kl", fontName="NG-B", fontSize=8.5, leading=11, textColor=teal),
    }
    esc = lambda s: escape(str(s))
    P = lambda s, k="cell": Paragraph(esc(s), st[k])

    W = 210 - 34  # mm, 좌우 여백 17mm

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
            ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        return t

    v, fm, pl = res["inputs"], res["formation"], res["plant"]
    story = []

    # ---- Page 1
    story += [Paragraph("PFMEA 연계 공정 전환 검토", st["title"]),
              P(f"시나리오: {res['scenario_label']}   |  계산 모드: {res['calculation_mode']}", "sub"),
              Spacer(1, 5 * mm)]
    kcells = []
    for k in res["kpi"]:
        kcells.append([P(k["title"], "kt"), P(k["value"], "kv"), P(k["sub"], "ks"), P("근거: " + k["label"], "kl")])
    kt = Table([[[*kc] for kc in kcells]], colWidths=[W / 4 * mm] * 4)
    kt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), light), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LINEAFTER", (0, 0), (-2, -1), 2, colors.white),
                            ("LINEABOVE", (0, 0), (-1, 0), 2, teal),
                            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story += [kt, Paragraph("관리조치 전·후 비교 (바꾸지 않은 입력은 동일 유지)", st["h2"])]
    ba = [[b["stage"], core.fmt_ratio(b["capacity_ratio"], 3), core.fmt_num(b["E_total"], 2),
           core.fmt_pct(b["saving_ratio"], 2), f"{b['gap']:+.2f}", b["note"]] for b in res["before_after"]]
    story.append(table(["단계", "화성 처리능력(배)", "총전력(pt)", "원단위 절감", "격차(pt)", "조건"], ba,
                       [40, 24, 20, 22, 18, 52], num_cols=(1, 2, 3, 4)))
    story.append(Paragraph("보완 요구 사양 (목표 도달에 필요한 조건이며 확보된 성능이 아님)", st["h2"]))
    rq = []
    for x in res["requirements"]:
        if x["unit"] == "비율":
            cur, req = core.fmt_pct(x["current"], 1), core.fmt_pct_up(x["required"], 1)
        elif x["unit"] == "채널비":
            cur, req = f"{x['current']:.2f}", f"{x['required']:.2f}"
        else:
            cur, req = f"{x['current']:.2f} {x['unit']}", f"{x['required']:.3f} {x['unit']}"
        rq.append([x["item"], cur, req, x["note"]])
    story.append(table(["항목", "현재 입력", "요구·허용", "해석"], rq, [58, 22, 24, 72], num_cols=(1, 2)))
    story += [Paragraph("조건부 엔지니어링 판단", st["h2"]), Paragraph(esc(res["conclusion"]), st["body"]),
              Spacer(1, 2 * mm),
              P("요구 사양은 표시 시 올림, 판정은 반올림 이전 값 기준. P_add 단위는 기준 전력 100에 대한 포인트(pt)이며 "
                "kWh·비용으로 환산하지 않았다.", "note"),
              m["PageBreak"]()]

    # ---- Page 2
    img = lambda n: m["Image"](str(Path(fig_dir) / n), width=W * mm, height=W * mm * 2.75 / 6.6)
    story += [Paragraph("그림 1 — Formation Boundary (화성 시간 경계)", st["h2"]), img("formation_boundary.png"),
              P(formation_caption(res), "note"),
              Paragraph("그림 2 — Energy Boundary (에너지 보완 경계)", st["h2"]), img("energy_boundary.png"),
              P(energy_caption(res), "note"),
              Paragraph("해석과 적용 한계", st["h2"])]
    lb = bool(fm.get("occupancy_lower_bound"))
    interp = [
        f"그림 1: 현재 채널비에서 화성 {v['formation_h']:g}h일 때 허용 추가 점유는 {core.fmt_num(fm.get('allowed_added_h'), 3)} h이며, "
        "채널비 1.08에서는 16h 기준 2.0 h까지 허용된다. 16h+2h는 검증된 현장값이 아닌 비교 가정이다."
        + (f" 현재 입력 추가 점유 {res['added_occupancy_h']:.2f} h는 미확인 조치({', '.join(fm['unquantified_actions'])})를 "
           f"뺀 하한이므로 처리능력 {fm['capacity_ratio']:.3f}배는 상한값이고 판정은 '{fm['status']}'이다." if lb else ""),
        "그림 2: 드라이룸 절감률이 낮을수록 필요한 건조 절감률이 커진다. 요구값이 100%를 넘으면 건조 단독 보완은 불가능하며 이 범위에서는 해당하지 않는다."
        + (f" {', '.join(pl['increase_systems'])} 계통은 절감률이 음수(전력 증가)로 입력되어 목표 미달 요인이다."
           if pl.get("increase_systems") else ""),
        "한계: 화성 처리능력은 화성 단독 결과이며 건조·조립 등 병목 자료가 없어 전체 공장 생산능력 달성은 미확인이다. "
        "공장 전력은 계통 비중·고정부하 비율·절감률을 가정한 설계 계산이며 실측이 아니다.",
        "품질 동등성은 별도 검증 대상이며 이 보고서는 수명·불량률을 예측하지 않는다."]
    story += [Paragraph("• " + esc(t), st["body"]) for t in interp]
    story.append(m["PageBreak"]())

    # ---- Page 3
    story.append(Paragraph("PFMEA 변경 영향표 (6개 위험 경로)", st["h2"]))
    rows = [[t["공정 변경"], t["실패 경로"], t["관리조치"], t["계산 영향"], t["확인 상태"], t["다음 검증"]]
            for t in core.pfmea_table(res)]
    story.append(table(["공정 변경", "실패 경로", "관리조치", "계산 영향", "확인 상태", "다음 검증"], rows,
                       [22, 23, 38, 41, 15, 37]))
    pf = res["pfmea"]
    c = pf.get("counts", {})
    story.append(P("계산 영향 표기: (자동 반영)=계산에 직접 합산, (수동 반영 대상)=자동 연결 안 됨·수동 반영해야 하는 미반영 항목, "
                   "(자동 반영 대상(값 미확인))=연결은 되나 값이 없어 미합산, (계산 미연결)=수치만 기록.", "note"))
    story += [Paragraph("요약", st["h2"])]
    summ = [
        f"주요 관리조치: 위험 경로 {c.get('risks', 0)}건 모두 관리조치가 정의됨(위 표의 관리조치 열 참조).",
        f"계산에 반영한 부담: 추가 점유 {'≥' if res.get('added_occupancy_lower_bound') else ''}{core.fmt_num(res['added_occupancy_h'], 2)} h"
        f"({'하한, 미확인 조치 제외' if res.get('added_occupancy_lower_bound') else 'F02, 목표 사양'}), "
        f"추가 관리 전력 P_add={core.fmt_num(res['p_add']['value'], 2)} pt({core.KEY_KO.get(res['p_add']['mode'], res['p_add']['mode'])}: {res['p_add']['note']}). "
        f"계산에 직접 반영된 효과 {c.get('reflected', 0)}건.",
        f"정량 부담이 미확인인 항목: {c.get('burden_unknown', 0)}건 - 필요한 조치는 있으나 0으로 처리하지 않고 미확인으로 유지.",
        f"품질 검증이 필요한 위험 경로: {c.get('quality_open', 0)}건(미확인·검증 중), 품질 미충족으로 적용 제외: {c.get('excluded', 0)}건"
        f"({', '.join(pf.get('unmet_risks', [])) or '없음'}).",
        "핵심 근거: R3·R5·R9(화성), R4·R6·R7·R10(건조), R1·R8(드라이룸·공간). 본 도구는 PFMEA 확률·RPN·안전 인증 결과를 생성하지 않는다."]
    story += [Paragraph("• " + esc(t), st["body"]) for t in summ]
    story.append(m["PageBreak"]())

    # ---- Page 4
    h2c = PS("h2c", parent=st["h2"], spaceBefore=4, spaceAfter=2)    # 4쪽은 항목이 많아 간격을 줄인다
    story.append(Paragraph("핵심 가정과 기준 과제 조건", h2c))
    asm = [["기준 과제 조건", "NCM 파우치 10→12GWh(1.2배), 원단위 0.70(30% 절감), 기존 화성 20h, 에이징 14일, 건조로 60m NMP, 드라이룸 이슬점 -40°C 이하, 기준 전력 100(건조 35·드라이룸 25·화성·에이징 15·기타 25)"],
           ["가정", f"화성 10·에이징 5 분할, f={v['f']}, r={v['r']}(건조 출처: {core.KEY_KO[res['drying_r_source']]}), P_add={core.fmt_num(res['p_add']['value'], 2)} pt, "
                    "채널비·가동률·수율 동일 유지. 모두 분석 가정이며 실측이 아님"],
           ["건조 모드 A", f"절감률 {core.fmt_pct(res['drying_a'].get('saving_ratio'), 2)} ({core.drying_a_condition(v['drying_a'])}). 수동 입력 건조 {core.fmt_pct(v['r'][0], 0)}와 다른 값이며 공장 모델에는 '{core.KEY_KO[res['drying_r_source']]}' 하나만 반영. b·COP_h는 분석 가정, R6의 COP 정의는 미확인"],
           ["건조 모드 B", drying_b_text(res["drying_b"])]]
    if res["aging"].get("zone_mode"):
        asm.append(["에이징 구역별", aging_zone_text(res["aging"])])
    story.append(table(["구분", "내용"], asm, [30, 146]))
    story.append(Paragraph("사용한 문헌 (v10 참고문헌 목록 기준, 원문 확인 상태는 근거 판정 보고서 참조)", h2c))
    ev = {e["evidence_id"]: e for e in core.load_csv(core.DEFAULT_EVIDENCE)}
    refs = [[k, ev[k]["title"], ev[k]["doi"] or "DOI 없음"] for k in USED_REFS]
    story.append(table(["번호", "제목", "DOI"], refs, [11, 113, 52]))
    story.append(P("R2(Wood et al., 2019)는 v10 본문에서 인용되지 않아 위 표에서 제외했고 evidence.csv에만 기록했다.", "note"))
    story.append(Paragraph("실행 정보와 검산 결과", h2c))
    npass = sum(1 for c_ in checks if c_["pass"])
    info = [["실행", f"{run_info['timestamp']} / {run_info['execution_mode']} / {res['scenario_label']} / 설정 해시 {res['config_hash'][:16]}…"],
            ["검산·테스트", f"대표 검산 {npass}/{len(checks)} 항목 일치. pytest: {run_info['test_status_text']}"],
            ["폰트·라이선스", FONT_LICENSE_TEXT]]
    story.append(table(["항목", "값"], info, [30, 146]))
    story.append(Paragraph("제한 사항", h2c))
    lim = ["본 결과는 가정 기반의 조건부 계산이며 대상 공장의 품질 충족을 의미하지 않는다. 현장 공정 검증(품질 동등성, 방재, 온도 균일성 등)은 이 소프트웨어 검증과 별개이다.",
           "화성 처리능력은 화성 단독 값이며 전체 공장 생산능력·건조·조립 병목은 미확인이다.",
           "건조 모드 B, 에이징 대기공간 전환, 채널 수 등 미확인 입력은 0으로 채우지 않고 계산을 보류하거나 비율만 표시했다."]
    story += [Paragraph("• " + esc(t), st["body"]) for t in lim]

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("NG", 8.5)
        canvas.setFillColor(colors.HexColor(GRAY))
        canvas.drawString(17 * mm, 285 * mm, "BATTERY ACADEMY 2026 / 문제 4 / v10")
        canvas.setStrokeColor(teal)
        canvas.line(17 * mm, 13 * mm, 193 * mm, 13 * mm)
        canvas.drawString(17 * mm, 8.5 * mm, f"PFMEA 연계 공정 전환 검토  |  {res['scenario_label']}")
        canvas.drawRightString(193 * mm, 8.5 * mm, f"{doc.page} / 4")
        canvas.restoreState()

    doc = m["BaseDocTemplate"](str(out_path), pagesize=A4, title="PFMEA 연계 공정 전환 검토 결과 보고서",
                               author="battery_v10", leftMargin=17 * mm, rightMargin=17 * mm,
                               topMargin=17 * mm, bottomMargin=17 * mm)
    frame = m["Frame"](17 * mm, 17 * mm, W * mm, (297 - 34 - 4) * mm, id="f", leftPadding=0, rightPadding=0,
                       topPadding=0, bottomPadding=0)
    doc.addPageTemplates([m["PageTemplate"](id="p", frames=[frame], onPage=on_page)])
    doc.build(story)

    from pypdf import PdfReader
    n = len(PdfReader(str(out_path)).pages)
    if n != 4:
        raise RuntimeError(f"PDF가 4쪽이 아니다({n}쪽)")
    return n


# ------------------------------------------------------------------ manifest
def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_manifest(res, out, run_info, config_path=None):
    pk = {}
    for p in PACKAGES:
        try:
            pk[p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            pk[p] = None
    sources = [{"path": str(Path(p).relative_to(BASE_DIR)) if Path(p).is_absolute() and BASE_DIR in Path(p).parents else str(p),
                "sha256": _sha(p)}
               for p in (config_path or core.DEFAULT_CONFIG, core.DEFAULT_PFMEA, core.DEFAULT_EVIDENCE, FONT_REG, FONT_BOLD, FONT_LICENSE)]
    man = {"scenario": res["scenario"], "execution_mode": run_info["execution_mode"],
           "timestamp": run_info["timestamp"], "configuration_hash": res["config_hash"],
           "python_version": platform.python_version(), "package_versions": pk,
           "calculation_mode": res["calculation_mode"], "warnings": res["warnings"],
           "test_status": run_info["test_status"], "input_sources": sources,
           "derived": {"formation_capacity_ratio": res["formation"].get("capacity_ratio"),
                       "E_total": res["plant"].get("E_total"), "saving_ratio": res["plant"].get("saving_ratio"),
                       "gap": res["plant"].get("gap"), "quality_status": res["quality_status"],
                       "formation_status": res["formation"].get("status"),
                       "occupancy_lower_bound": bool(res["formation"].get("occupancy_lower_bound")),
                       "capacity_is_upper_bound": bool(res["formation"].get("capacity_is_upper_bound")),
                       "increase_systems": res["plant"].get("increase_systems", []),
                       "unmet_risks": res["pfmea"].get("unmet_risks", []),
                       "manual_pending": res["pfmea"].get("manual_pending", [])},
           "font_note": "NanumGothic(NHN Corporation, 2011) 임베딩, fsType=8. 라이선스: SIL OFL 1.1 (assets/fonts/OFL.txt). "
                        "폰트 파일 메타데이터 자체에는 라이선스 문구가 없다 - README 참조"}
    ev = res.get("evidence") or {}
    kb_dir = BASE_DIR / "data" / "kb"
    man["evidence_dataset"] = {
        "files": [{"path": f"data/kb/{p.name}", "sha256": _sha(p)} for p in sorted(kb_dir.glob("*.csv"))],
        "status": ev.get("status"), "error": ev.get("error"),
    }
    if ev.get("status") == core.NUM_OK:
        man["evidence_dataset"].update({
            "verdict": ev["verdict"], "selected_levers": ev["selected"], "counts": ev["counts"],
            "validation_errors": ev["n_errors"], "holds": ev["holds"],
            "saving_ratio": {k: ev["cases"][k]["saving"] for k in ("conservative", "typical", "optimistic")},
            "best_addition": (next((x for x in ev["combos"]["results"] if x["verdict"] != "근거상 미달"), None) or {}).get("add"),
            "v10_check": {r["system"]: r["status"] for r in ev["v10_check"]}})
        cd = ev.get("candidates")
        if cd:
            man["evidence_dataset"]["candidates"] = {
                "selected": cd["selected"], "status": cd["status"],
                "rows": {c["id"]: {"saving": c["saving"], "label": c["label"], "eligible": c["eligible"],
                                   "axes": {a["axis"]: a["state"] for a in c["axes"]}} for c in cd["candidates"]}}
    Path(out, "run_manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
    return man


def make_run_info(mode, test_status=None):
    ts = test_status or {"status": "not_run"}
    txt = ("실행하지 않음" if ts["status"] == "not_run" else
           f"{ts['status']}: 통과 {ts.get('passed', '?')} / 실패 {ts.get('failed', '?')} (종료코드 {ts.get('exit_code', '?')})")
    return {"execution_mode": mode, "timestamp": datetime.now().isoformat(timespec="seconds"),
            "test_status": ts, "test_status_text": txt}


def export_all(res, out, run_info, config_path=None):
    """CSV · PNG · PDF · manifest를 한 번에 생성한다."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    write_csvs(res, out)
    write_figures(res, out)
    pages = build_pdf(res, out / "result_report.pdf", out, run_info, core.self_check())
    import evidence_report   # 근거 기반 판정 보고서는 별도 파일(4쪽 결과 보고서와 분리)
    evr = evidence_report.export(res, out, run_info)
    chk = None
    if evr:
        import results_export   # 숫자 원본 results.json + 일치 검사
        chk = results_export.export(res, out)
    man = write_manifest(res, out, run_info, config_path)
    if chk is not None:
        man["version"] = results_export.VERSION
        man["consistency_check"] = chk
        code = sorted(BASE_DIR.glob("*.py"))
        man["code_files"] = [{"path": p.name, "sha256": _sha(p)} for p in code]
        man["results_json_sha256"] = _sha(Path(out, "results.json"))
        log = Path(out, "test_log.txt")
        if log.exists() and run_info["test_status"].get("status") != "not_run":
            man["test_log_sha256"] = _sha(log)
        Path(out, "run_manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"pdf_pages": pages, "manifest": man, "evidence": evr, "consistency": chk}
