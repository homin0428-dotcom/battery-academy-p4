"""A/B/C 후보 설계 비교 - 공정 부하 연결 · 동일 기준 비교 · 실패 경계 · 검증 우선순위.

최종 개선 명세(2026-10-26)의 네 기능:
  ① 공정 부하 연결   고형분·속도·부하 분배·열원 → 용매량·잔여 건조 전력·건조 처리능력
  ② 동일 조건 비교   A/B/C를 같은 기준선(증산 무개선 ΣB)·같은 단가·같은 열원으로 계산
  ③ 실패 경계        효과 감소·관리 전력·추가 점유·슬롯·고형분·부하 비중이 어디서 판정을 바꾸는지
  ④ 검증 우선순위    불확실한 입력 양끝에서 다시 계산해 추천·판정을 바꾸는 시험부터 제시

판정 상태는 네 가지로만 표시한다: 검증 완료 / 가정하 수치 충족 / 미확인 / 미달.
'미확인'은 통과가 아니다. 확률·기대정보가치·최적화는 계산하지 않는다(결정적 재계산만).
"""
from __future__ import annotations

import copy
import math

import evidence_engine as ee
import kb_schema as S

ST_DONE, ST_OK, ST_UNK, ST_FAIL = "검증 완료", "가정하 수치 충족", "미확인", "미달"
STATES = (ST_DONE, ST_OK, ST_UNK, ST_FAIL)
CASES = ("conservative", "typical", "optimistic")
DI = ee.SYS_IDX["건조"]
TOL = 1e-12
DEFAULT_SOLIDS_OLD = 0.60


def solids_old(values):
    """기존 고형분. None이면 기본값(예시 60 wt%), 0 이하·1 이상은 입력 오류 (0을 조용히 기본값으로 바꾸지 않는다)."""
    import core
    v = values.get("solids_old")
    if v is None:
        return DEFAULT_SOLIDS_OLD
    v = core._need(v, "solids_old")
    if not 0 < v < 1:
        raise core.InputError(f"solids_old는 0~1 사이 질량분율이어야 한다({v})")
    return v


def phi_range(values):
    import core
    phi = values.get("drying_solvent_load_share")
    if phi is None:
        return [0.3, 0.5, 0.7]
    if not isinstance(phi, (list, tuple)) or len(phi) != 3:
        raise core.InputError("drying_solvent_load_share는 [보수, 대표, 낙관] 3개 값")
    phi = [core._need(x, "drying_solvent_load_share") for x in phi]
    if any(not 0 <= x <= 1 for x in phi):
        raise core.InputError("drying_solvent_load_share는 0~1")
    return phi


def candidate_solids(spec, values, levers):
    """후보 고형분. 질량수지 모드(DRY-HSC 포함)일 때만 기존과 달라진다.

    우선순위: solids_override(민감도용) → solids(직접 지정) → solids_rule {type: delta, value: Δ} → s0 + 0.05.
    delta 규칙이면 기존 고형분 s0를 바꿔도 '상향 폭'의 의미가 유지된다.
    """
    import core
    s0 = solids_old(values)
    if "DRY-HSC" not in levers:
        return s0
    if spec.get("solids_override") is not None:
        s1 = spec["solids_override"]
    elif spec.get("solids") is not None:
        s1 = spec["solids"]
    else:
        rule = spec.get("solids_rule") or {"type": "delta", "value": 0.05}
        if rule.get("type") != "delta":
            raise core.InputError(f"후보 {spec.get('id')}: 지원하지 않는 solids_rule {rule}")
        s1 = s0 + float(rule.get("value", 0.05))
    s1 = core._need(s1, "candidate solids")
    if not 0 < s1 < 1:
        raise core.InputError(f"후보 {spec.get('id')} 고형분 {s1}가 0~1 밖")
    return s1


def find_verification(values, cand_id, metric, cond):
    """후보별 현장 검증 기록 조회.

    values["kb_verifications"] = [{candidate_id: 'B1'|'*', metric, value, conditions: {...}, evidence, date}]
    반환 (record | None, 사유). 후보가 다르면 무시, 조건이 하나라도 다르면 None + '재검증 필요'.
    """
    recs = [r for r in (values.get("kb_verifications") or []) if r.get("metric") == metric
            and r.get("candidate_id") in (cand_id, "*")]
    recs.sort(key=lambda r: r.get("candidate_id") == "*")          # 후보 지정 기록 우선
    stale = []
    for r in recs:
        rc = r.get("conditions") or {}
        diff = [f"{k} {v}→{cond.get(k)}" for k, v in rc.items() if not ee._same(v, cond.get(k))]
        # 조건이 비었거나 빠진 기록은 '검증 완료'로 인정하지 않는다 (어떤 조건에서 쟀는지 모르면 재사용 불가)
        diff += [f"{k} 조건 누락" for k, v in cond.items() if v is not None and k not in rc]
        if not diff:
            return r, ("공통 기록('*') - 적용 후보 미지정" if r.get("candidate_id") == "*" else f"{cand_id} 기록")
        stale.append(", ".join(diff))
    if stale:
        return None, "재검증 필요(조건 변경: " + "; ".join(stale) + ")"
    return None, "기록 없음"

DEFAULT_CANDIDATES = [
    {"id": "A", "name": "운영·기존 설비 개선", "role": "비교 기준",
     "levers_add": [], "levers_remove": [], "solids": None, "aging_days": None,
     "desc": "기존 배합·열풍 건조 유지. 구간 운전·풍량·히트펌프, 드라이룸 국소화·기밀, 화성 단축·회생, 에이징 14일+랙 전환"},
    {"id": "B0", "name": "복사 가열만 (고형분 유지)", "role": "비교 기준(고형분 효과 분리)",
     "levers_add": ["DRY-RAD"], "levers_remove": [], "solids": None, "aging_days": None,
     "desc": "A + 복사(NIR) 가열. 고형분은 기존 유지 - B1에서 고형분이 무엇을 더하는지 보기 위한 비교 기준"},
    {"id": "B1", "name": "용매 부하 선저감 + 복사 가열", "role": "주력 검증 후보",
     "levers_add": ["DRY-HSC", "DRY-RAD"], "levers_remove": [], "solids_rule": {"type": "delta", "value": 0.05}, "aging_days": None,
     "desc": "고형분 상향 후 남은 건조 부하에 복사(NIR) 가열 적용. 화성 16h, 에이징 14일 + 승인 공간 확보"},
    {"id": "B2", "name": "용매 부하 선저감 + 배기열 회수", "role": "주력 검증 후보",
     "levers_add": ["DRY-HSC", "DRY-HX"], "levers_remove": [], "solids_rule": {"type": "delta", "value": 0.05}, "aging_days": None,
     "desc": "고형분 상향 후 남은 건조 부하에 배기열 회수 적용. 화성 16h, 에이징 14일 + 승인 공간 확보"},
    {"id": "C", "name": "공간 제약 대응", "role": "조건부 대안", "base": "B",
     "levers_add": ["AGE-EARLY"], "levers_remove": ["AGE-RACK"], "solids": None, "aging_days": 13,
     "precondition": "space_insufficient",
     "desc": "선택된 B의 전극·유틸리티 구성 공유. 승인 공간이 부족할 때만 에이징 단축·조기 선별 검토(13일 예시)"},
]

# 검증 시험 - 기간·비용 등급은 팀 가정(견적 아님). 결과가 판정을 바꾸는지는 계산으로 정한다.
VERIFY_TESTS = [
    {"id": "HEAT-DRY", "question": "건조 가열원이 실제 전기인가?", "how": "계량기·P&ID·유틸리티 계약 확인",
     "cost": "낮음", "period": "1주"},
    {"id": "HEAT-DRM", "question": "드라이룸 제습 재생 열원이 전기인가?", "how": "제습기 사양·계량 확인",
     "cost": "낮음", "period": "1주"},
    {"id": "SOLIDS", "question": "목표 고형분에서 분산·점도·코팅 품질이 유지되는가?", "how": "배합 2수준 × 기준 배합 대조 시험",
     "cost": "중간", "period": "4-8주"},
    {"id": "DRY-SPEED", "question": "목표 속도(1.2배)에서 건조 품질(잔류 NMP·크랙·접착)이 유지되는가?",
     "how": "고형분 2수준 × 건조 프로파일 2수준 파일럿 코팅", "cost": "중간", "period": "4-8주"},
    {"id": "SPACE", "question": "14일 보관용 승인 공간을 확보할 수 있는가?", "how": "시설·방재·보험 검토로 승인 슬롯 산정",
     "cost": "중간", "period": "4주"},
    {"id": "FOR-OCC", "question": "PFMEA 검사 시간이 화성 채널을 얼마나 점유하는가?", "how": "채널 로그·검사 점유 계측",
     "cost": "낮음", "period": "1-2주"},
    {"id": "PHI", "question": "건조 계통 전력 중 용매 증발·응축·회수에 비례하는 비중은?", "how": "구간별(가열·팬·응축·회수·대기) 전력 계측",
     "cost": "낮음", "period": "2-4주"},
    {"id": "BURDEN", "question": "아직 정량화 안 된 관리 전력은 얼마인가?", "how": "FMEA 관리조치(검사·제습·혼합) 전력 계측",
     "cost": "낮음", "period": "2-4주"},
    {"id": "TRANSFER", "question": "문헌 절감 효과가 C사 라인에서 얼마나 재현되는가?", "how": "파일럿 전후 계통 전력 실측",
     "cost": "높음", "period": "3-6개월"},
    {"id": "JOINT", "question": "문헌 효과 재현율과 미정량 관리 전력이 함께 나빠지면?", "how": "파일럿 전후 계통 전력 + 관리조치 전력 동시 계측",
     "cost": "높음", "period": "3-6개월"},
    {"id": "KAPPA", "question": "같은 계통 안의 결합 효과가 독립적으로 남는가?", "how": "결합 운전 파일럿 실측",
     "cost": "높음", "period": "3-6개월"},
]
COST_RANK = {"낮음": 0, "중간": 1, "높음": 2}


# ================================================================== ① 공정 부하 연결
def mass_balance(s0, s1, q):
    """같은 전극 고형물 투입 기준. 용매/고형물 비 = (1-s)/s.

    solvent_per_solid_ratio: 고형물(=면적·로딩) 당 용매 비 (변경/기존) - 같은 생산량 비교, 건조 증발량/면적 비
    solvent_vs_base: 증산 후 총 용매량 / 기존(10 GWh) 총 용매량 = q × 위 비
    s1_min_keep_solvent: 증산 후에도 총 용매량을 늘리지 않는 최소 고형분 = q·s0 / (1 + (q-1)·s0)
    """
    if not (0 < s0 < 1 and 0 < s1 < 1):
        raise ValueError("고형분 질량분율은 0~1 사이")
    sa = ((1 - s1) / s1) / ((1 - s0) / s0)
    return {"s0": s0, "s1": s1, "q": q, "solvent_per_solid_ratio": sa, "solvent_vs_base": q * sa,
            "solvent_cut_same_output": 1 - sa, "s1_min_keep_solvent": q * s0 / (1 + (q - 1) * s0)}


def drying_residual(values, mb):
    """고형분 변경 후 남는 건조 계통 전력 / 고형분 변경 없는 증산 후 건조 전력 (보수·대표·낙관).

    건조 계통 = 고정부하 f + 변동부하(1-f). 변동부하 중 용매 비례 비중 φ만 용매량(R)을 따르고,
    나머지(기재 가열·이송 등)는 생산량(q)을 따른다. 팬·대기 등 고정부하는 용매가 줄어도 줄지 않는다.
    φ는 C사 계측 전까지 가정 범위 → 보수=φ 하한(절감 작음), 낙관=φ 상한.
    """
    q, f = values["q"], values["f"][DI]
    phi = phi_range(values)
    R = mb["solvent_vs_base"]
    base = f + (1 - f) * q
    out = {}
    for c, p in zip(CASES, (phi[0], phi[1], phi[2])):
        out[c] = (f + (1 - f) * (p * R + (1 - p) * q)) / base
    out["phi"] = list(phi)
    return out


def _weak(rows):
    return bool(rows) and all(S.GRADE_ORDER.index(e["grade"]) >= S.GRADE_ORDER.index("D") for e in rows)


def drying_axis(eff, eff_levers, values, s1=None, cand_id=None):
    """건조 처리능력: 고정 길이 오븐에서 속도 q배 → 가능 체류시간 1/q.

    필요 건조시간비 = 기술 시간비 t × 면적당 용매비. 면적당 증발량이 같으면 같은 시간이 필요하다는(증발속도 동일)
    단순 가정이며 감률 건조 구간은 반영하지 않는다. 기본은 t=1(질량수지만). 등급 D 이하 문헌 시간비는
    '그 근거에서만 성립'으로만 표시하고 성립 판단에 쓰지 않는다. 실측 속도 상한이 없으면 계산이 맞아도 '미확인'.
    """
    q = values["q"]
    s0 = solids_old(values)
    s1 = s1 if s1 is not None else s0
    mb = mass_balance(s0, s1, q)
    sa = mb["solvent_per_solid_ratio"]
    avail = 1.0 / q
    rows = [e for e in eff if e["metric"] == "drying_time_ratio" and e["lever_id"] in eff_levers
            and e["use"] != ee.USE_EXCL and e["typ"] is not None and e["lever_id"] != "DRY-HSC"]
    strong = [e for e in rows if S.GRADE_ORDER.index(e["grade"]) < S.GRADE_ORDER.index("D")]
    t_s = min((e["typ"] for e in strong), default=1.0)
    t_w = min((e["typ"] for e in rows), default=1.0)
    need = t_s * sa                       # 판정에 쓰는 필요 시간
    need_w = t_w * sa                     # 약한 근거까지 쓸 때
    calc_ok = need <= avail + TOL
    weak_ok = (not calc_ok) and need_w <= avail + TOL
    used_s = [e for e in strong if e["typ"] == t_s]
    used_w = [e for e in rows if e["typ"] == t_w]
    eh = {**ee.DEFAULT_ELECTRIC_HEATING, **(values.get("kb_electric_heating") or {})}
    cond = {"solids": round(s1, 4), "heat_dry": "전기" if eh.get("건조") else "가스·스팀",
            "drying_profile": values.get("drying_profile") or "기준"}
    rec, why = find_verification(values, cand_id, "drying_speed_ratio", cond)
    ver = rec["value"] if rec else None
    ver_note = f" [{why}]" if rec or why.startswith("재검증") else ""
    if ver is None and values.get("drying_max_speed_ratio_verified") is not None and not why.startswith("재검증"):
        ver = values["drying_max_speed_ratio_verified"]          # 하위 호환: 공통 입력
        ver_note = " [공통 입력 - 적용 후보 미지정]"
    basis = (f"기술 시간비 {t_s:.2f}({', '.join(e['effect_id'] for e in used_s)})" if used_s else "질량수지만(기술 시간비 1.00)")
    calc_txt = (f"필요 건조시간 {need:.3f} (= {basis} × 면적당 용매비 {sa:.3f}) vs 가능 체류 {avail:.3f}(속도 {q:g}배, 고정 길이)")
    weak_txt = (f"; 등급 D 근거 {', '.join(e['effect_id'] for e in used_w)}(시간비 {t_w:.2f}) 적용 시 필요 {need_w:.3f}"
                if used_w and t_w < t_s else "")
    if ver is not None:
        st = ST_DONE if ver >= q - TOL else ST_FAIL
        txt = f"실측 속도 상한 {ver:g}배 {'≥' if st == ST_DONE else '<'} 요구 {q:g}배{ver_note}. " + calc_txt
    elif calc_ok:
        st = ST_UNK
        txt = "계산상 충족, 실측 속도 상한 미확인" + ver_note + ". " + calc_txt + weak_txt
    elif weak_ok:
        st = ST_UNK
        txt = (f"질량수지로는 증발속도 {need / avail:.3f}배 필요 - 등급 D 근거에서만 성립, 실측 필요. " + calc_txt + weak_txt)
    else:
        st = ST_FAIL
        txt = f"증발속도 {need / avail:.3f}배 필요 - 패키지에 가열 보강 근거 없음. " + calc_txt + weak_txt
    return {"axis": "건조 처리능력", "state": st, "status": txt, "calc_ok": calc_ok, "weak_ok": weak_ok,
            "need_time_ratio": need, "need_time_ratio_weak": need_w, "available_time_ratio": avail,
            "evap_rate_multiplier": need / avail, "t_tech": t_s, "t_tech_weak": t_w,
            "ids": [e["effect_id"] for e in used_s], "ids_weak": [e["effect_id"] for e in used_w],
            "mass_balance": mb, "verified_speed": ver, "verification_note": ver_note.strip(" []"), "conditions": cond}


# ================================================================== 축별 상태
def energy_axis(cases):
    if cases["conservative"]["plant_ok"]:
        st, txt = ST_OK, "보수(근거 하한+부담 상한)에서도 충족"
    elif cases["typical"]["plant_ok"]:
        st, txt = ST_OK, "대표값 기준 충족 · 보수 기준 미달"
    else:
        st, txt = ST_FAIL, f"대표 기준 {cases['typical']['gap']:+.2f} pt 부족"
    t = cases["typical"]
    return {"axis": "전력 원단위(-30%)", "state": st,
            "status": f"{txt} (대표 절감 {t['saving'] * 100:.1f}%, E={t['E_total']:.2f} pt, 목표 {t['target_energy']:.0f} pt)"}


def formation_axis(cases, bur, values):
    import core
    t = cases["typical"]
    pend = [p["fmea_id"] for p in bur["pending"] if p["metric"] == "added_occupancy_h"]
    fm0 = core.formation_capacity(values["formation_h"], 0.0, values["channel_ratio"], values["availability_ratio"],
                                  values["yield_ratio"], values["baseline_formation_h"], values["target_capacity_ratio"])
    allow = fm0["allowed_added_h"]
    used = t["occupancy_h"]
    if not t["capacity_ok"]:
        st = ST_FAIL
        txt = f"처리능력 {t['capacity']:.3f}배 < 1.2배 (추가 점유 {used:.2f} h > 허용 {allow:.2f} h)"
    elif pend:
        st = ST_UNK
        txt = f"≤{t['capacity']:.3f}배 - 추가 채널 점유 미정량 {len(pend)}건, 남은 허용 {allow - used:.2f} h ({(allow - used) * 60:.0f}분)"
    else:
        st = ST_OK
        txt = f"{t['capacity']:.3f}배 (추가 점유 {used:.2f} h ≤ 허용 {allow:.2f} h)"
    return {"axis": "화성 처리능력(1.2배)", "state": st, "status": txt, "allowed_added_h": allow, "used_h": used,
            "pending": pend}


def aging_axis(eff, eff_levers, values, days_c, bur_age, cand_id=None):
    """필요 슬롯비 = q·cu/pu × (기간 + 추가 보관일)/기존 기간. 승인 슬롯(aging_slot_gain_approved)과 비교.

    공간은 시설 승인 사항이므로 승인값이 없으면 '미확인'(요구량만 제시). 단축(기간 < 기존)은 검출력 검증 전 '미확인'.
    """
    q, cu, pu = values["q"], values["current_utilization"], values["planned_utilization"]
    d0 = values.get("aging_days") or 14
    add = bur_age["aging_days"]["typ"]
    pend = [p["fmea_id"] for p in bur_age["pending"] if p["metric"] == "added_aging_days"]
    need = q * cu / pu * (days_c + add) / d0 - 1.0
    allowed_days = d0 * pu / (q * cu)
    rec, why = find_verification(values, cand_id, "aging_slot_gain", {"aging_days": days_c})
    appr = rec["value"] if rec else values.get("aging_slot_gain_approved")
    shorten = days_c < d0 - TOL
    arows = [e for e in eff if e["role"] == "aging" and e["use"] == ee.USE_CALC and e["lever_id"] in eff_levers]
    ev_ratio = min((e["typ"] for e in arows), default=None)
    pend_txt = f" [추가 보관일 미정량 {len(pend)}건]" if pend else ""
    if shorten and (ev_ratio is None or ev_ratio > days_c / d0 + TOL):
        st, txt = ST_FAIL, f"{days_c:g}일 단축 근거 없음"
    elif need <= TOL:
        st = ST_UNK if shorten else ST_OK
        txt = f"{days_c:g}일: 추가 슬롯 불필요(허용 평균 점유 {allowed_days:.3f}일)" + (" - 단축 검출력 검증 필요" if shorten else "")
    elif appr is None:
        st = ST_UNK
        txt = f"{days_c:g}일: 승인 슬롯 +{need * 100:.2f}% 필요(시설 검토 전)" + (" · 단축 검출력 검증 필요" if shorten else "")
    elif appr >= need - TOL:
        st = ST_UNK if shorten else ST_DONE
        txt = f"{days_c:g}일: 승인 슬롯 +{appr * 100:.1f}% ≥ 필요 +{need * 100:.2f}%" + (" · 단축 검출력 검증 필요" if shorten else "")
    else:
        st = ST_FAIL
        txt = f"{days_c:g}일: 승인 슬롯 +{appr * 100:.1f}% < 필요 +{need * 100:.2f}%"
    if shorten and ev_ratio is not None:
        g = min((e["grade"] for e in arows), key=S.GRADE_ORDER.index)
        txt += f" (단축 근거 기간비 {ev_ratio:.2f}, 최고 등급 {g} - 공격적 기간은 기본값으로 쓰지 않음)"
    return {"axis": "에이징 보관능력", "state": st, "status": txt + pend_txt, "days": days_c, "required_slot_gain": need,
            "allowed_days_without_slots": allowed_days, "approved": appr, "pending": pend, "shorten": shorten}


def quality_axis(qs):
    n = qs["counts"]
    if n["불합격"]:
        st = ST_FAIL
    elif n["미확인"] or n["재검증 필요"]:
        st = ST_UNK
    elif sum(n.values()):
        st = ST_DONE
    else:
        st = ST_UNK
    txt = " · ".join(f"{k} {v}" for k, v in n.items() if v) or "관문 없음"
    return {"axis": "품질·안전 관문", "state": st, "status": txt, "counts": n}


def overall_label(axes):
    q = next(a for a in axes if a["axis"].startswith("품질"))
    if q["counts"]["불합격"]:
        return "탈락 - 품질 불합격"
    fails = [a["axis"] for a in axes if a["state"] == ST_FAIL]
    if fails:
        return "미달 - " + ", ".join(fails)
    unk = [a["axis"] for a in axes if a["state"] == ST_UNK]
    if unk:
        return f"전력 목표 계산상 충족 · 현장 확인 {len(unk)}개 조건(" + ", ".join(unk) + ")"
    return ST_DONE if all(a["state"] == ST_DONE for a in axes) else ST_OK


# ================================================================== ② 동일 조건 후보 비교
def _B(values):
    return [wi * (fi + (1 - fi) * values["q"]) for wi, fi in zip(values["w"], values["f"])]


def _resolve(clean, spec, base_levers, b_levers=None):
    if spec.get("levers_exact"):                      # core 패키지 모드: 필요성 분석으로 정한 레버만
        known = {x["lever_id"] for x in clean["levers"]}
        bad = [l for l in spec["levers_exact"] if l not in known]
        if bad:
            raise ee.KBError(f"후보 {spec['id']}: 데이터셋에 없는 레버 {bad}")
        return list(spec["levers_exact"])
    src = list(b_levers) if spec.get("base") == "B" and b_levers is not None else list(base_levers)
    out = [l for l in src if l not in spec.get("levers_remove", [])]
    for l in spec.get("levers_add", []):
        if l not in out:
            out.append(l)
    known = {x["lever_id"] for x in clean["levers"]}
    bad = [l for l in out if l not in known]
    if bad:
        raise ee.KBError(f"후보 {spec['id']}: 데이터셋에 없는 레버 {bad}")
    return out


def _mask_hsc(eff):
    """고형분 변경을 질량수지로 계산하는 후보에서는 고형분 레버의 문헌 절감률을 쓰지 않는다(같은 부하 중복 차감 방지)."""
    return [({**e, "use": ee.USE_REF, "how": e["how"] + " [질량수지로 대체 - 후보 비교에서 미사용]"}
             if e["lever_id"] == "DRY-HSC" and e["role"] == "saving" and e["use"] == ee.USE_CALC else e) for e in eff]


def evaluate_candidate(clean, eff, spec, levers, values, alpha=1.0):
    if "FOR-FAST" not in levers and values.get("formation_h") != values.get("baseline_formation_h"):
        # 화성 단축 레버가 없으면 유효 화성시간 = 기존(20 h). 필요성 분석에서 FOR-FAST를 빼면 처리능력도 1.0배로 돌아간다
        values = {**values, "formation_h": values["baseline_formation_h"]}
    q = values["q"]
    s0 = solids_old(values)
    s1 = candidate_solids(spec, values, levers)
    B = _B(values)
    mb = mass_balance(s0, s1, q)
    # 질량수지 모드는 '고형분 레버가 패키지에 있는가'로만 정한다 (s1 == s0에서 문헌값으로 되돌아가는 불연속 방지)
    mass_mode = "DRY-HSC" in levers
    changed = mass_mode
    eff_c = _mask_hsc(eff) if mass_mode else eff
    res = drying_residual(values, mb) if mass_mode else None
    struct = values.get("drying_structure") or {}
    dry_scale = 1.0
    if mass_mode and struct.get("mode") == "M2":       # 복사 등 건조 레버 효과가 열 관련 비중 h에만 작용
        dry_scale = float(struct.get("h", 1.0))
    elif mass_mode and struct.get("mode") == "M3":     # 고형분의 전력 효과 0 (처리능력 효과만 인정)
        res = {c: 1.0 for c in CASES}
    sysr, _d, bur, cases = ee._run_cases(clean, eff_c, levers, values, B, drying_residual=res, scale=alpha,
                                         dry_scale=dry_scale)
    occ_pend = any(p["metric"] == "added_occupancy_h" for p in bur["pending"])
    for c in cases.values():
        c["capacity_upper_bound"] = occ_pend
    eff_l, _ = ee.effective_levers(clean, levers)
    bur_age = ee.burdens(clean, levers, [1.0] * len(S.SYSTEMS))
    days_c = spec.get("aging_days") or values.get("aging_days") or 14
    # 품질 관문 확인은 후보 자신의 조건(고형분·에이징 기간)으로 조회 - 다른 후보·다른 조건의 확인을 승계하지 않음
    cand_values = {**values, "solids": round(s1, 4), "aging_days": days_c, "candidate_id": spec["id"]}
    qs = ee.quality_status(clean, levers, cand_values)
    axes = [energy_axis(cases), drying_axis(eff_c, eff_l, values, s1, spec["id"]), formation_axis(cases, bur, values),
            aging_axis(eff_c, eff_l, values, days_c, bur_age, spec["id"]), quality_axis(qs)]
    label = overall_label(axes)
    fm_by = {f["fmea_id"]: f for f in clean["fmea"]}
    n_safety = sum("안전" in (fm_by.get(r["fmea_id"], {}).get("affected_list") or []) for r in qs["rows"])
    # 비용: 같은 기준선(증산 무개선 ΣB) 대비 감소 pt × 현재 공장 연간 전력 × 단가
    pe = ee.plant_electricity(eff, values)
    price = values.get("electricity_price_krw_per_kwh") or 100.0
    years = values.get("payback_years") or [3, 5]
    E0 = sum(B)

    def money(pt):
        if pe is None:
            return None
        g = (pt / 100 * pe["gwh_lo"], pt / 100 * pe["gwh_hi"])
        k = (g[0] * 1e6 * price / 1e8, g[1] * 1e6 * price / 1e8)
        return {"gwh": g, "krw_eok": k, "invest_eok": {n: (k[0] * n, k[1] * n) for n in years}}

    t = cases["typical"]
    shortfall = None
    if not t["plant_ok"]:
        import core
        pt = t["plant"]
        req = []
        for j, s in enumerate(S.SYSTEMS):
            rq = core.required_reduction(sum(pt["E"]) - pt["E"][j], pt["P_add"], pt["target_energy"], pt["B"][j])
            req.append({"system": s, "current": t["r"][j], "required": rq,
                        "feasible": rq is not None and rq <= 1})
        shortfall = {"gap_pt": t["gap"], "per_system": req,
                     "text": f"추가로 {t['gap']:.2f} pt(기준 공장 100 대비) 감소 필요 - 한 계통만으로 보완 시 요구 절감률: "
                             + ", ".join(f"{r['system']} {r['required'] * 100:.1f}%" + ("" if r["feasible"] else "(불가)")
                                         for r in req if r["required"] is not None)}
    scope = max((ee.CHANGE_ORDER.get(ee._lever(clean, l).get("change_type") or "", 0) for l in eff_l
                 if ee._lever(clean, l)["exclusive_group"] != "BASE"), default=0)
    return {"id": spec["id"], "name": spec["name"], "role": spec.get("role", ""), "desc": spec.get("desc", ""),
            "levers": list(levers), "solids": s1, "solids_changed": changed, "mass_balance": mb, "drying_residual": res,
            "r_drying": [c["r"][DI] for c in (cases[k] for k in CASES)],
            "cases": cases, "saving": tuple(cases[k]["saving"] for k in CASES), "E_typ": t["E_total"],
            "margin_pt": -t["gap"], "E0": E0, "pt_saved": (E0 - cases["conservative"]["E_total"], E0 - t["E_total"]),
            "money_typ": money(E0 - t["E_total"]), "money_cons": money(E0 - cases["conservative"]["E_total"]),
            "axes": axes, "label": label, "n_fail": sum(a["state"] == ST_FAIL for a in axes),
            "n_unk": sum(a["state"] == ST_UNK for a in axes), "quality": qs, "burdens": bur,
            "n_gates": len(qs["rows"]), "n_safety_gates": n_safety,
            "n_weak": int(bool(axes[1].get("weak_ok")) and axes[1]["state"] != ST_DONE),
            "scope": scope + (1 if changed else 0), "shortfall": shortfall,
            "precondition": spec.get("precondition"), "aging_days": days_c}


def _rank_key(c, base_levers):
    """미달 축 수 → 약한 근거(등급 D)에만 기대는 축 수 → 변경 범위 → 미확인 축 수 → 변경 레버 수."""
    extra = len(set(c["levers"]) ^ set(base_levers))
    return (c["n_fail"], c.get("n_weak", 0), c["scope"], c["n_unk"], extra, -c["saving"][1])


def run_candidates(values, clean=None, eff=None, alpha=1.0, solids_B=None, specs=None):
    """모든 후보를 같은 입력으로 계산하고 선택 규칙에 따라 추천 후보를 고른다.

    선택 규칙: 품질 불합격 후보 제외 → C는 승인 공간이 B의 요구량보다 작을 때만 → 미달 축 수 → 변경 범위
    → 미확인 축 수 → 기준 대비 변경 레버 수. 모두 미달이면 미달 축이 적고 부족 pt가 작은 후보를 '최선 미달 후보'로.
    """
    if clean is None:
        clean, _ = ee.validate_kb(ee.load_kb())
    eh = {**ee.DEFAULT_ELECTRIC_HEATING, **(values.get("kb_electric_heating") or {})}
    if eff is None:
        eff = ee.classify_effects(clean, values["w"], eh, bool(values.get("kb_allow_cross_share")),
                                  ee.plant_basis(clean, values))
        eff = ee.apply_effect_selection(eff, values.get("kb_effect_selection"))
    specs = copy.deepcopy(specs or values.get("kb_candidates") or DEFAULT_CANDIDATES)
    base = values.get("kb_selected_levers") or [l["lever_id"] for l in clean["levers"] if l.get("v10_adopted") == "예"]
    out, skipped = [], []
    for sp in [s for s in specs if s.get("base") != "B"]:
        if solids_B is not None and "DRY-HSC" in sp.get("levers_add", []):
            sp["solids_override"] = solids_B
        try:
            lev = _resolve(clean, sp, base)
        except ee.KBError as e:
            skipped.append({"id": sp["id"], "reason": str(e)})
            continue
        out.append(evaluate_candidate(clean, eff, sp, lev, values, alpha))
    bs = [c for c in out if c["id"].startswith("B") and c["quality"]["counts"]["불합격"] == 0]
    best_b = min(bs, key=lambda c: _rank_key(c, base)) if bs else None
    for sp in [s for s in specs if s.get("base") == "B"]:
        if best_b is None:
            continue
        sp["name"] = f"{sp['name']} ({best_b['id']} 기반)"
        if sp.get("solids") is None and not sp.get("solids_rule"):
            sp["solids"] = best_b["solids"]
        try:
            lev = _resolve(clean, sp, base, best_b["levers"])
        except ee.KBError as e:
            skipped.append({"id": sp["id"], "reason": str(e)})
            continue
        out.append(evaluate_candidate(clean, eff, sp, lev, values, alpha))
    appr = values.get("aging_slot_gain_approved")
    need_b = next((a["required_slot_gain"] for a in (best_b or {}).get("axes", []) if a["axis"].startswith("에이징")), None)
    space_short = appr is not None and need_b is not None and appr < need_b - TOL
    for c in out:
        if c["quality"]["counts"]["불합격"]:
            c["eligible"], c["why_not"] = False, "품질 불합격"
        elif c["precondition"] == "space_insufficient" and not space_short:
            c["eligible"], c["why_not"] = False, ("승인 공간이 부족할 때만 검토 (승인 슬롯 미확인)" if appr is None
                                                  else "승인 공간이 B 요구량 이상 - 단축 불필요")
        else:
            c["eligible"], c["why_not"] = True, ""
    el = [c for c in out if c["eligible"]]
    passing = [c for c in el if not c["n_fail"]]
    if passing:
        sel = min(passing, key=lambda c: _rank_key(c, base))
    else:   # 모두 미달: 미달 축이 적고 전력 부족분이 작은 후보
        sel = min(el, key=lambda c: (c["n_fail"], -c["margin_pt"])) if el else None
    if sel is None:
        status = "추천 후보 없음 - 모든 후보 품질 탈락 또는 전제 미충족"
    elif sel["n_fail"]:
        status = f"최선 미달 후보 {sel['id']} - {sel['label']}"
    else:
        status = f"조건부 추천 {sel['id']} - {sel['label']}" if sel["n_unk"] else f"{sel['id']} 추천 - {sel['label']}"
    return {"candidates": out, "skipped": skipped, "selected": sel["id"] if sel else None, "status": status, "base_levers": base,
            "space_short": space_short, "clean": clean, "eff": eff}


# ================================================================== ③ 실패 경계
def _bisect(f, lo, hi, n=60):
    """f(lo) != f(hi)인 단조 판정의 경계."""
    flo = f(lo)
    for _ in range(n):
        mid = (lo + hi) / 2
        if f(mid) == flo:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def boundaries(values, clean, eff, spec_id, run=None):
    """선택 후보의 판정이 바뀌는 경계값 (결정적 역산). 각 항목은 경계 바로 안팎에서 판정이 바뀐다."""
    run = run or run_candidates(values, clean, eff)
    cand = next(c for c in run["candidates"] if c["id"] == spec_id)
    specs = values.get("kb_candidates") or DEFAULT_CANDIDATES
    spec = next((s for s in specs if s["id"] == spec_id), None)
    if spec is None:   # C처럼 이름이 바뀐 경우
        spec = next(s for s in specs if s.get("base") == "B" and spec_id == s["id"])
    spec = {**spec, "solids": cand["solids"]}
    lev = cand["levers"]

    def ok_energy(v=None, alpha=1.0, s=None):
        sp = {**spec, "solids_override": s} if s is not None else spec
        c = evaluate_candidate(clean, eff, sp, lev, v or values, alpha)
        return c["cases"]["typical"]["plant_ok"]

    out = []
    base_ok = cand["cases"]["typical"]["plant_ok"]
    # 문헌 효과 전이율 α
    if ok_energy(alpha=2.0) != ok_energy(alpha=0.0):
        a = _bisect(lambda x: ok_energy(alpha=x), 0.0, 2.0)
        out.append({"kind": "문헌 효과 전이율", "value": a, "unit": "×대표값", "current": 1.0,
                    "text": f"문헌 절감 효과가 대표값의 {a * 100:.0f}% 아래로 줄면 전력 목표 미달 (현재 100%)"
                    if base_ok else f"문헌 효과가 대표값의 {a * 100:.0f}% 이상이어야 전력 목표 충족 (현재 100%)"})
    # 관리 전력
    m = cand["margin_pt"]
    out.append({"kind": "추가 관리 전력", "value": max(m, 0.0), "unit": "pt", "current": values.get("kb_extra_burden_pt") or 0.0,
                "text": (f"미정량 관리 전력 합이 {m:.2f} pt를 넘으면 전력 목표 미달 (1 pt = 원단위 절감 {100 / (100 * values['q']):.3f}%p)"
                         if m >= 0 else f"이미 {-m:.2f} pt 부족")})
    # 화성 추가 점유
    fa = next(a for a in cand["axes"] if a["axis"].startswith("화성"))
    out.append({"kind": "화성 추가 채널 점유", "value": fa["allowed_added_h"] - fa["used_h"], "unit": "h", "current": fa["used_h"],
                "text": f"검사·진단 등 추가 채널 점유가 {(fa['allowed_added_h'] - fa['used_h']) * 60:.0f}분을 넘으면 처리능력 1.2배 미달 "
                        f"(총 허용 {fa['allowed_added_h'] * 60:.0f}분)"})
    # 에이징
    aa = next(a for a in cand["axes"] if a["axis"].startswith("에이징"))
    out.append({"kind": "에이징 승인 슬롯", "value": aa["required_slot_gain"], "unit": "비율", "current": aa["approved"],
                "text": f"승인 슬롯이 +{aa['required_slot_gain'] * 100:.2f}% 미만이면 {aa['days']:g}일 보관 미달 "
                        f"(슬롯 무증설 허용 평균 점유 {aa['allowed_days_without_slots']:.3f}일 - 품질 보장 기간 아님)"})
    # 고형분 (질량수지 후보만)
    if cand["solids_changed"]:
        s0 = solids_old(values)
        smin_dry = None
        da = next(a for a in cand["axes"] if a["axis"].startswith("건조"))
        t, tw = da["t_tech"], da["t_tech_weak"]
        # 필요 시간 t·sa ≤ 1/q → sa ≤ 1/(q t) → s1 ≥ 1/(1 + k0/(q t))   (t=1이면 = 용매량 유지 고형분 q·s0/(1+(q-1)s0))
        k0 = (1 - s0) / s0
        smin_dry = 1.0 / (1.0 + k0 / (values["q"] * t))
        smin_w = 1.0 / (1.0 + k0 / (values["q"] * tw))
        out.append({"kind": "고형분(건조 처리능력)", "value": smin_dry, "unit": "질량분율", "current": cand["solids"],
                    "text": f"고형분 {smin_dry * 100:.3f}% 미만이면 증발속도 동일 가정에서 체류 {1 / values['q']:.3f}배 안에 건조 불가"
                            + (f" (등급 D 시간비 {tw:.2f}를 쓰면 {smin_w * 100:.1f}% - 판정에 쓰지 않음)" if tw < t else "")})
        hi = 0.80
        if ok_energy(s=hi) != ok_energy(s=s0 + 1e-6):
            se = _bisect(lambda x: ok_energy(s=x), s0 + 1e-6, hi)
            out.append({"kind": "고형분(전력)", "value": se, "unit": "질량분율", "current": cand["solids"],
                        "text": f"고형분 {se * 100:.2f}% 미만이면 전력 목표 미달 (현재 {cand['solids'] * 100:.1f}%)"})
        else:
            out.append({"kind": "고형분(전력)", "value": None, "unit": "질량분율", "current": cand["solids"],
                        "text": ("고형분 60~80% 범위에서 전력 판정이 바뀌지 않음 - 다른 레버가 전력 목표를 좌우" if base_ok
                                 else "고형분 80%까지 올려도 전력 목표 미달")})
        phi = phi_range(values)

        def ok_phi(p):
            return ok_energy(v={**values, "drying_solvent_load_share": [p, p, p]})
        if ok_phi(1.0) != ok_phi(0.0):
            pm = _bisect(ok_phi, 0.0, 1.0)
            out.append({"kind": "용매 비례 부하 비중 φ", "value": pm, "unit": "비율", "current": phi[1],
                        "text": f"건조 계통 변동부하 중 용매 비례 비중이 {pm * 100:.0f}% 아래면 전력 목표 미달 (가정 범위 "
                                f"{phi[0] * 100:.0f}~{phi[2] * 100:.0f}%, 대표 {phi[1] * 100:.0f}%)"})
        else:
            out.append({"kind": "용매 비례 부하 비중 φ", "value": None, "unit": "비율", "current": phi[1],
                        "text": "φ 0~100% 전 범위에서 전력 판정 불변"})
    for b in out:
        b["text"] += " [단독 경계: 다른 입력 고정]"
    out.append({"kind": "건조 속도 상한", "value": values["q"], "unit": "배", "current": values.get("drying_max_speed_ratio_verified"),
                "text": f"실측 건조 속도 상한이 {values['q']:g}배 미만이면 증산 미달 (현재 미계측이면 판정 보류)"})
    return out


def check_boundary_consistency(values, clean, eff, spec_id, eps=1e-3):
    """경계 바로 안팎에서 판정이 실제로 바뀌는지 (구현 완료 조건 ③). 항목별 True/False."""
    run = run_candidates(values, clean, eff)
    cand = next(c for c in run["candidates"] if c["id"] == spec_id)
    spec = {**next(s for s in (values.get("kb_candidates") or DEFAULT_CANDIDATES) if s["id"] == spec_id), "solids": cand["solids"]}
    res = {}
    for b in boundaries(values, clean, eff, spec_id, run):
        if b["value"] is None:
            continue
        if b["kind"] == "문헌 효과 전이율":
            f = lambda x: evaluate_candidate(clean, eff, spec, cand["levers"], values, x)["cases"]["typical"]["plant_ok"]
        elif b["kind"] == "추가 관리 전력":
            base_p = values.get("kb_extra_burden_pt") or 0.0
            f = lambda x: evaluate_candidate(clean, eff, spec, cand["levers"], {**values, "kb_extra_burden_pt": base_p + x})["cases"]["typical"]["plant_ok"]
        elif b["kind"] == "고형분(전력)":
            f = lambda x: evaluate_candidate(clean, eff, {**spec, "solids_override": x}, cand["levers"], values)["cases"]["typical"]["plant_ok"]
        elif b["kind"] == "고형분(건조 처리능력)":
            f = lambda x: next(a for a in evaluate_candidate(clean, eff, {**spec, "solids_override": x}, cand["levers"], values)["axes"]
                               if a["axis"].startswith("건조"))["calc_ok"]
        elif b["kind"] == "화성 추가 채널 점유":
            base_o = values.get("kb_extra_occupancy_h") or 0.0
            f = lambda x: evaluate_candidate(clean, eff, spec, cand["levers"], {**values, "kb_extra_occupancy_h": base_o + x})["cases"]["typical"]["capacity_ok"]
        elif b["kind"] == "용매 비례 부하 비중 φ":
            f = lambda x: evaluate_candidate(clean, eff, spec, cand["levers"], {**values, "drying_solvent_load_share": [x] * 3})["cases"]["typical"]["plant_ok"]
        elif b["kind"] == "에이징 승인 슬롯":
            f = lambda x: next(a for a in evaluate_candidate(clean, eff, spec, cand["levers"], {**values, "aging_slot_gain_approved": x})["axes"]
                               if a["axis"].startswith("에이징"))["state"] != ST_FAIL
        elif b["kind"] == "건조 속도 상한":
            f = lambda x: next(a for a in evaluate_candidate(clean, eff, spec, cand["levers"], {**values, "drying_max_speed_ratio_verified": x})["axes"]
                               if a["axis"].startswith("건조"))["state"] != ST_FAIL
        else:
            continue
        v = b["value"]
        d = eps * max(1.0, abs(v))
        res[b["kind"]] = f(v - d) != f(v + d)
    return res


# ================================================================== ④ 검증 우선순위
def _variants(test_id, values, run):
    sel = next((c for c in run["candidates"] if c["id"] == run["selected"]), None)
    eh = {**ee.DEFAULT_ELECTRIC_HEATING, **(values.get("kb_electric_heating") or {})}
    need = next((a["required_slot_gain"] for a in (sel or {}).get("axes", []) if a["axis"].startswith("에이징")), 0.1368)
    phi = phi_range(values)
    s0 = solids_old(values)
    q = values["q"]
    sel_id = (sel or {}).get("id", "*")
    dry = next((a for a in (sel or {}).get("axes", []) if a["axis"].startswith("건조")), {})

    def _ver(x):   # 선택 후보 자신의 조건으로 기록 (다른 후보에 승계되지 않음)
        return list(values.get("kb_verifications") or []) + [
            {"candidate_id": sel_id, "metric": "drying_speed_ratio", "value": x, "conditions": dry.get("conditions") or {},
             "evidence": "검증 우선순위 시나리오"}]
    return {
        "HEAT-DRY": [("가스·스팀 가열", {"kb_electric_heating": {**eh, "건조": False}}, {}),
                     ("전기 가열", {"kb_electric_heating": {**eh, "건조": True}}, {})],
        "HEAT-DRM": [("가스·스팀 재생", {"kb_electric_heating": {**eh, "드라이룸": False}}, {}),
                     ("전기 재생", {"kb_electric_heating": {**eh, "드라이룸": True}}, {})],
        "SOLIDS": [("고형분 상향 실패(기존 유지)", {}, {"solids_B": s0}), ("목표 고형분 확보", {}, {})],
        "DRY-SPEED": [(f"{sel_id} 속도 상한 {q - 0.1:.1f}배", {"kb_verifications": _ver(round(q - 0.1, 3))}, {}),
                      (f"{sel_id} 속도 상한 {q:g}배 이상", {"kb_verifications": _ver(q)}, {})],
        "SPACE": [("승인 슬롯 0%", {"aging_slot_gain_approved": 0.0}, {}),
                  ("승인 슬롯 +6%", {"aging_slot_gain_approved": 0.06}, {}),
                  (f"승인 슬롯 +{need * 100:.1f}% 이상", {"aging_slot_gain_approved": need + 1e-6}, {})],
        "FOR-OCC": [("추가 점유 60분", {"kb_extra_occupancy_h": 1.0}, {}), ("추가 점유 15분", {"kb_extra_occupancy_h": 0.25}, {})],
        "PHI": [(f"φ {phi[0] * 100:.0f}%", {"drying_solvent_load_share": [phi[0]] * 3}, {}),
                (f"φ {phi[2] * 100:.0f}%", {"drying_solvent_load_share": [phi[2]] * 3}, {})],
        "BURDEN": [("+5 pt", {"kb_extra_burden_pt": 5.0}, {}), ("0 pt", {"kb_extra_burden_pt": 0.0}, {})],
        "TRANSFER": [("문헌 대표값의 70%", {}, {"alpha": 0.7}), ("문헌 대표값 100%", {}, {"alpha": 1.0})],
        "JOINT": [("문헌 효과 90% + 관리 전력 4 pt", {"kb_extra_burden_pt": (values.get("kb_extra_burden_pt") or 0.0) + 4.0}, {"alpha": 0.9}),
                  ("문헌 효과 100% + 관리 전력 0 pt", {}, {"alpha": 1.0})],
        "KAPPA": [("κ = 0.5", {"kb_combine_retention": 0.5}, {}), ("κ = 1", {"kb_combine_retention": 1.0}, {})],
    }[test_id]


def short_label(label):
    """표·CSV용 짧은 판정."""
    if label.startswith("전력 목표 계산상 충족"):
        n = label.split("현장 확인 ")[1].split("개")[0]
        return f"조건부(확인 {n}개)"
    if label.startswith("미달 - "):
        return "미달(" + ", ".join(x.split("(")[0].replace(" 처리능력", "").replace(" 보관능력", "") for x in label[5:].split(", ")) + ")"
    return label


def verification_priority(values, clean, eff, run):
    """불확실한 입력의 양끝에서 다시 계산해 추천 후보·목표 판정이 바뀌는지 본다 (확률·기대정보가치 아님)."""
    base_sel = run["selected"]
    sel_c = next((c for c in run["candidates"] if c["id"] == base_sel), None)
    rows = []
    for t in VERIFY_TESTS:
        outs = []
        for lab, vo, ko in _variants(t["id"], values, run):
            v2 = {**values, **vo}
            eff2 = None if "kb_electric_heating" in vo else eff
            r2 = run_candidates(v2, clean, eff2, alpha=ko.get("alpha", 1.0), solids_B=ko.get("solids_B"))
            c2 = next((c for c in r2["candidates"] if c["id"] == r2["selected"]), None)
            dry = next((a for a in c2["axes"] if a["axis"].startswith("건조")), {}) if c2 else {}
            outs.append({"case": lab, "selected": r2["selected"], "label": c2["label"] if c2 else "-",
                         "dry_basis": "계산 성립" if dry.get("calc_ok") else "D등급 근거에서만" if dry.get("weak_ok") else "불성립",
                         "energy": next(a["state"] for a in c2["axes"]) if c2 else "-",
                         "saving_typ": c2["saving"][1] if c2 else None, "n_fail": c2["n_fail"] if c2 else None})
        sels = {o["selected"] for o in outs}
        fails = {(o["n_fail"] or 0) > 0 for o in outs}
        same_saving = len({round(o["saving_typ"] or 0, 9) for o in outs}) == 1
        if t["id"] == "KAPPA" and same_saving and len(sels) == 1:
            rows.append({**t, "outcomes": outs, "impact": "해당 없음", "impact_rank": 9,
                         "text": "선택 후보에는 κ가 작용하는 결합이 없음(고형분×건조 레버는 질량수지로 κ 밖에서 계산) - 순위 제외"})
            continue
        if len(sels) > 1:
            impact, rank = "추천 후보 변경", 0
        elif len(fails) > 1:
            impact, rank = "목표 판정 변경", 1
        elif len({o["label"] for o in outs}) > 1:
            impact, rank = "판정 상태 변경(보류↔충족)", 2
        elif len({o["dry_basis"] for o in outs}) > 1:
            impact, rank = "건조 판정 근거 약화(질량수지 성립 ↔ D등급 근거에서만)", 2
        else:
            impact, rank = "변화 없음", 3
        rows.append({**t, "outcomes": outs, "impact": impact, "impact_rank": rank,
                     "text": " / ".join(f"{o['case']} → {o['selected'] or '-'} {short_label(o['label'])}"
                                        + (f"[건조 {o['dry_basis']}]" if rank == 2 and "건조" in impact else "") for o in outs)})
    rows.sort(key=lambda r: (r["impact_rank"], COST_RANK.get(r["cost"], 9)))
    for i, r in enumerate(rows, 1):
        r["priority"] = i
    mandatory = []
    if sel_c:
        aff = {f["fmea_id"]: f for f in clean["fmea"]}
        for g in sel_c["quality"]["rows"]:
            if g["status"] == "확인":
                continue
            fr = aff.get(g["fmea_id"], {})
            mandatory.append({"fmea_id": g["fmea_id"], "lever_id": g["lever_id"], "gate": g["gate"], "status": g["status"],
                              "safety": "안전" in (fr.get("affected_list") or [])})
        mandatory.sort(key=lambda m: (not m["safety"], m["lever_id"]))
    return {"tests": rows, "mandatory": mandatory,
            "note": "안전·품질 관문은 판정 영향과 무관하게 먼저 수행한다. 나머지는 추천 후보를 바꾸는 시험 → 목표 판정을 바꾸는 시험 → "
                    "비용이 낮은 시험 순. 기간·비용 등급은 팀 가정이며 견적이 아니다. 확률분포가 없으므로 기대정보가치를 계산하지 않는다."}


# ================================================================== 품질 관문 검출력
def miss_rate_upper(n, conf=0.95):
    """독립 결함 양성 표본 n개에서 미검출 0건일 때 미검출 확률의 단측 정확 이항 상한 = 1 - (1-conf)^(1/n)."""
    if n <= 0:
        raise ValueError("n은 양수")
    return 1.0 - (1.0 - conf) ** (1.0 / n)


def n_for_miss_rate(p_upper, conf=0.95):
    """미검출 0건으로 상한 p_upper를 보이려면 필요한 결함 양성 표본 수."""
    if not 0 < p_upper < 1:
        raise ValueError("p_upper는 0~1")
    return math.ceil(math.log(1.0 - conf) / math.log(1.0 - p_upper) - 1e-12)


def detection_table(conf=0.95):
    return [{"n_defect_samples": n, "miss_upper": miss_rate_upper(n, conf)} for n in (50, 100, 300, 600, 1000)]


def sys_change(r):
    """계통 절감률 r(음수 = 전력 증가)을 오해 없는 말로."""
    return f"절감 {r * 100:.1f}%" if r >= 0 else f"전력 {-r * 100:.1f}% 증가"


# ================================================================== 열원 민감도 · 단계별 누적 효과
HEAT_CASES = [("기준(건조·드라이룸 전기)", {}), ("건조 가스·스팀", {"건조": False}),
              ("드라이룸 재생 가스·스팀", {"드라이룸": False}), ("둘 다 가스·스팀", {"건조": False, "드라이룸": False})]


def heat_sensitivity(values, clean):
    """후보별로 열원 가정만 바꿔 다시 계산 (각 후보 자신의 구성으로 - 다른 조합의 값을 옮겨 쓰지 않도록)."""
    base_eh = {**ee.DEFAULT_ELECTRIC_HEATING, **(values.get("kb_electric_heating") or {})}
    rows = []
    for lab, ch in HEAT_CASES:
        eh = {**base_eh, **ch}
        r = run_candidates({**values, "kb_electric_heating": eh}, clean)
        for c in r["candidates"]:
            t = c["cases"]["typical"]
            rows.append({"case": lab, "candidate": c["id"], "selected": c["id"] == r["selected"],
                         "saving": c["saving"], "margin_pt": c["margin_pt"],
                         "r_drying": t["r"][DI], "r_dryroom": t["r"][ee.SYS_IDX["드라이룸"]],
                         "energy_state": c["axes"][0]["state"], "label": c["label"]})
    return {"rows": rows, "cases": [c for c, _ in HEAT_CASES],
            "note": "각 후보를 자기 구성 그대로 열원만 바꿔 재계산. 계통 절감률이 음수면 그 계통 전력이 늘어난다는 뜻. "
                    "C는 열원 조건과 관계없이 B1 구성 기반이다(그 열원에서 최선 B가 바뀌면 C도 그 B 기반으로 다시 정의해야 함). "
                    "가스·스팀 가열에서는 합산 절감률 대신 전력 절대 증감·설비 전기 변화율 근거를 쓴다."}


STAGE_OF = {"운영변경": 1, "설비개조": 2, "설비교체": 3, "공정전환": 9}
STAGE_KO = {1: "1년차 운영 변경", 2: "2년차 설비 개조", 3: "3년차 설비 교체"}


def stage_progress(values, clean, eff, cand):
    """선택 후보의 레버를 변경 유형 순서(운영변경 → 설비개조 → 설비교체)로 쌓았을 때 단계별 누적 결과.

    고형분 상향(DRY-HSC)은 그 레버가 들어가는 단계부터 질량수지로 반영. 연도별 성과를 미리 확정하는 값이 아니라
    '그 단계까지의 레버만 적용했을 때' 같은 기준선에서의 계산값이다.
    """
    s0 = solids_old(values)
    by = {}
    for l in cand["levers"]:
        lv = ee._lever(clean, l)
        if lv["exclusive_group"] == "BASE":
            continue
        st = 9 if lv.get("horizon") == "장기" else STAGE_OF.get(lv.get("change_type") or "운영변경", 1)
        by.setdefault(st, []).append(l)
    out, acc = [], []
    for st in (1, 2, 3):
        add = by.get(st, [])
        if not add and st != 1:
            continue
        acc = acc + add
        sp = {"id": f"{cand['id']}-{st}", "name": STAGE_KO[st],
              "solids": cand["solids"] if "DRY-HSC" in acc else s0, "aging_days": cand.get("aging_days")}
        c = evaluate_candidate(clean, eff, sp, list(acc), values)
        out.append({"stage": STAGE_KO[st], "added": add, "levers": list(acc), "solids": sp["solids"],
                    "saving": c["saving"], "margin_pt": c["margin_pt"], "E_typ": c["E_typ"],
                    "axes": {a["axis"]: a["state"] for a in c["axes"]}, "label": c["label"],
                    "money_typ": c["money_typ"]})
    return {"candidate": cand["id"], "stages": out, "excluded_long": by.get(9, []),
            "note": "변경 유형(운영변경 → 설비개조 → 설비교체) 순서로 레버를 누적한 같은 기준선 계산값. "
                    "실측·품질 관문 통과 전 성과가 아니며, 근거 없는 레버는 0으로 계산된다."}


def reverse_models(values, cand_a):
    """단일 계통 역산 세 모델: ① 전부 비례(f=0) 무개선 ② 고정부하 엔진 무개선 ③ 후보 A 적용 후 남은 부족분."""
    q, w, f = values["q"], values["w"], values["f"]
    tgt = 100.0 * q * values["target_intensity_ratio"]
    B_lin = [wi * q for wi in w]
    B = _B(values)
    a_req = {r["system"]: r["required"] for r in ((cand_a or {}).get("shortfall") or {}).get("per_system", [])}
    rows = []
    for j, s in enumerate(S.SYSTEMS):
        r1 = (sum(B_lin) - tgt) / B_lin[j] if B_lin[j] else None
        r2 = (sum(B) - tgt) / B[j] if B[j] else None
        rows.append({"system": s, "w": w[j], "f": f[j], "B_linear": B_lin[j], "B_engine": B[j],
                     "linear": r1, "engine": r2, "after_A": a_req.get(s)})
    return {"rows": rows, "target": tgt, "sum_linear": sum(B_lin), "sum_engine": sum(B),
            "gap_linear": sum(B_lin) - tgt, "gap_engine": sum(B) - tgt,
            "gap_after_A": ((cand_a or {}).get("shortfall") or {}).get("gap_pt"),
            "note": "① 모든 부하가 생산량에 비례(f=0) ② 고정부하 f 반영(엔진 기준선) ③ 후보 A를 적용한 뒤 남은 부족분. "
                    "서로 다른 모델이므로 한 표 안에서 섞어 쓰지 않는다. 100% 초과는 그 계통 단독으로는 불가능."}


# ================================================================== 전체
def core_specs(values, run, clean):
    """kb_package_mode = 'core': 후보마다 레버 필요성 분석의 '핵심 + 처리능력 기여' 레버만 남긴 후보 정의."""
    import necessity
    specs = copy.deepcopy(values.get("kb_candidates") or DEFAULT_CANDIDATES)
    by_id = {c["id"]: c for c in run["candidates"]}
    for sp in specs:
        c = by_id.get(sp["id"])
        if c is None:
            continue
        ne = necessity.lever_necessity(values, clean, run["eff"], c)
        sp["levers_exact"] = ne["core"]["levers"]
        sp["name"] = sp["name"].split(" (")[0] + " [핵심 레버]"
    return specs


def evaluate(values, clean=None, eff=None):
    run = run_candidates(values, clean, eff)
    clean, eff = run["clean"], run["eff"]
    mode = values.get("kb_package_mode") or "full"
    full_summary = None
    if mode == "core":
        full_summary = {c["id"]: {"saving": c["saving"], "n_gates": c["n_gates"], "levers": c["levers"]} for c in run["candidates"]}
        values = {**values, "kb_candidates": core_specs(values, run, clean)}
        run = run_candidates(values, clean, eff)
    sel = run["selected"]
    bnd = boundaries(values, clean, eff, sel, run) if sel else []
    pri = verification_priority(values, clean, eff, run)
    switch = switch_conditions(run, bnd)
    sel_c = next((c for c in run["candidates"] if c["id"] == sel), None)
    mods = {}
    import baseline, capacity, joint, necessity   # v12 분석 모듈 (실패해도 나머지는 출력)
    for key, fn in (("baseline_model", lambda: baseline.analyze(values, run, clean)),
                    ("necessity", lambda: necessity.analyze(values, run, clean)),
                    ("joint", lambda: joint.analyze(values, run, clean))):
        try:
            mods[key] = fn()
        except Exception as e:  # noqa: BLE001 - 분석 하나가 실패해도 보고서는 나와야 한다
            mods[key] = {"error": f"계산 보류: {type(e).__name__}: {e}"}
    try:
        import upside
        mods["upside"] = upside.analyze(values, run, (mods.get("necessity") or {}).get("necessity"))
    except Exception as e:  # noqa: BLE001
        mods["upside"] = {"error": f"계산 보류: {type(e).__name__}: {e}"}
    try:
        import economics
        mods["economics"] = economics.analyze(values, run, clean, ee.plant_electricity(eff, values), mods.get("necessity"))
    except Exception as e:  # noqa: BLE001
        mods["economics"] = {"error": f"계산 보류: {type(e).__name__}: {e}"}
    try:
        import heat_integration
        mods["heat_map"] = heat_integration.analyze(values)
    except Exception as e:  # noqa: BLE001
        mods["heat_map"] = {"error": f"계산 보류: {type(e).__name__}: {e}"}
    try:
        mods["capacity"] = capacity.analyze(values, run, clean, (mods.get("necessity") or {}).get("necessity"))
    except Exception as e:  # noqa: BLE001
        mods["capacity"] = {"error": f"계산 보류: {type(e).__name__}: {e}"}
    try:
        import roadmap   # v12.1 PPT용 표(공간 수지·도달도·시기 분류·영향평가) - 판정 미반영
        mods["roadmap"] = roadmap.analyze(values, run, mods.get("capacity"), (mods.get("necessity") or {}).get("necessity"),
                                          mods.get("economics"), (mods.get("baseline_model") or {}).get("waterfall"),
                                          ((mods.get("joint") or {}).get("region") or {}).get("alpha_star"))
    except Exception as e:  # noqa: BLE001
        mods["roadmap"] = {"error": f"계산 보류: {type(e).__name__}: {e}"}
    mods["package_mode"] = {"mode": mode, "full": full_summary,
                            "note": "core = 레버 필요성의 '핵심 + 처리능력 기여' 레버만 공식 계산에 포함, 나머지는 1년차 실측 후 편입 후보(로드맵에 표시)."
                            if mode == "core" else "full = 후보 정의의 전체 레버(근거 없는 레버는 0으로 계산)."}
    out_ = {**mods, "candidates": run["candidates"], "skipped": run["skipped"], "selected": sel, "status": run["status"], "boundaries": bnd,
            "heat": heat_sensitivity(values, clean),
            "stages": stage_progress(values, clean, eff, sel_c) if sel_c else None,
            "reverse_models": reverse_models(values, next((c for c in run["candidates"] if c["id"] == "A"), None)),
            "priority": pri, "switch": switch, "space_short": run["space_short"],
            "detection": detection_table(), "n_for_1pct": n_for_miss_rate(0.01),
            "baseline": {"E_now": 100.0, "E_q_no_change": sum(_B(values)), "target": 100.0 * values["q"] * values["target_intensity_ratio"]},
            "note": ("모든 후보는 같은 기준선(현재 공장 100 pt, 12 GWh 무개선 ΣB pt)·같은 단가·같은 열원 가정으로 계산. "
                     "고형분 효과는 문헌 절감률이 아니라 질량수지 × 용매 비례 부하 비중 φ(가정 범위)로 계산하고, "
                     "다른 건조 레버는 그 '남은 부하'에만 적용한다. CAPEX 견적이 없어 허용 투자비(할인 없는 역산 상한)만 표시.")}
    if not values.get("_skip_design"):
        try:
            import design   # v12.2 설계 고정 비교 · 두 목표 신호등 · 금액 카드 (판정 미반영 표)
            out_["design"] = design.analyze(values, out_, clean)
        except Exception as e:  # noqa: BLE001
            out_["design"] = {"error": f"계산 보류: {type(e).__name__}: {e}"}
    return out_


def switch_conditions(run, bnd):
    """추천 전환 조건 - 계산 결과에서 만든 문장."""
    c = {x["id"]: x for x in run["candidates"]}
    sel = run["selected"]
    out = []
    if sel and sel.startswith("B") and "A" in c:
        sb = next((b for b in bnd if b["kind"] == "고형분(건조 처리능력)"), None)
        fb = "B0" if sel != "B0" and "B0" in c and "DRY-HSC" in c[sel]["levers"] else "A"
        dw = " - 건조 처리능력은 D등급 근거에서만 성립" if fb == "B0" else ""
        out.append(f"{sel} → {fb}: 목표 고형분에서 배합·건조 품질이 불합격이면 {fb}로 전환{dw}. {fb}는 현재 "
                   f"{c[fb]['label']} (대표 {c[fb]['saving'][1] * 100:.1f}%)"
                   + (f" → {c[fb]['shortfall']['text']}" if c[fb].get("shortfall") else ""))
        if sb:
            out.append(f"{sel} 유지 조건: 고형분 ≥ {sb['value'] * 100:.2f}% (건조 처리능력) 그리고 품질 관문 통과")
        cc = next((x for x in run["candidates"] if x.get("precondition") == "space_insufficient"), None)
        if cc:
            need = next(a["required_slot_gain"] for a in c[sel]["axes"] if a["axis"].startswith("에이징"))
            out.append(f"{sel} → C: 승인 슬롯이 +{need * 100:.2f}% 미만이면 C 검토. C는 단축 검출력 검증 전 양산 승인 불가 "
                       f"(C 현재: {cc['label']})")
    elif sel == "A":
        out.append("A 유지: 가장 작은 변경으로 모든 수치 축을 넘음. 품질 관문 통과 후 확정")
    elif sel:
        out.append(f"{sel}: 승인 공간 부족으로 선택된 대안 - 단축 검출력 검증이 끝나기 전 양산 적용 불가")
    for b in bnd:
        if b["kind"] in ("문헌 효과 전이율", "추가 관리 전력", "화성 추가 채널 점유"):
            out.append(b["text"])
    return out
