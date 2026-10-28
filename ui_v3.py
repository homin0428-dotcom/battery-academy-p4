"""v3 화면 부품 - 계산은 하지 않고 core.run_scenario 결과(res)를 그림·표로 보여 준다.

모든 숫자는 res(= results.json과 같은 엔진 출력)에서 읽는다. 가짜 시계열 데이터를 만들지 않는다.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

NAVY, TEAL, AMBER, RED, GREEN, GRAY, LIGHT = "#173B50", "#237B80", "#D9952B", "#E5534B", "#2BB673", "#94A3AB", "#EEF3F4"
FONT = dict(family="Noto Sans KR, sans-serif", size=13, color="#1F2D35")
pct = lambda x, n=1: "-" if x is None else f"{x * 100:.{n}f}%"


def md(t):
    """마크다운에서 '~'가 취소선으로 바뀌지 않게 이스케이프."""
    return str(t).replace("~", "\\~")


def _layout(fig, h=360, title=None):
    fig.update_layout(template="plotly_white", height=h, font=FONT, margin=dict(l=10, r=10, t=50 if title else 20, b=10),
                      title=dict(text=title, font=dict(size=15, color=NAVY)) if title else None,
                      legend=dict(orientation="h", y=-0.18), hoverlabel=dict(font_family="Noto Sans KR"))
    return fig


def _cell(v):
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(v, float):
        return f"{v:,.3f}".rstrip("0").rstrip(".") if abs(v) < 1e6 else f"{v:,.0f}"
    return str(v)


def table(df, hide_index=True, width=None, height=None, column_config=None, **kw):  # noqa: C901
    """긴 글이 있는 표는 줄바꿈되는 HTML 표로(모바일에서도 잘리지 않음), 숫자 위주 표는 기존 st.dataframe."""
    import html as _h
    if column_config is not None:
        return st.dataframe(df, hide_index=hide_index, width=width or "stretch", height=height or "auto", column_config=column_config, **kw)
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame(df)
    long_text = any(df[c].astype(str).str.len().max() > 18 for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])) if len(df) else False
    if not long_text:
        return st.dataframe(df, hide_index=hide_index, width=width or "stretch", height=height or "auto", **kw)
    mh = f"max-height:{int(height)}px;" if isinstance(height, (int, float)) else ("max-height:560px;" if len(df) > 14 else "")
    cells = [[_cell(v) for v in row.tolist()] for _, row in df.iterrows()]
    # 열 단위로 폭 등급을 정한다(같은 열은 같은 폭): 짧은 열은 줄바꿈 금지, 긴 열은 최소 폭 보장
    widths = []
    for j in range(len(df.columns)):
        mx = max([len(r[j]) for r in cells] + [0])
        widths.append("nw" if mx <= 12 else "w1" if mx <= 24 else "w2" if mx <= 45 else "w3" if mx <= 90 else "w4")
    head = "".join(f'<th class="{widths[j]}">{_h.escape(str(c))}</th>' for j, c in enumerate(df.columns))
    body = ["<tr>" + "".join(f'<td class="{widths[j]}">{_h.escape(t)}</td>' for j, t in enumerate(r)) + "</tr>" for r in cells]
    st.markdown(f'<div class="wtbl-wrap" style="{mh}"><table class="wtbl"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>',
                unsafe_allow_html=True)


def _dot(txt):
    return "🟢" if ("충족" in txt or "통과" in txt or "추천" in txt) else ("🔴" if "미달" in txt else "🟡")


def _ok(cd):
    return lambda k: cd.get(k) if isinstance(cd.get(k), dict) and "error" not in cd.get(k) else None


# ------------------------------------------------------------------ 탭 1
def tab_analysis(res):
    cd = (res.get("evidence") or {}).get("candidates")
    if not cd:
        st.info("후보 비교 결과가 없습니다.")
        return
    g = _ok(cd)
    sel = next(c for c in cd["candidates"] if c["id"] == cd["selected"])
    dz, bl, nc, jt, rm = g("design"), g("baseline_model"), g("necessity"), g("joint"), g("roadmap")

    if dz:
        st.markdown("### 두 목표 신호등")
        st.caption("같은 조건에서 전력 -30%와 생산능력 +20%를 함께 판정 - 전력 통과가 곧 종합 통과는 아니다")
        table(pd.DataFrame([{"조건": r["cond"], "전력 -30%": f"{_dot(r['power'])} {r['power']}",
                                    "생산능력 +20%": f"{_dot(r['capacity'])} {r['capacity']}", "종합": r["overall"]}
                                   for r in dz["signal"]["rows"]]), hide_index=True, width="stretch")

    c1, c2 = st.columns([1.15, 1])
    wf = (bl or {}).get("waterfall")
    with c1:
        if wf:
            steps = [s for s in wf["steps"] if abs(s["pt"]) > 1e-9]
            fig = go.Figure(go.Waterfall(
                x=["전부 비례\n(1.2배)"] + [s["item"].replace("(생산량이 늘어도 안 느는 부하)", "").replace(" 개조", " 개조") for s in steps] + ["12 GWh 총전력"],
                measure=["absolute"] + ["relative"] * len(steps) + ["total"],
                y=[wf["start_pt"]] + [-s["pt"] for s in steps] + [0],
                text=[f"{wf['start_pt']:.0f}"] + [f"-{s['pt']:.2f}<br>({s['pp']:.2f}%p)" for s in steps] + [f"{wf['E']:.2f}"],
                textposition="outside", connector=dict(line=dict(color="#C9D6DA")),
                decreasing=dict(marker=dict(color=TEAL)), increasing=dict(marker=dict(color=RED)), totals=dict(marker=dict(color=NAVY))))
            fig.add_hline(y=cd["baseline"]["target"], line_dash="dash", line_color=RED)
            fig.add_annotation(x=1.0, xref="paper", y=cd["baseline"]["target"], yref="y", xanchor="right", yanchor="bottom",
                               text=f"<b>목표 {cd['baseline']['target']:.0f} pt</b>", showarrow=False, yshift=4,
                               font=dict(color=RED, size=13), bgcolor="rgba(255,255,255,0.92)", borderpad=3)
            fig.update_yaxes(title="12 GWh 총전력 (pt, 현재 공장 = 100)", range=[60, wf["start_pt"] + 8])
            st.plotly_chart(_layout(fig, 400, f"{pct(wf['saving'])}는 어디서 나오나 (계통별)"), width="stretch")
            st.caption(f"공정 개조 {wf['tech_pp']:.2f}%p + 고정부하 희석 {wf['dilution_pp']:.2f}%p. 희석은 팀 가정 f에서 나오며 개조 성과가 아니다.")
    with c2:
        rows = [r for r in ((nc or {}).get("necessity") or {}).get("rows", []) if r["delta_pp"] > 1e-9][::-1]
        if rows:
            fig = go.Figure(go.Bar(y=[r["name"] for r in rows], x=[r["delta_pp"] for r in rows], orientation="h",
                                   marker_color=[TEAL if r["delta_pp"] >= 5 else "#5FB3B3" for r in rows],
                                   text=[f"{r['delta_pp']:.2f}%p" for r in rows], textposition="outside",
                                   hovertext=[r.get("dual_role") or r["class"] for r in rows], hoverinfo="text+x"))
            fig.update_xaxes(title="그 레버만 뺄 때 줄어드는 절감 (%p)", range=[0, max(r["delta_pp"] for r in rows) * 1.3])
            st.plotly_chart(_layout(fig, 400, "레버별 한계 기여 (서로 겹쳐 합계 ≠ 총 절감)"), width="stretch")
            ff = next((r for r in rows if r.get("dual_role")), None)
            if ff:
                st.caption("화성 단축의 이중 역할: " + ff["dual_role"])

    cands = cd["candidates"]
    fig = go.Figure(go.Bar(
        x=[f"{c['id']}<br>{c['name']}" for c in cands], y=[c["saving"][1] * 100 for c in cands],
        error_y=dict(type="data", symmetric=False, array=[(c["saving"][2] - c["saving"][1]) * 100 for c in cands],
                     arrayminus=[(c["saving"][1] - c["saving"][0]) * 100 for c in cands], color=GRAY),
        marker_color=[NAVY if c["id"] == cd["selected"] else ("#C7D3D7" if c["saving"][1] < 0.3 else "#7FB8BB") for c in cands],
        text=[f"{c['saving'][1] * 100:.1f}%" for c in cands], textposition="outside",
        hovertext=[f"{c['label']}<br>여유 {c['margin_pt']:+.2f} pt · 고형분 {c['solids'] * 100:.0f}%" for c in cands], hoverinfo="text"))
    fig.add_hline(y=30, line_dash="dash", line_color=RED, annotation_text="<b>목표 30%</b>", annotation_position="top left",
                  annotation=dict(font=dict(color=RED, size=13), bgcolor="rgba(255,255,255,0.92)"))
    fig.update_yaxes(title="전력 원단위 절감 (%) · 막대 = 보수~낙관", range=[0, 45])
    st.plotly_chart(_layout(fig, 380, "후보 5종 비교 - 같은 기준선·같은 근거"), width="stretch")
    b0 = next((c for c in cands if c["id"] == "B0"), None)
    hsc = next((r["delta_pp"] for r in ((nc or {}).get("necessity") or {}).get("rows", []) if r["lever_id"] == "DRY-HSC"), None)
    if b0 and hsc is not None:
        st.caption(f"B0(복사건조만)도 전력은 {pct(b0['saving'][1])}로 목표를 넘는다. 고형분이 전력에 더하는 건 {hsc:.2f}%p뿐이고, "
                   "핵심은 건조 처리능력 - 고형분 64.29% 이상이면 질량수지로 체류 0.833배 안에 건조가 끝난다(B0는 D등급 근거에서만 성립).")

    c3, c4 = st.columns(2)
    with c3:
        rg = (jt or {}).get("region")
        if rg:
            fig = go.Figure(go.Heatmap(x=rg["alpha_grid"], y=rg["p_grid"], z=[[1 if rg["ok_grid"][i][j] else 0 for i in range(len(rg["alpha_grid"]))] for j in range(len(rg["p_grid"]))],
                                       colorscale=[[0, "#F6D5D2"], [1, "#CDEBDD"]], showscale=False, hoverinfo="skip"))
            xs = [x for x in rg["alpha_grid"]]
            fig.add_trace(go.Scatter(x=xs, y=[rg["target"] - rg["a"] + rg["b"] * x for x in xs], mode="lines",
                                     line=dict(color=NAVY, width=2.5), name="목표 경계"))
            fig.add_trace(go.Scatter(x=[1.0], y=[0.0], mode="markers+text", marker=dict(size=12, color=NAVY),
                                     text=["대표"], textposition="top right", name="대표 (α 1, P 0)"))
            fig.add_trace(go.Scatter(x=[0.9], y=[4.0], mode="markers+text", marker=dict(size=12, color=RED, symbol="x"),
                                     text=["S1"], textposition="top right", name="문헌 90% + 관리 4 pt"))
            fig.update_xaxes(title="α 문헌 효과 재현율", range=[min(xs), max(xs)])
            fig.update_yaxes(title="P 미정량 관리 전력 (pt)", range=[min(rg["p_grid"]), max(rg["p_grid"])])
            st.plotly_chart(_layout(fig, 380, "어디서 깨지나 - α–P 성립 영역 (초록 = 목표 충족)"), width="stretch")
            st.caption(f"{rg['formula']} · 경계 α* = {rg['alpha_star']:.3f} · P 허용치 α 0.9 → {rg['p_max'].get(0.9, rg['p_max'].get('0.9', 0)):.2f} pt")
    with c4:
        rc = (rm or {}).get("reach")
        if rc:
            lab = [r["stage"] for r in rc["rows"]]
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Bar(x=lab, y=[r["power_no_slot"] * 100 for r in rc["rows"]], name="전력 절감 (공간 미확보)",
                                 marker_color="#9FC9CB", text=[f"{r['power_no_slot'] * 100:.1f}%" for r in rc["rows"]], textposition="outside"))
            fig.add_trace(go.Bar(x=lab, y=[r["power_if_slot"] * 100 for r in rc["rows"]], name="전력 절감 (슬롯 확보 시)",
                                 marker_color=TEAL, text=[f"{r['power_if_slot'] * 100:.1f}%" for r in rc["rows"]], textposition="outside"))
            fig.add_trace(go.Scatter(x=lab, y=[r["q_no_slot"] for r in rc["rows"]], name="생산비 q (미확보)", mode="lines+markers",
                                     line=dict(color=AMBER, dash="dot")), secondary_y=True)
            fig.add_trace(go.Scatter(x=lab, y=[r["q_if_slot"] for r in rc["rows"]], name="생산비 q (확보 시)", mode="lines+markers",
                                     line=dict(color=NAVY)), secondary_y=True)
            fig.add_hline(y=30, line_dash="dash", line_color=RED, annotation_text="<b>전력 목표 30%</b>", annotation_position="top left",
                          annotation=dict(font=dict(color=RED, size=13), bgcolor="rgba(255,255,255,0.92)"))
            fig.update_yaxes(title_text="원단위 절감 (%)", range=[0, 48], secondary_y=False)
            fig.update_yaxes(title_text="생산비 q (목표 1.2)", range=[0.9, 1.3], secondary_y=True)
            st.plotly_chart(_layout(fig, 380, "연차별 두 목표 도달도"), width="stretch")
            st.caption(md(rc["note"]))

    if dz:
        st.markdown("### 설계 고정 비교 - 왜 숫자를 낮췄나")
        cmp_ = dz["compare"]
        ok = lambda r, k, x: f"{'🟢' if r['ok'][k] else '🔴'} {pct(x, 2)}"
        df = pd.DataFrame({"조건": ["기본 · 여유", "문헌 효과 경계 α*", "문헌 90% + 관리 4 pt", "고정부하 f 전부 0", "2·3년차 공간 미확보",
                                   "드라이룸 재생 가스", "건조 가스", "연 전력비 현재 대비 / 무개선 대비"]})
        for r in cmp_["rows"]:
            df[r["label"] + (" ★공식" if r["official"] else "")] = [
                f"{pct(r['saving'][1], 2)} · {r['margin_pt']:+.2f} pt", f"{r['alpha_star']:.3f}", ok(r, "s1", r["s1"]), ok(r, "f0", r["f0"]),
                ok(r, "y2_no_slot", r["y2_no_slot"]), ok(r, "dryroom_gas", r["dryroom_gas"]), ok(r, "drying_gas", r["drying_gas"]),
                f"{r['money_now'][0]:.0f}~{r['money_now'][1]:.0f} / {r['money_nochange'][0]:.0f}~{r['money_nochange'][1]:.0f}억"]
        table(df, hide_index=True, width="stretch")
        st.caption(md(cmp_["protocol_basis"]))
    sp = ((rm or {}).get("space") or {})
    if sp.get("ledger"):
        st.markdown("### 에이징 공간 장부 - 무엇을 재면 +20% 확보 여부가 정해지나")
        st.write(md(sp["sentence"]))
        table(pd.DataFrame([{"장부": r["col"], "값": r["value"], "무엇으로 정하나": r["how"], "상태": r["status"]} for r in sp["ledger"]]),
                     hide_index=True, width="stretch")
        table(pd.DataFrame([{"": o["no"], "확보 후보": o["name"], "원리": o["how"], "기대는 조건": o["depends"], "시기": o["when"]}
                                   for o in sp["options"]]), hide_index=True, width="stretch")
        st.caption(md(sp["ledger_note"]))


# ------------------------------------------------------------------ 탭 2
TS = __import__("pathlib").Path(__file__).resolve().parent / "data" / "timeseries"
PROTO = {"Baseline": ("기준 화성", "#B77928"), "Fast": ("고속 화성", TEAL)}


def _ts(name):
    return pd.read_csv(TS / name)


def _band(fig, x, lo, hi, color, row=None, col=None):
    kw = dict(row=row, col=col) if row else {}
    fig.add_trace(go.Scatter(x=list(x) + list(x)[::-1], y=list(hi) + list(lo)[::-1], fill="toself", fillcolor=color,
                             opacity=0.15, line=dict(width=0), hoverinfo="skip", showlegend=False), **kw)


def fig_drying():
    d, q = _ts("drying_nmp_digitized.csv"), _ts("drying_quality_table5.csv")
    fig = make_subplots(rows=1, cols=2, column_widths=[0.56, 0.44], horizontal_spacing=0.12,
                        subplot_titles=("100°C · 1 m/s 대표 건조 곡선 (Fig.4, 18점 추출)", "건조속도 vs 표면 크랙 (Table 5)"))
    fig.add_trace(go.Scatter(x=d.time_s, y=d.nmp_kg_per_kg_dry, mode="lines+markers", line=dict(color="#367AC1", width=2.5),
                             name="NMP 잔량", hovertemplate="%{x:.0f} s · %{y:.3f} kg/kg<extra></extra>"), row=1, col=1)
    fig.add_annotation(x=640, y=0.25, ax=470, ay=1.15, xref="x1", yref="y1", axref="x1", ayref="y1", text="후반 감률 구간",
                       showarrow=True, arrowhead=2, font=dict(color="#627486"))
    fig.add_trace(go.Scatter(x=q.rate_1e4_kg_m2_s, y=q.uncalendered_crack_pct, mode="markers+text", name="조건별 평균 ± SD",
                             error_x=dict(type="data", array=q.rate_sd, color="#D5BA92"),
                             error_y=dict(type="data", array=q.crack_sd, color="#D5BA92"), marker=dict(size=11, color="#B77928"),
                             text=[f"{int(t)}°C/{v:g} m/s" for t, v in zip(q.temperature_c, q.air_speed_m_s)], textposition="top center",
                             hovertemplate="속도 %{x:.2f} · 크랙 %{y:.2f}%<extra></extra>"), row=1, col=2)
    fig.update_xaxes(title_text="건조 경과 시간 (s)", row=1, col=1)
    fig.update_yaxes(title_text="NMP 잔량 (kg/kg 건조 전극)", row=1, col=1)
    fig.update_xaxes(title_text="정률 건조속도 (×10⁻⁴ kg/m²/s)", range=[0, 4.2], row=1, col=2)
    fig.update_yaxes(title_text="캘린더 전 크랙 면적 (%)", range=[0, 14], row=1, col=2)
    return _layout(fig, 400)


def fig_formation(temps, individual):
    d = _ts("formation_cycle_capacity.csv")
    fig = make_subplots(rows=1, cols=len(temps), shared_yaxes=True, horizontal_spacing=0.06,
                        subplot_titles=[("후속 사이클 시험: 실온" if t == "RT" else "후속 사이클 시험: 45°C") for t in temps])
    for j, t in enumerate(temps, start=1):
        part = d[d.aging_temperature == t]
        for proto, gr in part.groupby("protocol"):
            lab, col = PROTO[proto]
            s = gr.groupby("cycle_index").retention_pct
            med, lo, hi = s.median(), s.quantile(.25), s.quantile(.75)
            if individual:
                for cid, c in gr.groupby("cell_id"):
                    fig.add_trace(go.Scatter(x=c.cycle_index, y=c.retention_pct, mode="lines", line=dict(color=col, width=0.8),
                                             opacity=0.3, showlegend=False, hovertemplate=f"셀 {cid} · %{{y:.1f}}%<extra></extra>"), row=1, col=j)
            _band(fig, med.index, lo, hi, col, 1, j)
            fig.add_trace(go.Scatter(x=med.index, y=med, mode="lines+markers", line=dict(color=col, width=3),
                                     name=f"{lab} (n={gr.cell_id.nunique()})", showlegend=(j == 1), legendgroup=proto,
                                     hovertemplate=f"{lab} · cycle %{{x}} · 중앙값 %{{y:.1f}}%<extra></extra>"), row=1, col=j)
        fig.add_hline(y=80, line_dash="dash", line_color=GRAY, row=1, col=j)
        fig.update_xaxes(title_text="후속 사이클 번호 (달력 시간 아님)", row=1, col=j)
    fig.update_yaxes(title_text="C/3 용량 / 각 셀 cycle 2 용량 (%)", range=[65, 103], row=1, col=1)
    return _layout(fig, 400)


def fig_rest(individual):
    d = _ts("formation_rest_voltage.csv")
    fig = make_subplots(rows=1, cols=2, column_widths=[0.56, 0.44], horizontal_spacing=0.12,
                        subplot_titles=("휴지 시작 대비 전압 하락 (6 h, 39셀)", "각 1 h 구간의 전압 하락"))
    for proto, gr in d.groupby("protocol"):
        lab, col = PROTO[proto]
        s = gr.groupby("rest_time_h").voltage_drop_mv
        med, lo, hi = s.median(), s.quantile(.25), s.quantile(.75)
        if individual:
            for cid, c in gr.groupby("cell_id"):
                fig.add_trace(go.Scatter(x=c.rest_time_h, y=c.voltage_drop_mv, mode="lines", line=dict(color=col, width=0.8),
                                         opacity=0.3, showlegend=False, hovertemplate=f"셀 {cid} · %{{y:.1f}} mV<extra></extra>"), row=1, col=1)
        _band(fig, med.index, lo, hi, col, 1, 1)
        fig.add_trace(go.Scatter(x=med.index, y=med, mode="lines+markers", line=dict(color=col, width=3), name=f"{lab} (n={gr.cell_id.nunique()})",
                                 legendgroup=proto, hovertemplate=f"{lab} · %{{x}} h · %{{y:.1f}} mV<extra></extra>"), row=1, col=1)
        inc = gr.pivot(index="cell_id", columns="rest_time_h", values="voltage_drop_mv").diff(axis=1).iloc[:, 1:].median()
        fig.add_trace(go.Scatter(x=inc.index, y=inc, mode="lines+markers", line=dict(color=col, width=3), showlegend=False, legendgroup=proto,
                                 hovertemplate=f"{lab} · ~%{{x}} h 구간 · %{{y:.1f}} mV<extra></extra>"), row=1, col=2)
    fig.add_vline(x=40 / 60, line_dash="dash", line_color="#7861B8", row=1, col=1)
    fig.add_annotation(x=40 / 60, y=28, xref="x1", yref="y1", text="40분 = 화성 추가 점유 예산", showarrow=False, xanchor="left",
                       font=dict(color="#7861B8", size=12))
    fig.update_xaxes(title_text="휴지 경과 시간 (h)", range=[0, 6.3], row=1, col=1)
    fig.update_yaxes(title_text="전압 하락 (mV)", range=[0, 30], row=1, col=1)
    fig.update_xaxes(title_text="관찰 구간 종료 시점 (h)", range=[0.7, 6.3], row=1, col=2)
    fig.update_yaxes(title_text="직전 1 h 하락 (mV)", range=[0, 15], row=1, col=2)
    return _layout(fig, 400)


def _source_box(idx, csv_name, png_fn):
    import json
    src = json.loads((TS / "sources.json").read_text(encoding="utf-8"))["sources"][idx]
    with st.expander("출처 · 가공 방법 · 한계 · 원자료"):
        st.markdown(md(f"**{src['authors']} ({src['year']})** - {src['title']}, *{src['journal']}* · [DOI]({src['url']})"
                       + (f" · [저자 공개 CSV]({src['data_url']})" if src.get("data_url") else "")))
        st.markdown(md(f"- **원문 위치**: {src['locator']}\n- **조건**: {src['conditions']}\n- **가공**: {src['processing']}\n"
                       f"- **한계**: {src['limits']}\n- **라이선스**: {src['license']}"))
        table(_ts(csv_name), hide_index=True, width="stretch", height=240)
        st.download_button("⬇ 시계열 원자료 CSV", (TS / csv_name).read_bytes(), file_name=csv_name, mime="text/csv", key=f"tscsv_{csv_name}")


def tab_validation(res):
    cd = (res.get("evidence") or {}).get("candidates")
    if not cd:
        return
    g = _ok(cd)
    rm, up = g("roadmap"), g("upside")
    hz = {r["lever_id"]: r for r in ((rm or {}).get("horizon") or {}).get("rows", [])}
    import timeseries_evidence as tse
    st.markdown("### 공정별 검증 계획 - 공개 실험 시계열로 본 검증 포인트")
    st.info("아래 그래프는 **공개 논문의 실험 데이터**다(C사 실측 아님). 결론 숫자나 품질 관문 상태를 바꾸지 않고, "
            "각 공정에서 **무엇을 재고 어떤 기준을 넘어야 하는지**를 보여 주는 근거로만 쓴다. C사 값은 1년차 파일럿에서 채운다.")

    def card(lids):
        for lid in lids:
            r = hz.get(lid)
            if not r:
                continue
            with st.container(border=True):
                st.markdown(md(f"**{r['name']}** · `{r['horizon']}` · {r['when']}"))
                st.markdown(md(f"- **근거 성격**: {r['nature']}\n- **측정**: {r['method']}\n- **통과 기준**: {r['pass']}"))

    st.markdown("#### ① 건조 - 후반 용매 제거와 품질을 함께")
    st.plotly_chart(fig_drying(), width="stretch")
    st.caption("읽을 점: NMP 제거가 후반에 느려지고(감률 구간), 건조속도가 클수록 크랙이 늘었다 → 고형분 상향으로 줄어든 용매량만으로 "
               "1.2배 속도의 출구 품질을 승인할 수 없다. Bryntesen 2023(R27), NMC111/NMP 실험실 열풍건조 - 60→65 wt%·NIR 비교시험이 아님.")
    a, b = st.columns(2)
    with a:
        card(["DRY-HSC"])
    with b:
        card(["DRY-RAD"])
    _source_box(0, "drying_nmp_digitized.csv", tse.plot_drying)

    st.markdown("#### ② 화성 - 고속 화성 후 수명을 같은 셀로 추적")
    c1, c2 = st.columns([1, 1])
    temp = c1.radio("후속 시험 온도", ["둘 다", "실온", "45°C"], horizontal=True, key="ts_temp")
    ind = c2.toggle("개별 셀 곡선 표시", key="ts_cells")
    temps = {"둘 다": ["RT", "45C"], "실온": ["RT"], "45°C": ["45C"]}[temp]
    st.plotly_chart(fig_formation(temps, ind), width="stretch")
    st.caption("읽을 점: 이 셀 설계(NMC111/흑연 2.36 Ah, 39셀)에서는 고속 화성군의 cycle 364 용량 중앙값이 더 높았다"
               "(실온 91.6% vs 79.0%, 45°C 87.6% vs 78.1% - 저자 CSV로 계산한 기술통계). 선 = 중앙값, 음영 = 25~75% 범위(신뢰구간 아님). "
               "Weng 14 h/56 h는 진단 제외 시간이라 C사 20→16 h와 다르다 → C사 셀로 대조 시험이 필요하다.".replace("~", "\\~"))
    card(["FOR-FAST"])
    _source_box(1, "formation_cycle_capacity.csv", tse.plot_cycle)

    st.markdown("#### ③ 화성 후 전압 - 조기 검사 시간과 채널 점유를 분리")
    ind2 = st.toggle("개별 셀 곡선 표시 ", key="ts_cells_rest")
    st.plotly_chart(fig_rest(ind2), width="stretch")
    st.caption("읽을 점: 휴지 초기의 전압 하락에는 완화(relaxation)가 섞여 있고 시간이 지나며 줄어든다. 6 h 관찰을 화성 채널에 그대로 붙이면 "
               "추가 점유 40분 예산을 넘는다 → 별도 측정기로 분리할지 정해야 한다. 미세단락 정답 라벨이 없어 검출력·14일 단축의 근거는 아니다.")
    card(["AGE-RACK", "SHADOW"])
    _source_box(1, "formation_rest_voltage.csv", tse.plot_rest)

    sh = (up or {}).get("shadow")
    if sh:
        st.markdown("#### 에이징 섀도 모드 4단계 관문")
        table(pd.DataFrame([{"단계": x["stage"], "운영": x["what"], "다음 단계 조건": x["gate"]} for x in sh["stages"]]),
                     hide_index=True, width="stretch")
        st.caption(md(sh.get("n_note", "")))
        pt = sh.get("period_table")
        if pt:
            st.caption(md(f"{pt['formula']} · 하루 {pt['cells_per_day'][0]:,}~{pt['cells_per_day'][1]:,}셀: "
                          + " / ".join(f"{r['label']} → {r['days'][0]:.1f}~{r['days'][1]:.1f}일" for r in pt["rows"])))
    bnd = next((b for b in cd.get("boundaries", []) if b["kind"] == "에이징 승인 슬롯"), None)
    if bnd:
        st.info(md("슬롯 비증설 평균 점유일 한계 12.315일은 **물류 슬롯 조건**이지 품질 보장 기간이 아니다. " + bnd["text"]))
    st.caption("이 공개 자료로도 아직 확인할 수 없는 것: C사 고정부하 f, NIR 현장 절감률, 승인 슬롯 +13.68%, 결함 양성 299개 검출력 - 모두 기존 상태(미확인) 유지.")


# ------------------------------------------------------------------ 탭 3 (관문 매트릭스)
def tab_gates(res):
    ev = res.get("evidence") or {}
    cd = ev.get("candidates")
    if not cd:
        return
    clean = ev.get("clean") or {}
    fm = {f["fmea_id"]: f for f in clean.get("fmea", [])}
    lv = {l["lever_id"]: l for l in clean.get("levers", [])}
    rows = []
    for m in cd["priority"]["mandatory"]:
        f = fm.get(m["fmea_id"], {})
        l = lv.get(m["lever_id"], {})
        rows.append({"FMEA": m["fmea_id"], "공정": l.get("system", "-"), "레버": l.get("name_ko", m["lever_id"]),
                     "안전": "예" if m["safety"] else "-", "근거 등급": f.get("evidence_grade") or "-",
                     "고장모드": f.get("failure_mode", ""), "통과 관문": m["gate"], "상태": m["status"]})
    df = pd.DataFrame(rows)
    n_s = sum(1 for r in rows if r["안전"] == "예")
    st.markdown(f"### 안전·품질 관문 매트릭스 - {len(rows)}건 (안전 {n_s}건)")
    st.caption("판정과 무관하게 다음 단계로 가기 전에 통과해야 하는 관문. 위험도 점수(RPN)는 일부러 계산하지 않는다.")
    f1, f2, f3, f4 = st.columns(4)
    opt = lambda c: sorted(df[c].unique().tolist())
    s1 = f1.multiselect("공정", opt("공정"), key="g_sys")
    s2 = f2.multiselect("안전 관문", opt("안전"), key="g_saf")
    s3 = f3.multiselect("근거 등급", opt("근거 등급"), key="g_grd")
    s4 = f4.multiselect("확인 상태", opt("상태"), key="g_st")
    for col, sv in (("공정", s1), ("안전", s2), ("근거 등급", s3), ("상태", s4)):
        if sv:
            df = df[df[col].isin(sv)]
    table(df, hide_index=True, width="stretch", height=min(38 * (len(df) + 1), 520))
    st.caption(f"표시 {len(df)}건 · 근거 등급 A~E(E = 팀 판단, 원문 확인 필요)")
    st.divider()
