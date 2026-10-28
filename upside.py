"""판정에 넣지 않는 추가 여유 (what-if) - 근거 없는 계통·레버, 섀도 모드 에이징.

여기 숫자는 '검증 통과 시 추가 이득'이며 기본 결론(추천·판정)에는 반영하지 않는다.
"""
from __future__ import annotations

import candidates as C
import kb_schema as S

LABEL = "검증 통과 시 추가 이득 - 기본 결론 미반영"


def per_point(values):
    """계통별 '1%p 절감당 추가 여유(pt)' = B_j × 0.01."""
    B = C._B(values)
    return [{"system": s, "B": B[j], "pt_per_pp": B[j] * 0.01, "pp_per_pp": B[j] * 0.01 / (100 * values["q"]) * 100}
            for j, s in enumerate(S.SYSTEMS)]


def whatif(values, nec):
    pp = {r["system"]: r for r in per_point(values)}
    rows = [{"item": "기타 유틸리티 10% 절감(근거 미확보)", "pt": pp["기타"]["pt_per_pp"] * 10,
             "how": "압축공기·공조·조명 실측 후 ETC-UTIL 근거 등록 시 자동 편입"},
            {"item": "에이징 공조 10% 절감(근거 미확보)", "pt": pp["에이징"]["pt_per_pp"] * 10, "how": "에이징실 공조 계측"}]
    for r in (nec or {}).get("rows", []):
        if r["class"].startswith("계산 기여 0"):
            lv = r["system"]
            rows.append({"item": f"{r['name']}({r['lever_id']}) - 계통 1%p 실측 시", "pt": pp[lv]["pt_per_pp"],
                         "how": "1년차 파일럿 실측으로 등급 B 근거 등록"})
    for r in rows:
        r["pp"] = r["pt"] / (100 * values["q"]) * 100
    return {"rows": rows, "per_point": list(pp.values()), "label": LABEL}


def shadow_mode(values, cand=None, days_list=(14, 13, 12.315, 10, 7)):
    """에이징 섀도 모드: 출하는 14일 판정 유지, 조기 측정을 병행해 단축 근거(결함 양성 표본)를 무위험으로 축적."""
    sm = values.get("shadow_mode") or {}
    target = sm.get("miss_upper_target", 0.01)
    conf = sm.get("confidence", 0.95)
    n = C.n_for_miss_rate(target, conf)
    q, cu, pu = values["q"], values["current_utilization"], values["planned_utilization"]
    d0 = values.get("aging_days") or 14
    fh = values["formation_h"]
    rate = None
    need_inputs = []
    nat = sm.get("natural_defects_per_week")
    inj = sm.get("injected_defects_per_week")
    dr = sm.get("defect_rate")
    dr_lo, dr_hi = (dr if isinstance(dr, (list, tuple)) else (dr, dr)) if dr is not None else (None, None)
    if nat is None and sm.get("cells_per_day") is not None and dr is not None:
        nat = sm["cells_per_day"] * 7 * dr_hi
    example = None
    ex_cells = sm.get("cells_per_day") or sm.get("example_cells_per_day")
    if dr is not None and ex_cells:
        wk = lambda r: n / (ex_cells * 7 * r)
        example = {"cells_per_day": ex_cells, "is_example": sm.get("cells_per_day") is None,
                   "defect_rate": [dr_lo, dr_hi], "weeks_natural": [wk(dr_hi), wk(dr_lo)], "source": sm.get("defect_rate_source")}
    if nat is None:
        need_inputs.append("자연 결함 양성 수/주 (= 일 처리 셀 × 7 × 자가방전·미세단락 불량률)")
    if inj is None:
        need_inputs.append("인위 내부단락 시험 셀 수/주")
    if nat is not None or inj is not None:
        rate = (nat or 0) + (inj or 0)
    weeks = n / rate if rate else None
    rows = []
    for d in days_list:
        need = q * cu / pu * d / d0 - 1
        rows.append({"days": d, "slot_need": need, "lead_time_h": fh + d * 24, "no_slot_ok": need <= 1e-9})
    base_lt = values["baseline_formation_h"] + d0 * 24
    if example:
        need_inputs = [x for x in need_inputs if not x.startswith("자연")]
    period = None
    rng = sm.get("cells_per_day_range")
    if rng:
        lo_c, hi_c = min(rng), max(rng)
        prow = []
        if dr is not None:
            prow.append({"label": f"필드 내부단락 {dr_lo * 1e6:g}~{dr_hi * 1e6:g} ppm (R25)", "ppm": [dr_lo * 1e6, dr_hi * 1e6],
                         "days": [n / (hi_c * dr_hi), n / (lo_c * dr_lo)], "kind": "자연 결함만"})
        for ppm in sm.get("scenario_ppm") or []:
            p_ = ppm * 1e-6
            prow.append({"label": f"예시 {ppm:g} ppm", "ppm": [ppm, ppm], "days": [n / (hi_c * p_), n / (lo_c * p_)], "kind": "예시(미확인)"})
        period = {"cells_per_day": [lo_c, hi_c], "source": sm.get("cells_per_day_source"), "rows": prow,
                  "formula": f"T(일) = {n} / (하루 셀 수 × 불량률)",
                  "note": "에이징 OCV로 걸리는 불량률 p는 미확인. 공정 단계 평균 수율 손실(25단계 평균값)은 에이징 OCV 검출 불량률이 아니라 표에 넣지 않는다. "
                          "자연 결함만으로는 수백 일이 걸려 인위 내부단락 셀(R25 유발 장치)을 병행한다."}
    return {"n_required": n, "miss_upper_at_n": C.miss_rate_upper(n, conf), "target": target, "weeks": weeks,
            "natural_example": example, "period_table": period,
            "need_inputs": need_inputs, "rows": rows, "base_lead_time_h": base_lt,
            "stages": [{"stage": "0 병행 관찰", "what": "14일 출하 판정 유지 + 같은 셀 조기 측정(누설전류·전압 이완 분리), 인위 내부단락 셀 병행",
                        "gate": f"결함 유형·로트별 표본 구성, 미검출·과검출 기록 (통계 예시: 결함 양성 {n}개 미검출 0건 → 상한 {target * 100:g}%)"},
                       {"stage": "1 승인 준비", "what": "단축 범위(셀 유형·기간)를 먼저 정의",
                        "gate": "품질팀 허용 위험·비열등 기준, 대표 결함 검출력, 재검·격리 능력"},
                       {"stage": "2 제한 로트", "what": "승인된 로트만 단축 적용, 14일 대조군 유지",
                        "gate": "대조군·로트별 품질·필드 추적, 중단 기준"},
                       {"stage": "3 확대", "what": "검증 조건에만 적용",
                        "gate": "조건 변경 시 재검증. 통과 시 10일이면 리드타임 " + f"{values['baseline_formation_h'] + d0 * 24:.0f} → {fh + 10 * 24:.0f} h, 추가 슬롯 0"}],
            "n_note": f"n = {n}·미검출 0건은 이항 가정의 통계 예시이며 단독 승인 요건이 아니다(결함 유형 대표성·과검출·필드 추적과 함께 판단).",
            "label": LABEL,
            "note": "필요 표본 n은 정상 셀 수가 아니라 실제 결함 양성 셀 수. 축적 기간은 결함 발생률 입력이 있어야 계산된다."}


def analyze(values, run, nec=None):
    return {"whatif": whatif(values, nec), "shadow": shadow_mode(values)}
