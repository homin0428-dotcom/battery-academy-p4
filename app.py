"""배터리셀 공장 병목공정 개선안 - Streamlit UI v3 (5개 탭).

계산 공식은 이 파일에 없다. 모든 계산은 core.run_scenario 결과를 표시만 한다.
"""
import hashlib
import json
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

import candidates as cand_mod
import core
import reporting
import ui_v3
import importlib
importlib.reload(ui_v3)   # 배포 서버가 이전 버전 모듈을 메모리에 남겨 두는 경우 대비 (화면 모듈만, 계산 엔진 아님)

def result_key(res, scenario, quality_overrides):
    """다운로드 파일이 현재 화면 결과와 같은 입력에서 만들어졌는지 확인하는 키."""
    payload = {"scenario": scenario, "config": res.get("config_hash"), "quality": quality_overrides or {}}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


st.set_page_config(page_title="배터리셀 공장 병목공정 개선안 - 근거 기반 판정", layout="wide")
CFG = core.load_config()
SCEN = {k: v["label_ko"] for k, v in CFG["scenarios"].items()}
ss = st.session_state
if "_goto" in ss:          # 위젯 생성 전에만 위젯 키를 바꿀 수 있다
    ss["scenario"] = ss.pop("_goto")
ss.setdefault("custom_overrides", {})
ss.setdefault("quality_overrides", {})
ss.setdefault("kb_confirm", {})      # 근거 FMEA 품질 관문 확인 기록 {fmea_id: {status, memo, conditions}}
ss.setdefault("report_files", None)
ss.setdefault("report_key", None)

scenario = ss.get("scenario", "representative")
overrides = dict(ss["custom_overrides"]) if scenario == "custom" else {}
if ss["kb_confirm"]:
    overrides["kb_quality_confirmations"] = ss["kb_confirm"]
res = core.run_scenario(CFG, scenario, overrides, quality_overrides=ss["quality_overrides"] or None)
base_vals, base_meta = core.resolve_inputs(CFG, "representative")
CUR_KEY = result_key(res, scenario, {"pfmea": ss["quality_overrides"], "kb": ss["kb_confirm"]})
if ss["report_files"] is not None and ss["report_key"] != CUR_KEY:
    # 시나리오·입력·품질 상태가 바뀌면 이전 보고서를 무효화한다 (화면과 다운로드 불일치 방지)
    ss["report_files"], ss["report_key"] = None, None
    ss["report_invalidated"] = True

REPO = "https://github.com/homin0428-dotcom/battery-academy-p4"
OUT = Path(__file__).resolve().parent / "outputs"
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap');
html, body, [class*="css"], .stMarkdown, .stDataFrame, button, input { font-family: 'Noto Sans KR', sans-serif; }
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] { visibility: hidden; height: 0; }
.block-container { padding-top: 3.2rem; max-width: 1280px; }
.hero { background: linear-gradient(120deg, #0f2a3a 0%, #173B50 45%, #237B80 100%); border-radius: 18px;
        padding: 30px 34px 26px; color: #fff; box-shadow: 0 10px 30px rgba(23,59,80,.25); margin-bottom: 18px; }
.hero .eyebrow { font-size: 13px; letter-spacing: .12em; text-transform: uppercase; opacity: .75; font-weight: 500; }
.hero h1 { color: #fff; font-size: 34px; font-weight: 900; line-height: 1.25; margin: 6px 0 8px; padding: 0; }
.hero .sub { font-size: 15px; opacity: .85; }
.hero .verdict { display: inline-block; margin-top: 16px; background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.28);
                 border-radius: 999px; padding: 7px 16px; font-size: 14px; font-weight: 500; }
.hero .verdict b { color: #8FF0D6; }
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 4px 0 16px; }
.kpi { background: #fff; border: 1px solid #E3ECEE; border-top: 4px solid #237B80; border-radius: 14px; padding: 16px 18px;
       box-shadow: 0 2px 10px rgba(23,59,80,.06); }
.kpi.amber { border-top-color: #D9952B; }
.kpi .t { font-size: 13px; color: #5F6F77; font-weight: 500; }
.kpi .v { font-size: 30px; font-weight: 900; color: #173B50; margin: 4px 0 2px; letter-spacing: -.02em; }
.kpi .s { font-size: 13px; color: #5F6F77; }
.lights { width: 100%; border-collapse: separate; border-spacing: 0; margin: 6px 0 10px; font-size: 14px; }
.lights th { text-align: left; color: #5F6F77; font-weight: 500; padding: 8px 10px; border-bottom: 2px solid #E3ECEE; }
.lights td { padding: 9px 10px; border-bottom: 1px solid #EEF3F4; }
.dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
.g { background: #2BB673; } .r { background: #E5534B; } .y { background: #D9952B; }
.stTabs [data-baseweb="tab-list"] { gap: 10px; width: 100%; border-bottom: 2px solid #E3ECEE; }
.stTabs [data-baseweb="tab"] { flex: 1 1 0; justify-content: center; min-height: 54px; background: #F2F6F7;
    border-radius: 12px 12px 0 0; padding: 12px 20px; font-weight: 600; }
.stTabs [data-baseweb="tab"] p { font-size: 15px; }
.stTabs [data-baseweb="tab"]:hover { background: #E2EEEF; }
.stTabs [aria-selected="true"] { background: #173B50 !important; color: #fff !important; }
.stTabs [aria-selected="true"] p { color: #fff !important; }
.stTabs [data-baseweb="tab-highlight"] { background-color: #237B80 !important; height: 4px; }
.stTabs [data-baseweb="tab-border"] { display: none; }
.stTabs [role="tablist"] { display: flex; gap: 10px; width: 100%; border-bottom: 2px solid #E3ECEE; }
.stTabs [role="tab"] { flex: 1 1 0; justify-content: center; text-align: center; min-height: 54px; background: #F2F6F7;
    border-radius: 12px 12px 0 0; padding: 12px 20px; font-weight: 600; }
.stTabs [role="tab"] p { font-size: 15px; }
.stTabs [role="tab"]:hover { background: #E2EEEF; }
.stTabs [role="tab"][data-selected="true"], .stTabs [role="tab"][aria-selected="true"] { background: #173B50 !important; color: #fff !important; }
.stTabs [role="tab"][data-selected="true"] p { color: #fff !important; }
div.stButton > button { border-radius: 10px; border: 1px solid #237B80; color: #173B50; font-weight: 700; background: #fff; }
div.stButton > button:hover { background: #237B80; color: #fff; }
div.stDownloadButton > button { background: #fff; width: 100%; min-height: 46px; border-radius: 10px; border: 1px solid #237B80; color: #173B50; font-weight: 700; }
div.stDownloadButton > button:hover { background: #237B80; color: #fff; }
.topbar { font-size: 13px; color: #5F6F77; letter-spacing: .04em; font-weight: 500; }
.topbar a { color: #237B80; text-decoration: none; }
.st-key-dl_top_pdf button { background: #173B50 !important; color: #fff !important; border: none !important; border-radius: 10px !important;
    font-size: 16px !important; font-weight: 700 !important; padding: 12px 18px !important; box-shadow: 0 6px 16px rgba(23,59,80,.28); }
.st-key-dl_top_pdf button:hover { background: #237B80 !important; }
.wtbl-wrap { overflow: auto; border: 1px solid #E3ECEE; border-radius: 10px; margin: 4px 0 14px; -webkit-overflow-scrolling: touch; }
.wtbl { width: 100%; border-collapse: collapse; font-size: 14px; }
.wtbl th { position: sticky; top: 0; z-index: 1; background: #F2F6F7; color: #4A5A63; font-weight: 600; text-align: left;
           padding: 9px 12px; border-bottom: 1px solid #E3ECEE; white-space: nowrap; }
.wtbl td { padding: 9px 12px; border-bottom: 1px solid #EEF3F4; vertical-align: top; line-height: 1.5; word-break: keep-all; overflow-wrap: anywhere; color: #1F2D35; }
.wtbl td.nw { white-space: nowrap; }
.wtbl .w1 { min-width: 150px; }
.wtbl .w2 { min-width: 170px; }
.wtbl .w3 { min-width: 240px; }
.wtbl .w4 { min-width: 320px; }
.wtbl tr:last-child td { border-bottom: none; }
.wtbl tbody tr:hover td { background: #F7FAFA; }
@media (max-width: 700px) { .wtbl { font-size: 12.5px; min-width: 620px; } .wtbl td, .wtbl th { padding: 7px 9px; } }
@media (max-width: 900px) { .stTabs [data-baseweb="tab"], .stTabs [role="tab"] { flex: 0 0 auto; }  .kpis { grid-template-columns: repeat(2, 1fr); } .hero h1 { font-size: 26px; } }
</style>""", unsafe_allow_html=True)

_cd0 = (res.get("evidence") or {}).get("candidates") or {}
_sel0 = next((c for c in _cd0.get("candidates", []) if c["id"] == _cd0.get("selected")), None)
_esc = lambda t: str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
_tl, _tr = st.columns([4, 1.25], vertical_alignment="center")
_tl.markdown(f'<div class="topbar">BATTERY ACADEMY 2026 · 문제 4 &nbsp;|&nbsp; <a href="{REPO}" target="_blank">GitHub 저장소</a></div>',
             unsafe_allow_html=True)
_pdf = OUT / "evidence_report.pdf"
if _pdf.exists():
    _tr.download_button("📄 PDF 보고서 다운로드", _pdf.read_bytes(), file_name="battery_p4_evidence_report.pdf",
                        mime="application/pdf", type="primary", key="dl_top_pdf", width="stretch")
st.markdown(f"""<div class="hero"><div class="eyebrow">2026 배터리아카데미 · 문제 4</div>
<h1>배터리셀 공장 병목공정 개선안<br>근거 기반 판정 프로그램</h1>
<div class="sub">C사 10 → 12 GWh · 전력 원단위 -30% · 화성·에이징 / 전극건조·드라이룸</div>
{f'<div class="verdict">조건부 추천 <b>{_sel0["id"]}</b> - {_esc(_sel0["name"])} · 전력 목표 계산상 충족, 현장 확인 {_sel0["n_unk"]}개 조건</div>' if _sel0 else ''}
</div>""", unsafe_allow_html=True)
if _sel0:
    _dz0 = _cd0.get("design") if isinstance(_cd0.get("design"), dict) and "error" not in _cd0.get("design") else {}
    _cp0 = (_cd0.get("capacity") or {}).get("plant") or {}
    _m0 = ((_dz0.get("money") or {}).get("cards") or [None])[0]
    _cards = [("전력 원단위 절감", f"{_sel0['saving'][1] * 100:.1f}%", f"목표 30% 대비 {(_sel0['saving'][1] - 0.30) * 100:+.1f}%p · 범위 {_sel0['saving'][0] * 100:.1f}~{_sel0['saving'][2] * 100:.1f}%", ""),
              ("12 GWh 총전력", f"{_sel0['E_typ']:.2f} pt", f"현재 100 · 무개선 {_cd0['baseline']['E_q_no_change']:.1f} · 목표 ≤ 84 pt (여유 {_sel0['margin_pt']:+.2f})", ""),
              ("공장 처리능력", f"{_cp0.get('plant', 0):.3f}배" if _cp0 else "-",
               f"병목 {_cp0.get('bottleneck')} · 승인 슬롯 확보 시 1.2배" if _cp0 else "", "amber"),
              ("연 전력비 (현재 대비)", f"{_m0['krw_eok'][0]:.0f}~{_m0['krw_eok'][1]:.0f}억↓" if _m0 else "-", "생산 20% 늘려도 총액 감소", "")]
    st.markdown('<div class="kpis">' + "".join(f'<div class="kpi {c}"><div class="t">{t}</div><div class="v">{v}</div><div class="s">{_esc(sb)}</div></div>'
                                               for t, v, sb, c in _cards) + "</div>", unsafe_allow_html=True)
    # 자료 다운로드 - 저장소에 함께 배포된 공식 결과물(outputs/)
    _dl = [("📊 숫자 원본 results.json", "results.json", "application/json"),
           ("📈 후보 비교 CSV", "kb_candidates.csv", "text/csv"),
           ("🧾 요약 보고서 PDF", "result_report.pdf", "application/pdf")]
    _dc = st.columns(len(_dl))
    for _c, (_lab, _fn, _mime) in zip(_dc, _dl):
        _f = OUT / _fn
        if _f.exists():
            _c.download_button(_lab, _f.read_bytes(), file_name=f"battery_p4_{_fn}", mime=_mime, key=f"dl_{_fn}", width="stretch")
    st.caption(f"[GitHub 저장소]({REPO}) · 다운로드 파일은 공식 설정(설계 고정 D2)으로 생성된 결과물이다. "
               "입력을 바꾼 결과는 '입력 · 계산' 탭에서 새로 만들 수 있다.")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 핵심 성과 분석", "🔬 공정별 검증 계획", "🛡️ 관문 매트릭스 · 근거", "⚙️ 입력 · 계산", "📁 상세 표 · 부록"])


def parse_opt(text):
    text = (text or "").strip()
    if text == "":
        return None
    return float(text)


def _cell(k, v):
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return None
    if k in ("fan_affinity", "supply_temp_ok"):
        return core.to_bool(v, k)   # bool("False")==True 방지: 명시적 변환, 해석 불가 값은 InputError
    return v if k == "name" else float(v)


# ---------------------------------------------------------------- 탭 1
with tab1:
    ui_v3.tab_analysis(res)

with tab2:
    ui_v3.tab_validation(res)

with tab3:
    ui_v3.tab_gates(res)
    pf = res.get("pfmea", {})
    if pf.get("status") == core.NUM_ERR:
        st.error(f"PFMEA 입력 오류: {pf['error']}")
        if ss["quality_overrides"] and st.button("품질 상태 변경 초기화"):
            ss["quality_overrides"] = {}
            st.rerun()
    table = core.pfmea_table(res)
    ui_v3.table(pd.DataFrame([{k: v for k, v in t.items() if k not in ("risk_id", "rows", "quality")} for t in table]),
                 hide_index=True, width="stretch")
    c = pf.get("counts", {})
    st.caption(f"계산 반영 효과 {c.get('reflected', 0)}건 · 정량 부담 미확인 {c.get('burden_unknown', 0)}건 · "
               f"품질 검증 필요 위험 경로 {c.get('quality_open', 0)}건 · 품질 미충족(적용 제외) {c.get('excluded', 0)}건. "
               "품질 미확인과 계산 입력 누락은 서로 다른 상태입니다.")
    st.markdown("##### PFMEA → 계산 연결 범위")
    st.caption("자동 반영: 추가 채널 점유시간 → 화성 처리능력, 개별 추가 전력 → P_add(항목별 합산 모드). "
               "그 외 효과는 자동 연결되지 않으며, 표시된 시나리오 입력에서 수동으로 검토합니다. "
               "보조열처럼 구간 지정이 필요한 값은 자동 합산·배분하지 않습니다.")
    link_rows = [{"조치": r["action_id"], "효과": core.PARAM_KO.get(r["impact_parameter"], r["impact_parameter"]),
                  "연결 방식": r.get("link_type", "-"), "반영 위치·방법": r.get("link_note", ""),
                  "계산 상태": r["calc_status"]} for r in pf.get("rows", [])]
    if link_rows:
        ui_v3.table(pd.DataFrame(link_rows), hide_index=True, width="stretch")
    if pf.get("manual_pending"):
        st.warning(f"자동 연결되지 않은 미반영 항목 {len(pf['manual_pending'])}건: {', '.join(pf['manual_pending'])} — "
                   "최종 결론에도 이 사실이 표시됩니다.")
    ev = {e["evidence_id"]: e for e in core.load_csv(core.DEFAULT_EVIDENCE)}
    for t in table:
        with st.expander(f"{t['공정 변경']} — {t['실패 경로']}"):
            for r in t["rows"]:
                st.markdown(f"**{r['action_id']}** · {r['control_action']}")
                st.write(f"- 계산 영향: {core.PARAM_KO.get(r['impact_parameter'], r['impact_parameter'])} = "
                         f"{r['impact_value'] if r['impact_value'] not in ('', None) else '미확인'} {r['impact_unit']} "
                         f"({r['accounting_location']}) → {core.TARGET_KO.get(r['calc_target'], r['calc_target'])} [{r['calc_status']}]")
                st.write(f"- 품질 상태(조치): {r['quality_status']} · 연결: {r.get('link_type', '-')} — {r.get('link_note', '')}")
                st.write(f"- 가정·적용 한계: {r['applicability_note']}")
                st.write(f"- 누락 정보: {r['missing_evidence']}")
                st.write(f"- 추가 검증 필요: {r['next_check']}")
                for eid in r["evidence_id"].split(";"):
                    e = ev.get(eid)
                    if e:
                        st.write(f"- 근거 {eid}: {e['title']} (DOI: {e['doi'] or '없음'}) — {e['verification_status']}")
            rid = t["risk_id"]
            cur = t["quality"]   # 첫 행이 아니라 위험 경로의 모든 조치를 집계한 상태
            st.caption(f"위험 경로 종합 품질: {t['확인 상태']} — 아래에서 변경하면 이 위험의 모든 조치에 적용됩니다.")
            q1, q2, q3 = st.columns([1, 3, 1])
            new = q1.selectbox("품질 상태", core.Q_STATES, index=core.Q_STATES.index(cur), key=f"qs_{rid}")
            note = q2.text_input("근거 메모(상태 변경 시 필수)", key=f"qn_{rid}")
            if q3.button("적용", key=f"qb_{rid}"):
                ss["quality_overrides"] = {**ss["quality_overrides"], rid: {"status": new, "note": note}}
                st.rerun()
    st.caption("PFMEA 확률·RPN·AP·CEI 등은 생성하지 않습니다. 전체 필드는 pfmea_summary.csv에 있습니다.")

    # ---- 근거 FMEA 데이터셋 (레버별 판정표 · 근거 추적 · 품질 관문 · 데이터셋 검증)
    st.divider()
    st.markdown("### 근거 FMEA 데이터셋")
    evd = res.get("evidence", {})
    if evd.get("status") != core.NUM_OK:
        st.error(evd.get("error", "근거 판정을 실행하지 못했습니다."))
    else:
        cnt = evd["counts"]
        st.caption(f"자료 {cnt['sources']}개 · 정량효과 {cnt['effects']}건(계산 사용 {cnt['calc']} · 참고 전용 {cnt['ref']} · "
                   f"제외 {cnt['excl']}) · 근거FMEA {cnt['fmea']}건 · 검증 오류 {evd['n_errors']}건. "
                   "판정은 범주(근거 충분/약함/참고만/없음)로만 하며 점수를 만들지 않습니다.")
        if evd["n_errors"]:
            st.error("데이터셋 검증 오류 - 해당 행은 판정에서 제외됨")
            ui_v3.table(pd.DataFrame([i for i in evd["issues"] if i["level"] == "error"]), hide_index=True, width="stretch")
        st.markdown("##### 레버별 근거 판정표")
        ui_v3.table(pd.DataFrame([{
            "레버": l["lever_id"], "이름": l["name"], "계통": l["system"], "선택": "선택" if l["selected"] else "",
            "판정": l["judge"],
            "계통 기준 절감(%)": "-" if not l["range"] else f"{l['range'][0] * 100:.1f}~{l['range'][2] * 100:.1f} (대표 {l['range'][1] * 100:.1f})",
            "계산/참고": f"{l['n_calc']}/{l['n_ref']}", "최고 등급": l["best_grade"],
            "주요 고장모드": "; ".join(l["failure_modes"]), "다음 조치": "; ".join(l["todo"])} for l in evd["levers"]]),
            hide_index=True, width="stretch")
        st.markdown("##### 근거 추적표 (수치 → 근거)")
        ui_v3.table(pd.DataFrame([{
            "ID": e["effect_id"], "레버": e["lever_id"], "지표": e["metric"], "측정범위": e["boundary"], "환산": e["how"],
            "계통 기준(%)": None if e["typ"] is None or e["role"] != "saving" else round(e["typ"] * 100, 1),
            "사용": e["use"], "적용": e["transfer"], "근거": e["source_id"], "위치": e["locator"],
            "등급": e["grade"], "확인": e["verification"], "근거요약": e["excerpt"]} for e in evd["effects"]]),
            hide_index=True, width="stretch")
        qrows = (evd.get("quality") or {}).get("rows", [])
        if qrows:
            import evidence_engine as ee
            st.markdown("##### 추천 조합의 품질 관문 - 확인 기록")
            qc = evd["quality"]["counts"]
            st.caption("관문을 '확인'으로 기록하면 그 시점의 공정 조건(화성 시간·채널비·에이징 일수·가열원 등)이 함께 저장됩니다. "
                       "이후 그 조건을 바꾸면 확인을 승계하지 않고 '재검증 필요'로 돌아갑니다. 확인에는 근거 메모(시험 번호·결과)가 필수입니다. "
                       f"현재: {' · '.join(f'{k} {v}' for k, v in qc.items() if v)} → 종합 판정 '{evd['overall']['label']}'")
            lev_f = st.multiselect("레버로 거르기", sorted({r["lever_id"] for r in qrows}), key="qgate_filter")
            shown = [r for r in qrows if not lev_f or r["lever_id"] in lev_f]
            df_q = pd.DataFrame([{"FMEA": r["fmea_id"], "레버": r["lever_id"], "고장모드": r["failure_mode"],
                                  "품질 관문": r["gate"], "판정 상태": r["status"], "바뀐 조건": "; ".join(r["changed"]),
                                  "기록": ss["kb_confirm"].get(r["fmea_id"], {}).get("status", "미기록"),
                                  "근거 메모": ss["kb_confirm"].get(r["fmea_id"], {}).get("memo", "")} for r in shown])
            ed = st.data_editor(df_q, hide_index=True, width="stretch", key="qgate_editor",
                                disabled=["FMEA", "레버", "고장모드", "품질 관문", "판정 상태", "바뀐 조건"],
                                column_config={"기록": st.column_config.SelectboxColumn(options=["미기록", "확인", "불합격"]),
                                               "고장모드": st.column_config.TextColumn(width="medium"),
                                               "품질 관문": st.column_config.TextColumn(width="large")})
            st.caption("표의 '기록' 칸에서 확인/불합격을 고르고 근거 메모를 적은 뒤 저장하면 판정이 다시 계산된다. 칸을 누르면 전체 글이 보인다.")
            b1, b3, b2, _bsp = st.columns([1, 1.15, 1, 2.2], vertical_alignment="center")
            if b1.button("품질 관문 기록 저장"):
                new, errs = dict(ss["kb_confirm"]), []
                for _, row in ed.iterrows():
                    fid, stt, memo = row["FMEA"], row["기록"], str(row["근거 메모"] or "").strip()
                    old = new.get(fid)
                    if stt == "미기록":
                        new.pop(fid, None)
                    elif old and old.get("status") == stt and old.get("memo") == memo:
                        continue   # 같은 기록은 그대로 둔다 (조건을 새로 찍지 않음 → 조건이 바뀌면 재검증 필요 유지)
                    else:
                        try:
                            new[fid] = ee.confirmation_record(evd["clean"], fid, stt, memo, res["inputs"])
                        except ValueError as e_:
                            errs.append(f"{fid}: {e_}")
                if errs:
                    st.error("저장 안 됨 - " + " / ".join(errs))
                else:
                    ss["kb_confirm"] = new
                    st.rerun()
            if ss["kb_confirm"] and b2.button("기록 모두 지우기"):
                ss["kb_confirm"] = {}
                st.rerun()
            b3.download_button("확인 기록 내보내기(.json)", json.dumps(ss["kb_confirm"], ensure_ascii=False, indent=2),
                               file_name="품질관문_확인기록.json", mime="application/json")
            with st.expander("저장해 둔 확인 기록 불러오기(.json)"):
                up = st.file_uploader("확인 기록 파일", type=["json"], key="qgate_upload")
            if up is not None and st.button("불러온 기록 적용"):
                try:
                    data = json.loads(up.getvalue().decode("utf-8"))
                    if not isinstance(data, dict):
                        raise ValueError("형식 오류")
                    ss["kb_confirm"] = data
                    st.rerun()
                except (ValueError, UnicodeDecodeError) as e_:
                    st.error(f"불러오기 실패: {e_}")
        tm = evd["time"]
        if tm.get("status") != "근거 없음":
            st.caption(f"화성시간 점검: 목표/기준 = {tm['target_ratio']:.2f}, 문헌 시간비 {tm['evidence_lo']:.2f}~{tm['evidence_hi']:.2f} → {tm['status']}")
        for p in evd["params"]:
            st.caption(f"파라미터 점검: {p['param']} 가정 {p['assumed']:g} vs 근거 {p['lo']:g}~{p['hi']:g} → {p['status']}")

# ---------------------------------------------------------------- 입력
with tab4:
    st.markdown("입력은 **사용자 조건** 시나리오에 적용됩니다. 비워 둔 항목은 *미확인*(0이 아님)으로 처리되어 해당 계산만 보류됩니다.")
    with st.form("inputs"):
        o = {}
        with st.expander("화성", expanded=True):
            c = st.columns(4)
            o["formation_h"] = c[0].number_input("화성 본공정 시간 [h]", 1.0, 60.0, float(base_vals["formation_h"]), 0.25)
            src = c[1].radio("추가 점유 출처", ["input", "pfmea"], index=1,
                             format_func=lambda x: {"input": "직접 입력", "pfmea": "PFMEA 효과 합계"}[x])
            o["added_occupancy_source"] = src
            if src == "input":
                o["added_occupancy_h"] = c[2].number_input("추가 점유시간 [h]", 0.0, 30.0, 0.25, 0.25)
            o["channel_ratio"] = c[3].number_input("채널비 [비율]", 0.1, 3.0, float(base_vals["channel_ratio"]), 0.01)
            with st.expander("출처·단위·고급 입력"):
                o["availability_ratio"] = st.number_input("가동률 [0~1]", 0.01, 1.0, float(base_vals["availability_ratio"]), 0.01)
                o["yield_ratio"] = st.number_input("수율 [0~1]", 0.01, 1.0, float(base_vals["yield_ratio"]), 0.01)
                bc = st.text_input("기존 채널 수 [개] (비우면 미확인 - 비율만 표시)", "")
        with st.expander("에이징·공간"):
            c = st.columns(2)
            o["current_utilization"] = c[0].number_input("현재 슬롯 사용률 [0~1]", 0.01, 1.0, float(base_vals["current_utilization"]), 0.01)
            o["planned_utilization"] = c[1].number_input("계획 슬롯 사용률 [0~1]", 0.01, 1.0, float(base_vals["planned_utilization"]), 0.01)
            with st.expander("출처·단위·고급 입력 (대기공간; 비우면 미확인)"):
                sp = {k: st.text_input(f"{k} [{base_meta[k]['unit']}]", "") for k in
                      ("old_throughput_per_day", "old_wait_days", "new_throughput_per_day", "new_wait_days",
                       "area_per_cell", "slots_per_area", "conversion_fraction")}
            st.markdown("**구역별 입력 (선택)** — 행을 추가하면 구역별로 계산하고, 비워 두면 위 단일 구역 계산을 사용합니다. "
                        "사용률을 비우면 위의 전체 사용률을 씁니다.")
            azed = st.data_editor(
                pd.DataFrame({k: pd.Series(dtype="object" if k == "name" else "float64") for k in core.ZONE_KEYS}),
                num_rows="dynamic", hide_index=True, width="stretch", key="aging_zone_editor",
                column_config={k: st.column_config.NumberColumn(k) for k in core.ZONE_KEYS if k != "name"})
        with st.expander("건조"):
            srcs = {"manual": "수동 절감률(공장 모델 r[0])", "mode_a": "모드 A (v10 단순화)", "mode_b": "모드 B (3구간 설계)"}
            o["drying_r_source"] = st.radio("공장 모델에 반영할 건조 절감률(하나만 선택)", list(srcs), format_func=srcs.get, horizontal=True)
            st.markdown("**모드 A** (a: 풍량비, s: 풍량 민감도, b: 히트펌프 열 비율)")
            c = st.columns(5)
            da = base_vals["drying_a"]
            a_in = {"a": c[0].number_input("a", 0.1, 1.0, float(da["a"]), 0.05),
                    "s": c[1].number_input("s", 0.0, 1.0, float(da["s"]), 0.05),
                    "b": c[2].number_input("b", 0.0, 1.0, float(da["b"]), 0.01),
                    "cop_h": c[3].number_input("COP_h", 1.01, 10.0, float(da["cop_h"]), 0.05),
                    "cop_c": c[4].number_input("COP_c", 0.1, 10.0, float(da["cop_c"]), 0.1)}
            o["drying_a"] = a_in
            o["drying_a_airflow_scope"] = st.selectbox(
                "모드 A 풍량 감소 a의 적용 범위", list(core.DRYING_SCOPES),
                format_func={"system": "건조 계통 전체 값", "zone": "특정 구간 값 (계통 전체 적용 시 차단)"}.get)
            st.markdown("**모드 B** — 정확히 3개 구간 (빈칸=미확인, 모드 A 값으로 채우지 않음)")
            zdf = pd.DataFrame(base_vals["drying_b_zones"])
            zed = st.data_editor(zdf, hide_index=True, width="stretch", key="zones_editor")
            gcols = st.columns(4)
            g_txt = {k: gcols[i % 4].text_input(k, "") for i, k in enumerate(core.GLOBAL_FIELDS)}
        with st.expander("공장 에너지"):
            c = st.columns(5)
            r_in = [c[i].number_input(f"r {SYS} [0~1]", 0.0, 1.0, float(base_vals["r"][i]), 0.05, key=f"r{i}")
                    for i, SYS in enumerate(core.SYSTEMS)]
            o["r"] = r_in
            c = st.columns(5)
            f_in = [c[i].number_input(f"f {SYS} [0~1]", 0.0, 1.0, float(base_vals["f"][i]), 0.05, key=f"f{i}")
                    for i, SYS in enumerate(core.SYSTEMS)]
            o["f"] = f_in
            c = st.columns(3)
            o["q"] = c[0].number_input("실제 양품 생산량비 q", 0.1, 5.0, float(base_vals["q"]), 0.05)
            o["p_add_mode"] = c[1].radio("P_add 집계 방식(하나만)", ["aggregate", "itemized"])
            pa = c[2].text_input("P_add aggregate [pt, 기준 전력 100 대비] (itemized 선택 시 비워야 함)", "2.0")
        evd0 = res.get("evidence", {})
        if evd0.get("status") == core.NUM_OK:
            with st.expander("근거 기반 판정 레버 (근거 FMEA 데이터셋)", expanded=False):
                lev_all = [l for l in evd0["clean"]["levers"] if l["exclusive_group"] != "BASE"]
                lab = {l["lever_id"]: f"{l['lever_id']} · {l['name_ko']} ({l['system']}{', 장기' if l['horizon'] == '장기' else ''})"
                       for l in lev_all}
                o["kb_selected_levers"] = st.multiselect(
                    "판정에 포함할 공정 변경 레버", list(lab), default=[x for x in evd0["selected"] if x in lab],
                    format_func=lab.get, help="기본값은 v10 제안서가 채택한 레버. 같은 중복방지그룹 레버는 곱하지 않습니다.")
                kc1, kc2 = st.columns(2)
                o["kb_combine_retention"] = kc1.slider(
                    "결합 이득 유지율 κ", 0.0, 1.0, float(base_vals.get("kb_combine_retention") or 1.0), 0.05,
                    help="같은 계통에서 서로 다른 그룹 레버를 함께 쓸 때 독립 곱셈 대비 추가 이득이 남는 비율. 1=독립, 0=가장 큰 레버만")
                o["kb_extra_burden_pt"] = kc2.number_input(
                    "추가 미정량 관리 전력 P [pt]", 0.0, 50.0, float(base_vals.get("kb_extra_burden_pt") or 0.0), 0.5,
                    help="아직 정량화되지 않은 관리조치 전력(기준 공장 100 대비). 민감도 확인용")
                eh0 = base_vals.get("kb_electric_heating") or {}
                h1, h2 = st.columns(2)
                dry_e = h1.radio("건조 가열원", ["전기", "가스·스팀"], index=0 if eh0.get("건조", True) else 1, horizontal=True,
                                 help="가스·스팀이면 합산(전기+열) 절감률 대신 설비 전기 변화율로 전력 효과를 계산합니다. "
                                      "복사건조처럼 열을 전기로 바꾸는 기술은 전력이 오히려 늘어납니다.")
                drm_e = h2.radio("드라이룸 제습 재생 열원", ["전기", "가스·스팀"], index=0 if eh0.get("드라이룸", True) else 1,
                                 horizontal=True)
                o["kb_electric_heating"] = {**eh0, "건조": dry_e == "전기", "드라이룸": drm_e == "전기"}
            with st.expander("A/B/C 후보 비교 조건 (공정 부하 연결·현장 확인값)", expanded=False):
                k1, k2, k3 = st.columns(3)
                o["solids_old"] = k1.number_input("기존 고형분 [질량분율]", 0.30, 0.90, float(base_vals.get("solids_old") or 0.60), 0.005,
                                                  format="%.3f", help="예시 60 wt%. C사 측정값으로 바꾸세요.")
                cands0 = base_vals.get("kb_candidates") or []
                dB = next(((c.get("solids_rule") or {}).get("value") for c in cands0 if c.get("solids_rule")), 0.05)
                new_dB = k2.number_input("B안 고형분 상향폭 Δ [질량분율, 기존+Δ]", 0.0, 0.30, float(dB), 0.005, format="%.3f")
                o["kb_candidates"] = [{**c, "solids_rule": {"type": "delta", "value": new_dB}} if c.get("solids_rule") else c
                                      for c in cands0] or None
                ph = base_vals.get("drying_solvent_load_share") or [0.3, 0.5, 0.7]
                phr = k3.slider("용매 비례 부하 비중 φ 범위(보수~낙관)", 0.0, 1.0, (float(ph[0]), float(ph[2])), 0.05,
                                help="건조 계통 변동부하 중 용매 증발·응축·회수에 비례하는 몫. 팬·대기 부하는 용매가 줄어도 줄지 않음")
                o["drying_solvent_load_share"] = [phr[0], (phr[0] + phr[1]) / 2, phr[1]]
                k4, k5, k6 = st.columns(3)
                spd = k4.text_input("실측 건조 속도 상한 [배] (빈칸=미계측)",
                                    "" if base_vals.get("drying_max_speed_ratio_verified") is None else str(base_vals["drying_max_speed_ratio_verified"]))
                slot = k5.text_input("승인된 에이징 슬롯 증가율 [비율] (빈칸=미확인)",
                                     "" if base_vals.get("aging_slot_gain_approved") is None else str(base_vals["aging_slot_gain_approved"]))
                o["kb_extra_occupancy_h"] = k6.number_input("미정량 화성 추가 점유 [h]", 0.0, 10.0,
                                                            float(base_vals.get("kb_extra_occupancy_h") or 0.0), 0.05)
                sp["drying_max_speed_ratio_verified"] = spd
                sp["aging_slot_gain_approved"] = slot
        submitted = st.form_submit_button("계산 실행")
    if submitted:
        try:
            o["p_add_aggregate"] = parse_opt(pa)
            o["baseline_channels"] = parse_opt(bc)
            for k, t in sp.items():
                o[k] = parse_opt(t)
            gl = {k: parse_opt(t) for k, t in g_txt.items()}
            o["drying_b_global"] = gl
            o["aging_zones"] = [{k: (None if pd.isna(v) else (str(v) if k == "name" else float(v)))
                                 for k, v in row.items()} for row in azed.to_dict("records")] or None
            o["drying_b_zones"] = [{k: _cell(k, v) for k, v in row.items()} for row in zed.to_dict("records")]
            ss["custom_overrides"] = o
            ss["_goto"] = "custom"
            ss["report_files"], ss["report_key"] = None, None
            st.rerun()
        except core.InputError as e:
            st.error(f"입력 오류: {e}")
        except ValueError as e:
            st.error(f"숫자 형식 오류: {e}")
    if not res.get("blocked"):
        st.markdown("##### 그림 1 — Formation Boundary")
        st.pyplot(reporting.fig_formation(res))
        st.caption(reporting.formation_caption(res))
        st.markdown("##### 그림 2 — Energy Boundary")
        st.pyplot(reporting.fig_energy(res))
        st.caption(reporting.energy_caption(res))
        st.markdown("##### 비교 조건 (과제 표)")
        cmp_df = pd.DataFrame(res["comparison"]).drop(columns=["group"], errors="ignore")
        ui_v3.table(cmp_df, hide_index=True, width="stretch")
        st.markdown("##### 건조 모드 A / B 결과 (서로 중복 반영하지 않음)")
        a, b = res["drying_a"], res["drying_b"]
        c = st.columns(2)
        c[0].metric("모드 A 절감률", core.fmt_pct(a.get("saving_ratio"), 2) if a["status"] == core.NUM_OK else a["status"],
                    help=a.get("note", a.get("error", "")))
        c[0].caption(f"적용 조건: {core.drying_a_condition(res['inputs']['drying_a'])}. 대표 시나리오의 건조 "
                     f"{core.fmt_pct(res['inputs']['r'][0], 0)}(수동 입력)와 다른 값이며, 공장 모델에는 '{core.KEY_KO[res['drying_r_source']]}' 출처만 반영됩니다.")
        c[1].metric("모드 B 절감률", core.fmt_pct(b.get("saving_ratio"), 2) if b["status"] == core.NUM_OK else b["status"],
                    help=b.get("reason", b.get("error", "")))
        if b["status"] == core.NUM_HOLD:
            st.caption(f"모드 B 미확인 입력 {len(b['missing'])}건 — 위 입력표의 빈칸을 채우면 계산됩니다.")
        elif b["status"] == core.NUM_OK:
            st.caption(f"모드 B Qh 제한 요인: {b['limit_by']} (열원 한계 {b['source_limit_kwth']:.2f} kWth, "
                       f"열원 부족으로 미공급된 HP 요구 {b['unmet_hp_kwth']:.2f} kWth)")
            for w in b["warnings"]:
                st.warning(w)
        ag = res["aging"]
        if ag.get("zone_mode") and ag["status"] == core.NUM_OK:
            st.markdown("##### 에이징 구역별 슬롯·공간 (구역 간 상쇄 없음, 총 14일 유지)")
            ui_v3.table(pd.DataFrame([{"구역": z["name"], "추가 슬롯비": z["additional_slot_ratio"],
                                       "freed_area [m²]": z["freed_area_m2"], "전환 가능 슬롯(조건부)": z["convertible_slots"],
                                       "상태": z["space_status"]} for z in ag["zones"]]), hide_index=True, width="stretch")
            st.caption(f"합계 상태: {ag['space_status']} — {ag['space_note']}")
        st.markdown("##### 다운로드")
        if ss.pop("report_invalidated", False):
            st.info("시나리오·입력·품질 상태가 바뀌어 이전 보고서는 무효화되었습니다. 현재 결과로 다시 생성하세요.")
        if st.button("CSV·PDF 보고서 생성"):
            with tempfile.TemporaryDirectory() as td:
                reporting.export_all(res, td, reporting.make_run_info("streamlit"))
                names = ["result_report.pdf", "evidence_report.pdf", "scenario_comparison.csv", "requirements.csv",
                         "pfmea_summary.csv", "evidence.csv", "kb_lever_judgement.csv", "kb_effect_trace.csv",
                         "kb_cases.csv", "kb_combos.csv", "kb_options.csv", "kb_thresholds.csv", "kb_roadmap.csv",
                         "kb_decision_boundary.csv", "kb_overall.csv", "kb_quality_gates.csv", "kb_candidates.csv",
                         "kb_boundaries.csv", "kb_verification_priority.csv", "kb_heat_sensitivity.csv",
                         "kb_stage_progress.csv", "kb_reverse_models.csv", "results.json", "kb_lever_economics.csv",
                         "kb_rollout.csv", "kb_heat_matches.csv", "evidence_sensitivity.png", "evidence_candidates.png"]
                ss["report_files"] = {n: (Path(td) / n).read_bytes() for n in names if (Path(td) / n).exists()}
                ss["report_key"] = CUR_KEY
        if ss["report_files"] and ss["report_key"] == CUR_KEY:
            st.caption(f"아래 파일은 현재 화면 결과({res['scenario_label']})로 생성되었습니다.")
            mimes = {"pdf": "application/pdf", "csv": "text/csv", "png": "image/png", "json": "application/json"}
            items = list(ss["report_files"].items())
            for i in range(0, len(items), 5):
                for col, (n, data) in zip(st.columns(5), items[i:i + 5]):
                    col.download_button(n, data, file_name=n, mime=mimes[n.rsplit(".", 1)[1]])

# ---------------------------------------------------------------- 상세·부록 (기존 1번 탭)
with tab5:
    if res.get("blocked"):
        st.error(f"입력 오류로 계산이 차단되었습니다: {res['blocked']}")
    else:
        for w in res["warnings"]:
            st.warning(w)
        cd = (res.get("evidence") or {}).get("candidates")
        if cd:
            st.markdown("### A·B·C 후보 설계 비교 (같은 기준선·같은 근거)")
            sel_c = next((c for c in cd["candidates"] if c["id"] == cd["selected"]), None)
            (st.warning if sel_c and not sel_c["n_fail"] else st.error)(f"추천: {cd['status']}")
            pct_ = lambda x: f"{x * 100:.1f}%"
            tbl = {"항목": ["역할", "후보 여부", "고형분", "총 용매량(기존=1)", "원단위 절감 대표", "보수~낙관", "여유(pt)", "연 절감(억원)"]
                   + [a["axis"] for a in cd["candidates"][0]["axes"]] + ["품질 관문(안전)", "종합"]}
            for c in cd["candidates"]:
                mny = c["money_typ"]
                tbl[f"{c['id']}{' ★' if c['id'] == cd['selected'] else ''} {c['name']}"] = (
                    [c["role"], "후보" if c["eligible"] else f"대기({c['why_not']})", pct_(c["solids"]),
                     f"{c['mass_balance']['solvent_vs_base']:.3f}", pct_(c["saving"][1]),
                     f"{pct_(c['saving'][0])}~{pct_(c['saving'][2])}", f"{c['margin_pt']:+.2f}",
                     f"{mny['krw_eok'][0]:.0f}~{mny['krw_eok'][1]:.0f}" if mny else "-"]
                    + [a["state"] for a in c["axes"]] + [f"{c['n_gates']}건 (안전 {c['n_safety_gates']})", c["label"]])
            ui_v3.table(pd.DataFrame(tbl), hide_index=True, width="stretch")
            if sel_c:
                with st.expander(f"{sel_c['id']} 축별 근거 · 실패 경계 · 전환 조건", expanded=False):
                    ui_v3.table(pd.DataFrame([{"축": a["axis"], "상태": a["state"], "내용": a["status"]} for a in sel_c["axes"]]),
                                 hide_index=True, width="stretch")
                    ui_v3.table(pd.DataFrame([{"경계": b["kind"], "의미": b["text"]} for b in cd["boundaries"]]),
                                 hide_index=True, width="stretch")
                    for t_ in cd["switch"]:
                        st.write("· " + t_)
            wf_ = (cd.get("baseline_model") or {}).get("waterfall")
            cp_ = (cd.get("capacity") or {}).get("plant")
            if wf_ or cp_:
                st.info((f"절감 구성: 공정 개조 {wf_['tech_pp']:.2f}%p + 고정부하 희석 {wf_['dilution_pp']:.2f}%p(팀 가정 f). " if wf_ else "")
                        + (f"공장 처리능력 {cp_['plant']:.3f}배 (병목: {cp_['bottleneck']}; "
                           + ", ".join(f"{k} {v:.3f}" for k, v in cp_["caps"].items()) + ")" if cp_ else ""))
            jt_ = (cd.get("joint") or {})
            if jt_.get("stress"):
                with st.expander("동시 불확실성·스트레스 시나리오", expanded=False):
                    st.caption(jt_["region"]["formula"] + " — P 허용치: " + " · ".join(
                        f"α {a:g} → {p:.2f} pt" for a, p in jt_["region"]["p_max"].items()))
                    ui_v3.table(pd.DataFrame([{"ID": r_["id"], "시나리오": r_["scenario"], "원단위 절감": pct_(r_["saving"]),
                                                "여유(pt)": f"{r_['margin_pt']:+.2f}", "판정": r_["verdict"]} for r_ in jt_["stress"]["rows"]]),
                                 hide_index=True, width="stretch")
            nc_ = (cd.get("necessity") or {}).get("necessity")
            if nc_:
                with st.expander(f"레버 필요성 ({nc_['candidate']}에서 하나씩 뺄 때)", expanded=False):
                    ui_v3.table(pd.DataFrame([{"레버": f"{r_['name']}({r_['lever_id']})", "빼면 감소(%p)": round(r_["delta_pp"], 2),
                                                "관문 수 감소": r_["gates_delta"], "분류": r_["class"]} for r_ in nc_["rows"]]),
                                 hide_index=True, width="stretch")
            if cd.get("heat"):
                with st.expander("열원 민감도 (후보별 재계산)", expanded=False):
                    st.caption("후보: " + " · ".join(f"**{c_['id']}** {c_['name']}" for c_ in cd["candidates"])
                               + " ｜ ★ = 그 열원 조건에서 추천되는 후보(모두 미달이면 그중 가장 나은 후보)")
                    ui_v3.table(pd.DataFrame([{"열원 조건": r_["case"], "후보": r_["candidate"] + (" ★" if r_["selected"] else ""),
                                                "원단위 절감 대표": pct_(r_["saving"][1]), "건조 계통": cand_mod.sys_change(r_["r_drying"]),
                                                "드라이룸 계통": cand_mod.sys_change(r_["r_dryroom"]), "전력 축": r_["energy_state"]}
                                               for r_ in cd["heat"]["rows"]]), hide_index=True, width="stretch")
                    st.caption(cd["heat"]["note"])
            if cd.get("stages"):
                with st.expander(f"단계별 누적 효과 ({cd['stages']['candidate']})", expanded=False):
                    ui_v3.table(pd.DataFrame([{"단계": x["stage"], "추가 레버": ", ".join(x["added"]) or "-",
                                                "원단위 절감 대표": pct_(x["saving"][1]),
                                                "보수~낙관": f"{pct_(x['saving'][0])}~{pct_(x['saving'][2])}",
                                                "여유(pt)": f"{x['margin_pt']:+.2f}", "종합": x["label"]} for x in cd["stages"]["stages"]]),
                                 hide_index=True, width="stretch")
                    st.caption(cd["stages"]["note"])
            dz_ = cd.get("design") if isinstance(cd.get("design"), dict) and "error" not in cd.get("design") else None
            if dz_:
                with st.expander("두 목표 신호등 · 금액 카드 · 설계 고정 비교 (v12.2)", expanded=True):
                    ui_v3.table(pd.DataFrame([{"조건": r_["cond"], "전력 -30%": r_["power"], "생산능력 +20%": r_["capacity"], "종합": r_["overall"]}
                                               for r_ in dz_["signal"]["rows"]]), hide_index=True, width="stretch")
                    for c_ in dz_["money"]["cards"]:
                        st.write(f"**{c_['title']}**: 연 {c_['krw_eok'][0]:.0f}~{c_['krw_eok'][1]:.0f}억 원 - {c_['line']}")
                    ui_v3.table(pd.DataFrame([{"설계": r_["label"] + (" ★공식" if r_["official"] else ""), "절감": pct_(r_["saving"][1]),
                                                "여유(pt)": f"{r_['margin_pt']:+.2f}", "α*": f"{r_['alpha_star']:.3f}", "f 전부 0": pct_(r_["f0"]),
                                                "2년차 공간 미확보": pct_(r_["y2_no_slot"])} for r_ in dz_["compare"]["rows"]]),
                                 hide_index=True, width="stretch")
                    st.caption(dz_["compare"]["protocol_basis"])
            rm_ = cd.get("roadmap") if isinstance(cd.get("roadmap"), dict) and "space" in cd.get("roadmap", {}) else None
            if rm_:
                with st.expander("생산능력 +20% 공간 수지 · 연차별 도달도 · 영향평가", expanded=False):
                    st.write(rm_["space"]["sentence"])
                    ui_v3.table(pd.DataFrame([{"": o["no"], "확보 후보": o["name"], "원리": o["how"], "전제 조건": o["depends"],
                                                "시기": o["when"]} for o in rm_["space"]["options"]]), hide_index=True, width="stretch")
                    ui_v3.table(pd.DataFrame([{"단계": r_["stage"], "전력 절감(공간 미확보)": pct_(r_["power_no_slot"]),
                                                "전력 절감(슬롯 확보 시)": pct_(r_["power_if_slot"]), "생산비 q_t": f"{r_['q_no_slot']:.3f}",
                                                "q_t(슬롯 확보 시)": f"{r_['q_if_slot']:.3f}"} for r_ in rm_["reach"]["rows"]]),
                                 hide_index=True, width="stretch")
                    ui_v3.table(pd.DataFrame([{"개선안": r_["name"], "생산능력": r_["capacity"], "전력": r_["power"], "투자": r_["capex"],
                                                "난이도": r_["difficulty"], "수명·검출력": r_["quality"], "안전": r_["safety"], "시기": r_["horizon"]}
                                               for r_ in rm_["impact"]["rows"]]), hide_index=True, width="stretch")
                    st.caption(rm_["impact"]["rule"])
            with st.expander("무엇을 먼저 확인하는가 (검증 우선순위)", expanded=False):
                ui_v3.table(pd.DataFrame([{"순위": t_["priority"], "질문": t_["question"], "판정 영향": t_["impact"],
                                            "시험": t_["how"], "기간·비용(가정)": f"{t_['period']} · {t_['cost']}",
                                            "시험 결과별 판정 (나쁠 때 / 좋을 때)": t_["text"]} for t_ in cd["priority"]["tests"]]),
                             hide_index=True, width="stretch")
                st.caption(cd["priority"]["note"])
            st.caption("상태: 검증 완료 / 가정하 수치 충족 / 미확인 / 미달. 미확인은 통과가 아닙니다. " + cd["note"])
            st.divider()
        st.divider()
        with st.expander("부록 A. 이전 모델 (v10 시나리오 · 레버 조합 엔진) - 참고용 기록, 결론은 위 표", expanded=False):
            st.selectbox("시나리오", list(SCEN), format_func=lambda k: SCEN[k], key="scenario")
            st.caption(CFG["scenarios"][scenario]["description"] + (" — 탭 2에서 입력한 값이 적용됩니다." if scenario == "custom" else ""))
            cols = st.columns(4)
            for c, k in zip(cols, res["kpi"]):
                with c.container(border=True, height=250):
                    st.caption(k["title"])
                    st.subheader(k["value"])
                    st.write(k["sub"])
                    st.caption("근거: " + k["label"])
            st.markdown("##### 관리조치 전·후·보완 요구 비교")
            if res["before_after"]:
                df = pd.DataFrame([{"단계": b["stage"], "화성 처리능력(배)": b["capacity_ratio"], "총전력(pt)": b["E_total"],
                                    "원단위 절감(%)": None if b["saving_ratio"] is None else b["saving_ratio"] * 100,
                                    "격차(pt)": b["gap"], "조건": b["note"]} for b in res["before_after"]])
                ui_v3.table(df, hide_index=True, width="stretch",
                             column_config={"화성 처리능력(배)": st.column_config.NumberColumn(format="%.3f"),
                                            "총전력(pt)": st.column_config.NumberColumn(format="%.2f"),
                                            "원단위 절감(%)": st.column_config.NumberColumn(format="%.2f"),
                                            "격차(pt)": st.column_config.NumberColumn(format="%+.2f")})
            rq = pd.DataFrame([{"항목": x["item"], "현재 입력": x["current"], "요구·허용": x["required"],
                                "단위": x["unit"], "해석": x["note"]} for x in res["requirements"]])
            ui_v3.table(rq, hide_index=True, width="stretch")
            st.info(res["conclusion"])
            st.caption("요구값은 확보된 성능이 아니며, 수치 충족과 품질 상태는 별개로 판정합니다.")

            # ---- 근거 기반 자동 판정 (사람이 정한 r 대신 근거 FMEA 데이터셋만 사용)
            st.divider()
            st.markdown("### 근거 기반 자동 판정 (근거 FMEA 데이터셋)")
            evd = res.get("evidence", {})
            if evd.get("status") != core.NUM_OK:
                st.error(evd.get("error", "근거 판정을 실행하지 못했습니다."))
            else:
                cs = evd["cases"]
                pct = lambda x: f"{x * 100:.1f}%"
                n_sel = sum(1 for l in evd["levers"] if l["selected"])
                n_cov = sum(1 for l in evd["levers"] if l["selected"] and l["judge"] in ("근거 충분", "근거 약함"))
                ov = evd.get("overall")
                if ov:
                    (st.success if ov["all_ok"] else st.error)(f"종합 판정(추천 조합): {ov['label']}")
                    ui_v3.table(pd.DataFrame([{"축": a_["axis"], "현재 선택": f"[{b_['state']}] {b_['status']}",
                                                "추천 조합": f"[{a_['state']}] {a_['status']}"}
                                               for a_, b_ in zip(ov["axes"], evd["overall_selected"]["axes"])]),
                                 hide_index=True, width="stretch")
                cols = st.columns(4)
                for col, (t, v, s) in zip(cols, [
                        ("근거 판정", evd["verdict"], "목표 원단위 30% 절감 기준"),
                        ("원단위 절감 (대표)", pct(cs["typical"]["saving"]),
                         f"보수 {pct(cs['conservative']['saving'])} ~ 낙관 {pct(cs['optimistic']['saving'])}"),
                        ("위 v10 가정 결과", core.fmt_pct(res["plant"].get("saving_ratio"), 2), "사람이 정한 r로 계산 (비교용)"),
                        ("근거 있는 선택 레버", f"{n_cov} / {n_sel}", "계산 가능한 근거가 있는 레버")]):
                    with col.container(border=True, height=190):
                        st.caption(t)
                        st.subheader(v)
                        st.write(s)
                st.info(evd["conclusion"])
                for h in evd["holds"]:
                    st.warning(h)
                pr = evd.get("production_rec") or evd["production"]
                st.markdown(f"**증산 +20% 판정: {pr['verdict']}** — 화성 처리능력 {'≤' if pr['formation_upper_bound'] else ''}"
                            f"{pr['formation_capacity']:.3f}배 · 에이징 {pr['aging_status']}")
                st.caption(pr["note"])
                op = evd["options"]
                st.markdown("##### 개선안 비교표")
                yrs = op["payback_years"]
                fmt_rng = lambda m, k: "-" if not m else f"{m[k][0]:.0f}~{m[k][1]:.0f}"
                ui_v3.table(pd.DataFrame([{
                    "개선안": r["option"], "전력 판정": r["verdict"],
                    "대표 절감(%)": None if r["saving"][1] is None else round(r["saving"][1] * 100, 1),
                    "보수~낙관(%)": "-" if r["saving"][0] is None else f"{r['saving'][0] * 100:.1f}~{r['saving'][2] * 100:.1f}",
                    "연 절감(억원)": fmt_rng(r["money_typ"], "krw_eok"),
                    **{f"허용 투자비 {n}년(억원)": ("-" if not r["money_typ"] else
                                              f"{r['money_typ']['invest_eok'][n][0]:.0f}~{r['money_typ']['invest_eok'][n][1]:.0f}") for n in yrs},
                    "증산": r["production"] or "-", "품질 위험(FMEA)": r["risks"], "최대 변경": r["difficulty"], "근거": r["evidence"]}
                    for r in op["rows"]]), hide_index=True, width="stretch")
                st.caption(op["note"])
                st.markdown("##### 추천이 바뀌는 조건")
                ui_v3.table(pd.DataFrame([{"구분": t["kind"], "계통": t["system"], "조건": t["text"]} for t in evd["thresholds"]]),
                             hide_index=True, width="stretch")
                st.markdown("##### 3년 적용 순서")
                for stg in evd["roadmap"]:
                    with st.expander(f"{stg['year']} — {stg['title']} ({len(stg['levers'])}개 레버)"):
                        for lv in stg["levers"]:
                            st.write(f"- **{lv['lever_id']}** {lv['name']} · {lv['change_type']}" + ("" if lv["has_evidence"] else " · [근거 없음]"))
                            for g in lv["gates"]:
                                st.caption(f"  품질 관문: {g}")
                        for a_ in stg["actions"]:
                            st.write(f"· {a_}")
                        st.caption(f"다음 단계 진입 조건: {stg['exit']}")
                import evidence_report
                st.pyplot(evidence_report.fig_systems(res))
                st.caption("막대 = 근거 범위(보수~낙관), ● = 근거 대표값, × = v10 가정, ◇ = 그 계통만으로 목표를 맞출 때 필요한 절감률")
                ui_v3.table(pd.DataFrame([{"계통": r["system"], "v10 가정 r": r["v10_r"] * 100,
                                            "근거 하한(%)": r["lo"] * 100, "근거 대표(%)": r["typ"] * 100,
                                            "근거 상한(%)": r["hi"] * 100, "판정": r["status"]} for r in evd["v10_check"]]),
                             hide_index=True, width="stretch",
                             column_config={k: st.column_config.NumberColumn(format="%.1f")
                                            for k in ("v10 가정 r", "근거 하한(%)", "근거 대표(%)", "근거 상한(%)")})
                st.pyplot(evidence_report.fig_cases(res))
                sv = evd.get("sensitivity")
                if sv:
                    st.markdown("##### 결합 효과·관리부담 경계도 (추천 조합)")
                    st.pyplot(evidence_report.fig_sensitivity(res))
                    fk = lambda x: "-" if x is None else f"{x * 100:.0f}%"
                    st.caption(f"대표 기준 최소 κ {fk(sv['kappa_min_typ'])} · 보수 기준 최소 κ {fk(sv['kappa_min_cons'])} · "
                               f"허용 추가 부담(κ=1) {sv['p_max'][1.0]:.2f} pt. " + sv["note"] if sv["p_max"][1.0] is not None else sv["note"])
                q = evd.get("quality")
                if q and q["rows"]:
                    with st.expander(f"품질 관문 확인 상태 ({' · '.join(f'{k} {v}' for k, v in q['counts'].items() if v)})"):
                        ui_v3.table(pd.DataFrame([{"FMEA": r["fmea_id"], "레버": r["lever_id"], "고장모드": r["failure_mode"],
                                                    "품질 관문": r["gate"], "상태": r["status"], "바뀐 조건": "; ".join(r["changed"])}
                                                   for r in q["rows"]]), hide_index=True, width="stretch")
                cb = evd["combos"]
                st.markdown(f"**근거 있는 레버 추가 조합** — 3년 내 후보 {len(cb['candidates'])}개, 조합 {cb['n_evaluated']}개를 결정적으로 열거")
                if cb["results"]:
                    ui_v3.table(pd.DataFrame([{"추가 레버": " + ".join(x["names"]), "판정": x["verdict"],
                                                "보수(%)": x["conservative"] * 100, "대표(%)": x["typical"] * 100,
                                                "낙관(%)": x["optimistic"] * 100, "대표 격차(pt)": x["gap_typical"]}
                                               for x in cb["results"]]), hide_index=True, width="stretch",
                                 column_config={k: st.column_config.NumberColumn(format="%.1f")
                                                for k in ("보수(%)", "대표(%)", "낙관(%)", "대표 격차(pt)")})
                if cb["long_term_excluded"]:
                    st.caption("장기 레버(3년 내 적용 어려움)는 탐색에서 제외: " + ", ".join(cb["long_term_excluded"]))
                st.caption("탭 2 '근거 기반 판정 레버'에서 레버를 바꾸면 이 판정이 다시 계산됩니다. "
                           "근거 범위는 확보된 성능이 아니며, 확률·점수를 만들지 않습니다.")
