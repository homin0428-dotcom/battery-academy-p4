"""v12.1 PPT용 출력 - 결론 숫자는 바꾸지 않고, 이미 계산된 값을 PPT 표 형태로 묶는다 (조원 v13.1 제안 반영).

  space_plan()      생산능력 +20%의 남은 병목(에이징 공간) 수지: 필요 슬롯 · 면적 상한 · 확보 후보 ①~④와 의존 조건
  reach()           연차별 두 목표 도달도 (전력 원단위 절감 · 생산비 q_t, 슬롯 확보 시/미확보 시)
  horizon_table()   개선안별 근거 성격 → 단기/중기/장기 분류 + 검증 방법 · 통과 기준
  impact_matrix()   상·중·하 영향평가 (전력은 규칙: 상 ≥ 5%p, 중 1~5%p, 하 < 1%p · 나머지 칸은 팀 판단 표기)
  kpi_card()        1쪽 처리능력 KPI 카드 문구
"""
from __future__ import annotations

POWER_RULE = (5.0, 1.0)          # %p: 상 ≥ 5, 중 1~5, 하 < 1

# 근거 성격·시기·검증 (v13.1 4장). delta_pp·처리능력은 프로그램 출력으로 채운다.
HORIZON = [
    {"lever_id": "DRY-HSC", "name": "고형분 60→65%", "nature": "질량수지(물리식) + 문헌 권장 64~66%(R28)",
     "horizon": "단기", "when": "1년차 상반기 - 배합 변경",
     "method": "배합 파일럿: 점도·겔화·슬롯다이 토출 안정, 잔류 NMP·접착·크랙",
     "pass": "결함률 기준 배합과 동등 · 고형분 64.29% 이상 유지(미만이면 건조 처리능력 미성립)"},
    {"lever_id": "FOR-FAST", "name": "화성 20→16 h", "nature": "시간: Weng 2021 파일럿 프로토콜(R3) / 전력: Degen 모델(R1)",
     "horizon": "단기", "when": "1년차 파일럿 검증 후 라인 적용 ('즉시' 아님)",
     "method": "프로토콜별 초기효율·용량·가스·저항 비교 + 화성 데이터 수명 예측, 장기 사이클 병행",
     "pass": "수명·초기효율 비열등 · 추가 점유 40분 예산 이내"},
    {"lever_id": "DRY-RAD", "name": "복사건조(NIR + 열풍 하이브리드)", "nature": "Degen 2023 Table 1 2040년·100% 대체 모델값(C등급)",
     "horizon": "중기", "when": "1년차 실측 → 2년차 오븐 일부 구간 부스터",
     "method": "파일럿 구간 실측 kWh/m², 바인더 이동, NMP 농도·표면 온도 인터록",
     "pass": "문헌 효과 재현율 α* 이상(관리 전력 증가 시 α–P 영역 안) · 점화원 관문 통과"},
    {"lever_id": "DRM-LOCAL", "name": "드라이룸 부분 국소화(주액~밀봉)", "nature": "Degen 2040 모델 + Lechner 2025 비용 모델(R8)",
     "horizon": "중기(부분) / 장기(전면)", "when": "2년차 부분 미니환경",
     "method": "노출 구역 이슬점 지도, 최악 출입 복구 시간, 전환 로트 품질 비교",
     "pass": "전 구간 이슬점 -40°C 이하 기록 · 전환 로트 품질 동등"},
    {"lever_id": "AGE-RACK", "name": "에이징 랙·버퍼 전환", "nature": "공간 계산(리틀의 법칙) + FM Global DS 7-112 방재 기준",
     "horizon": "중기", "when": "1~2년차 버퍼 전환 · 2년차 랙 고단화",
     "method": "현장 면적 실측, 인랙 스프링클러·하중 검토",
     "pass": "방재 승인된 순 슬롯 +13.68% 이상"},
    {"lever_id": "SHADOW", "name": "섀도 모드 조기 선별", "nature": "검출력 계산(이항, 미검출 0건)",
     "horizon": "중기(upside)", "when": "1년차부터 병행",
     "method": "14일 판정 유지 + 조기 측정 병행, 인위 내부단락 셀로 결함 표본 확보",
     "pass": "결함 양성 299개에서 미검출 0건 (판정 미반영)"},
]

# 영향평가 - 전력 칸은 규칙으로 계산, 나머지는 팀 판단(v13.1 5장). 판정에 쓰지 않는다.
IMPACT = {
    "FOR-FAST": {"capacity": "상 (화성 1.25배)", "capex": "하 - 프로토콜 변경", "difficulty": "중", "quality": "상 (리튬 석출·SEI)", "safety": "중"},
    "DRY-HSC": {"capacity": "상 (건조 1.24배)", "capex": "하 - 배합 변경", "difficulty": "중 (점도·겔화)", "quality": "중 (접착·크랙)", "safety": "하"},
    "DRY-RAD": {"capacity": "중", "capex": "중 - NIR은 열풍 대비 투자 낮음(정성)", "difficulty": "상", "quality": "중 (바인더 이동)", "safety": "중 (점화원)"},
    "DRM-LOCAL": {"capacity": "하", "capex": "중~상 - 부분 미니환경 셀 원가 +1.9% vs 전면 +8.6% (R8 Sc4·Sc5)",
                  "difficulty": "상 (전환기 이슬점)", "quality": "중 (수분)", "safety": "중"},
    "AGE-RACK": {"capacity": "상 (1.056→1.2)", "capex": "중 - 설비 개조", "difficulty": "중 (방재 승인)", "quality": "하 (14일 유지)", "safety": "상 (화재 하중)"},
    "SHADOW": {"capacity": "중 (통과 시)", "capex": "하 - 측정 장비", "difficulty": "중", "quality": "하 (병행이라 위험 0)", "safety": "하"},
    "NEWLINE": {"capacity": "-", "capex": "상 - 신규 라인", "difficulty": "상", "quality": "미확인", "safety": "미확인"},
}
NEWLINE = [
    {"tech": "건식 전극(용매·건조 제거)", "change": "NMP 건조·회수 계통 자체가 사라짐 → 건조 35% 계통의 구조 변화", "kb": "DRY-DRYCOAT: EF-009(Degen 2040 모델), EF-010",
     "cond": "신규 라인. 기존 슬롯다이·오븐과 호환 안 됨"},
    {"tech": "전면 미니환경 조립 라인", "change": "드라이룸 체적을 설비 내부로 축소", "kb": "DRM-LOCAL 확대 국소화 시나리오(R8 Sc5)",
     "cond": "신규 라인 설계 단계에서 반영해야 효과 최대"},
    {"tech": "회생형 충방전기 전면 도입", "change": "방전 에너지 재사용", "kb": "FOR-REGEN: 장비 효율만 있음(계산 0)", "cond": "설비 교체 주기에 맞춤. 동시성 실측 후 편입"},
    {"tech": "화성 데이터 기반 조기 판정", "change": "화성 곡선으로 수명·자가방전 조기 예측 → 에이징 단축 근거", "kb": "FOR-DATA, Weng 2021, Zheng 2026(R29, 서지만)",
     "cond": "섀도 모드와 결합해 데이터 축적"},
]
ORDER = ["① 고형분 65% 배합 파일럿", "② 화성 16 h 파일럿(수명·가스)", "③ 둘 다 통과 시 라인 적용 + 대기 버퍼 전환",
         "④ 1년차 실측으로 NIR 부스터·국소화 용량 결정", "⑤ 2년차 설비 개조 + 랙 방재 승인", "⑥ 섀도 모드는 1년차부터 병행"]


def power_grade(pp):
    hi, mid = POWER_RULE
    return "상" if pp >= hi else "중" if pp >= mid else "하"


def _sel(run):
    return next((c for c in run["candidates"] if c["id"] == run["selected"]), None)


def space_plan(values, cand, cap):
    """에이징 공간 수지. 필요 슬롯은 계산상 요구량이지 확보된 공간이 아니다."""
    ag = next(a for a in cand["axes"] if a["axis"].startswith("에이징"))
    need = ag["required_slot_gain"]
    share = values.get("formation_aging_area_share_max") or 0.25
    q, fh0, fh = values["q"], values["baseline_formation_h"], values["formation_h"]
    occ = cand["cases"]["typical"]["occupancy_h"]
    wip_for = q * (fh + occ) / fh0                     # 리틀의 법칙: 화성 동시 재공(현재 = 1)
    caps = cap["caps"]
    return {
        "slot_need": need, "formula": f"{q:g} × {values['current_utilization']:g} / {values['planned_utilization']:g} - 1",
        "area_share_max": share, "area_upper": share * need,
        "area_note": f"출제서 '화성·에이징이 공장 면적 최대 {share * 100:g}%'(ORNL, R2) × {need * 100:.2f}% → 공장 면적 최대 약 {share * need * 100:.1f}% "
                     "(화성 구역까지 전부 에이징으로 본 상한 - 실제 필요는 더 작다)",
        "formation_wip": wip_for, "formation_spare": 1 - wip_for,
        "caps": caps, "bottleneck": cap["bottleneck"],
        "options": [
            {"no": "①", "name": "화성 전 대기 버퍼 전환", "how": f"화성 처리능력 {caps['화성']:.3f}배 > {q:g}배면 대기열이 사라져 그 면적을 에이징 랙으로",
             "depends": "화성 16 h 파일럿 통과", "when": "1~2년차", "basis": "출제서(충방전기 부족 → 조립 완료 셀 대기) · 버퍼 면적 현장 확인"},
            {"no": "②", "name": "화성 랙 감소분", "how": f"{q:g}배 생산에서도 {fh:g} h면 동시 재공 = {q:g} × {fh + occ:g} / {fh0:g} = {wip_for:.2f}배 → 화성 구역 {(1 - wip_for) * 100:.0f}% 여유",
             "depends": "화성 16 h 파일럿 통과", "when": "1~2년차", "basis": "리틀의 법칙 계산값(채널 수 기준)"},
            {"no": "③", "name": "랙 고단화·자동창고", "how": "같은 바닥 면적에서 단수를 늘림", "depends": "방재 승인", "when": "2년차",
             "basis": "FM Global DS 7-112: 인랙 스프링클러·차단판 반영 후 순 슬롯만 인정"},
            {"no": "④", "name": "섀도 모드 통과 후 기간 단축", "how": "평균 점유 12.315일 이하면 추가 슬롯 0", "depends": "결함 표본 확보(n ≥ 299)",
             "when": "2~3년차", "basis": "검출력 관문 통과 전 미적용 - 기본 결론에 넣지 않음"},
        ],
        "fallback": "화성 파일럿이 실패하면 ①·②가 함께 사라진다 → ③ 확대 또는 화성 채널 증설(공간 소요)",
        "ledger": [
            {"col": "필요 슬롯", "value": f"+{need * 100:.2f}%", "how": "계산값 (q × 현재 사용률 / 계획 상한 - 1)", "status": "계산됨"},
            {"col": "후보 슬롯", "value": "(현장 실측)", "how": "① 대기 버퍼 전환 · ② 화성 랙 감소분 · ③ 고단화 - 같은 면적을 두 후보에 중복 집계하지 않음",
             "status": "빈칸"},
            {"col": "제외 슬롯", "value": "(현장 실측)", "how": "통로·불량 격리·소방 간격·바닥 하중으로 못 쓰는 슬롯", "status": "빈칸"},
            {"col": "승인 슬롯", "value": (f"+{values['aging_slot_gain_approved'] * 100:.1f}%" if values.get("aging_slot_gain_approved") is not None
                                          else "(방재 승인)"),
             "how": "후보 - 제외 중 방재 승인(FM Global DS 7-112)된 순 슬롯. 이 값 ≥ 필요 슬롯이어야 1.2배", "status":
                 "입력됨" if values.get("aging_slot_gain_approved") is not None else "빈칸 = 미확인"}],
        "ledger_note": (f"화성 랙 {(1 - wip_for) * 100:.0f}% 여유는 검사 추가 점유 40분이면 사라진다(1.2 × {fh + 40 / 60:.2f} / {fh0:g} = "
                        f"{q * (fh + 40 / 60) / fh0:.2f}). 평균 처리능력이 1.2배를 넘어도 대기열 소멸은 보장되지 않는다(변동·고장). "
                        "'확보 계획이 있다'가 아니라 '무엇을 재면 확보 여부가 정해지는지 안다'를 보여 주는 장부."),
        "sentence": (f"생산능력 +20%는 건조 {caps['건조']:.2f}배·화성 {caps['화성']:.2f}배로 계산상 성립하고(화성은 16 h 파일럿 통과 조건), "
                     f"남은 병목은 에이징 보관 공간 +{need * 100:.2f}%(공장 면적 최대 약 {share * need * 100:.1f}%) 하나다. "
                     "이 공간은 현장 실측과 방재 승인 후 확보되는 조건부 값이다."),
        "note": "필요 슬롯은 계산상 요구량(현재 사용률 90%·계획 상한 95%는 팀 가정). '확보 완료', '+20% 달성'이라고 쓰지 않는다.",
    }


def reach(values, stages):
    """연차별 두 목표 도달도. 전력은 그 시점 생산비 q_t 기준 절감, 생산은 q_t / 목표 q."""
    q = values["q"]
    target = 1 - values["target_intensity_ratio"]
    rows = []
    for s in stages["stages"]:
        rows.append({"stage": s["stage"], "power_no_slot": s["at_q_t"]["saving"], "power_if_slot": s["at_q_if_slots"]["saving"],
                     "q_no_slot": s["q_t"], "q_if_slot": s["q_t_if_slots"],
                     "cap_reach_no_slot": (s["q_t"] - 1) / (q - 1), "cap_reach_if_slot": (s["q_t_if_slots"] - 1) / (q - 1),
                     "power_ok_no_slot": s["at_q_t"]["saving"] >= target - 1e-12, "power_ok_if_slot": s["at_q_if_slots"]["saving"] >= target - 1e-12})
    return {"target_power": target, "target_q": q, "rows": rows,
            "note": "'슬롯 확보 시'는 에이징 승인 슬롯이 필요량만큼 확보된 경우(조건부). 1년차는 공간이 없어 생산 "
                    f"{rows[0]['q_no_slot']:.3f}배·원단위 {rows[0]['power_no_slot'] * 100:.2f}%." if rows else ""}


def horizon_table(nec, alpha_star=None):
    d = {r["lever_id"]: r for r in (nec or {}).get("rows", [])}
    out = []
    for h in HORIZON:
        r = d.get(h["lever_id"])
        pp = r["delta_pp"] if r else None
        row = {**h, "delta_pp": pp, "power_grade": power_grade(pp) if pp is not None and pp > 0 else "-"}
        if alpha_star is not None:
            row["pass"] = row["pass"].replace("α* 이상(", f"{alpha_star * 100:.0f}% 이상(α*, ")
        out.append(row)
    return {"rows": out, "newline": NEWLINE, "order": ORDER,
            "note": "전력 목표를 좌우하는 두 레버(복사건조·국소화)는 Degen 2040 모델값이라 중기. 화성 16 h는 단기지만 파일럿 후 적용."}


def impact_matrix(nec, econ, impact=None):
    impact = impact or IMPACT
    d = {r["lever_id"]: r for r in (nec or {}).get("rows", [])}
    be = {r["lever_id"]: r for r in ((econ or {}).get("levers") or {}).get("rows", [])}
    out = []
    for h in HORIZON + [{"lever_id": "NEWLINE", "name": "건식 전극 등 신규라인", "horizon": "장기"}]:
        lid = h["lever_id"]
        r = d.get(lid)
        pp = r["delta_pp"] if r else None
        if lid == "NEWLINE":
            pw = "상 (정성)"
        elif pp is None or pp <= 0:
            pw = "-"
        else:
            pw = f"{power_grade(pp)} ({pp:.2f}%p)"
        b3 = (be.get(lid) or {}).get("breakeven_eok", {}).get(3)
        capex = impact[lid]["capex"] + (f" · 3년 손익분기 {b3[0]:.0f}~{b3[1]:.0f}억" if b3 and b3[1] > 0 else "")
        out.append({"lever_id": lid, "name": h["name"], "power": pw, "horizon": h["horizon"], **impact[lid], "capex": capex})
    return {"rows": out, "rule": "전력: 상 ≥ 5%p, 중 1~5%p, 하 < 1%p (한계 기여 = 그 레버만 뺄 때 줄어드는 절감). 나머지 칸은 팀 판단(판정 미반영).",
            "note": "3년 손익분기 투자비 = 레버별 연 전력비 절감 × 3 (181.9원/kWh, 50~65 kWh/kWh셀). 견적이 아니라 상한. "
                    "Lechner 수치는 15 GWh 원통형 신설·독일 단가라 C사 금액으로 쓰지 않는다."}


def kpi_card(cap, space):
    c = cap["caps"]
    return {"title": f"공장 처리능력 {cap['plant']:.3f}배 (병목 {cap['bottleneck']}) · 슬롯 확보 시 1.2배",
            "lines": [f"건조 {c['건조']:.3f} · 화성 {c['화성']:.3f} · 에이징 {c['에이징']:.3f}",
                      f"남은 병목: 에이징 승인 슬롯 +{space['slot_need'] * 100:.2f}% (공장 면적 최대 약 {space['area_upper'] * 100:.1f}%) - 실측·방재 승인 후 확보"]}


def dept_answers(wf, nec):
    """4개 부서 요구에 대한 답. 개조 기여 비중은 워터폴에서 계산."""
    tech = {st["system"]: st["pt"] for st in (wf or {}).get("steps", []) if st["kind"] == "개조"}
    tot = sum(tech.values()) or 1
    share = (tech.get("건조", 0) + tech.get("드라이룸", 0)) / tot
    gates = ((nec or {}).get("full") or {})
    g, gs = gates.get("n_gates"), gates.get("n_safety_gates")
    return {"share_dry": share, "rows": [
        {"dept": "생산팀", "ask": "화성·에이징 시간 단축, 출하 당기기",
         "answer": "화성 20→16 h(1년차 파일럿 후), 대기 버퍼 해소로 투입 대기 감소, 에이징은 섀도 모드로 14일 판정 유지하며 근거 축적 후 단축",
         "where": "처리능력·섀도 모드"},
        {"dept": "유틸리티팀", "ask": "건조·드라이룸 우선",
         "answer": f"맞다 - 화성·에이징 전력을 0으로 해도 목표 미달(역산), 건조 + 드라이룸이 개조 기여의 {share * 100:.0f}%",
         "where": "역산 세 모델·워터폴"},
        {"dept": "품질팀", "ask": "수명·안전 무영향 근거",
         "answer": f"관문 {g}건(안전 {gs}) 통과 전 다음 단계 금지, 검출력 n ≥ 299, 에이징 14일 유지, 화성 16 h는 수명 비교 후 적용",
         "where": "관문·검출력"},
        {"dept": "재무팀", "ask": "대규모 교체보다 빠른 회수",
         "answer": "단기안은 배합·프로토콜 변경 위주, 설비 개조는 1년차 실측 후 용량 결정, 부분 국소화 우선(전면 대비 셀 원가 증가 작음, R8)",
         "where": "경제성·간트"}],
        "note": f"개조 기여 {share * 100:.0f}% = (건조 {tech.get('건조', 0):.2f} + 드라이룸 {tech.get('드라이룸', 0):.2f}) / 개조 합 {tot:.2f} pt."}


def analyze(values, run, cap_mod, nec, econ, wf=None, alpha_star=None):
    sel = _sel(run)
    if sel is None or not cap_mod or "plant" not in cap_mod:
        return None
    sp = space_plan(values, sel, cap_mod["plant"])
    return {"space": sp, "reach": reach(values, cap_mod["stages"]), "horizon": horizon_table(nec, alpha_star),
            "impact": impact_matrix(nec, econ), "kpi": kpi_card(cap_mod["plant"], sp), "departments": dept_answers(wf, nec)}
