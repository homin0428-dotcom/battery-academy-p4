"""근거 FMEA 데이터셋 기반 자동 판정 엔진.

입력 : data/kb/*.csv (sources, levers, effects, fmea) + 시나리오 값(core.resolve_inputs 결과)
출력 : 문헌 수치를 명시된 환산·결합 가정으로 비교한 계통별 절감률 범위, 관리 부담, 3개 경우(보수·대표·낙관)의 목표 판정,
       부족분 역산과 대안 레버, v10 가정 검증, 레버별 판정표, 수치 → 근거 추적표

원칙
  * 사람이 정한 절감률(r)을 쓰지 않는다. 근거 행에서만 범위를 만든다.
  * 측정 범위(경계)가 다른 수치는 환산 규칙으로만 바꾸고, 환산할 수 없으면 '참고 전용'으로 계산에서 뺀다.
  * 같은 중복 방지 그룹의 레버는 곱하지 않는다 (가장 큰 단일 레버 값만).
  * 점수·확률을 만들지 않는다. 근거 등급·확인 상태·적용 조건 일치는 범주로만 보고한다.
  * 몬테카를로·최적화를 쓰지 않는다. 범위의 끝값(보수·낙관)과 대표값만 결정적으로 전파한다.
"""
from __future__ import annotations

import csv
import math
import re
import statistics
from pathlib import Path

import kb_schema as S

KB_DIR = Path(__file__).resolve().parent / "data" / "kb"
SYS_IDX = {s: i for i, s in enumerate(S.SYSTEMS)}

# 사용 상태
USE_CALC, USE_REF, USE_EXCL = "계산 사용", "참고 전용", "제외"
CASES = ("conservative", "typical", "optimistic")
CASE_KO = {"conservative": "보수", "typical": "대표", "optimistic": "낙관"}


class KBError(ValueError):
    """데이터셋 구조 오류 (계산 불가)."""


# ================================================================== 읽기·검증
def load_kb(kb_dir=None):
    d = Path(kb_dir or KB_DIR)
    kb = {}
    for sheet in S.SHEETS:
        p = d / f"{sheet}.csv"
        if not p.exists():
            raise KBError(f"데이터셋 파일 없음: {p.name}")
        with open(p, encoding="utf-8-sig", newline="") as fh:
            kb[sheet] = [dict(r) for r in csv.DictReader(fh)]
    return kb


def _blank(v):
    return v is None or (isinstance(v, str) and v.strip() == "") or (isinstance(v, float) and math.isnan(v))


def _num(v, issues, ctx, field):
    if _blank(v):
        return None
    try:
        x = float(str(v).replace(",", "").strip())
    except ValueError:
        issues.append({**ctx, "field": field, "level": "error", "msg": f"숫자가 아님: {v!r}"})
        return None
    if not math.isfinite(x):
        issues.append({**ctx, "field": field, "level": "error", "msg": "유한한 숫자가 아님"})
        return None
    return x


def validate_kb(kb):
    """필수값·범주·단위·범위·ID 연결을 검사하고 정규화된 데이터셋을 만든다.

    반환: (clean, issues). error 행은 clean에서 빠진다. 'EX-'로 시작하는 예시 행은 무시한다.
    """
    issues, clean = [], {k: [] for k in S.SHEETS}
    seen = {k: set() for k in S.SHEETS}
    doi_seen = {}   # 같은 DOI를 다른 ID로 두 번 등록하면 독립 근거 2건으로 세어지므로 막는다

    def req_ok(sheet, r, ctx):
        ok = True
        for k, ko, req, _d in S.SHEETS[sheet]:
            if req and _blank(r.get(k)):
                issues.append({**ctx, "field": k, "level": "error", "msg": f"필수값 '{ko}' 비어 있음"})
                ok = False
        return ok

    def enum_ok(r, ctx, field, allowed):
        v = str(r.get(field) or "").strip()
        if v and v not in allowed:
            issues.append({**ctx, "field": field, "level": "error", "msg": f"허용되지 않은 값 '{v}' (허용: {', '.join(allowed)})"})
            return False
        return True

    for sheet in ("sources", "levers", "effects", "fmea"):
        idc = S.ID_COL[sheet]
        for i, raw in enumerate(kb.get(sheet, []), 1):
            r = {k: (str(v).strip() if isinstance(v, str) else v) for k, v in raw.items()}
            rid = str(r.get(idc) or "").strip()
            if rid.startswith("EX-"):
                continue
            if all(_blank(v) for v in r.values()):
                continue
            ctx = {"sheet": sheet, "row": i, "id": rid or f"(행 {i})"}
            if not req_ok(sheet, r, ctx):
                continue
            if rid in seen[sheet]:
                issues.append({**ctx, "field": idc, "level": "error", "msg": f"ID 중복: {rid}"})
                continue
            seen[sheet].add(rid)
            ok = True
            if sheet == "sources":
                ok &= enum_ok(r, ctx, "source_type", S.SOURCE_TYPES) & enum_ok(r, ctx, "access", S.ACCESS)
                doi = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", str(r.get("doi") or "").strip().lower()).strip()
                if doi:
                    if doi in doi_seen:
                        issues.append({**ctx, "field": "doi", "level": "error",
                                       "msg": f"DOI {doi}가 이미 {doi_seen[doi]}로 등록됨 - 새 ID를 만들지 말고 {doi_seen[doi]}를 근거ID로 쓰세요"})
                        ok = False
                    else:
                        doi_seen[doi] = rid
            elif sheet == "levers":
                ok &= enum_ok(r, ctx, "system", S.SYSTEMS) & enum_ok(r, ctx, "horizon", ["3년내", "장기"])
                ok &= enum_ok(r, ctx, "change_type", list(S.CHANGE_TYPES))
                r["horizon"] = r.get("horizon") or "3년내"
                r["covers_list"] = [x.strip() for x in str(r.get("covers") or "").split(";") if x.strip()]
            else:
                ok &= enum_ok(r, ctx, "evidence_grade", list(S.EVIDENCE_GRADES))
                ok &= enum_ok(r, ctx, "verification", list(S.VERIFICATION))
            if sheet == "effects":
                ok &= enum_ok(r, ctx, "chemistry", S.CHEMISTRY) & enum_ok(r, ctx, "cell_format", S.CELL_FORMAT)
                ok &= enum_ok(r, ctx, "scale", S.SCALE) & enum_ok(r, ctx, "boundary", list(S.BOUNDARY))
                ok &= enum_ok(r, ctx, "metric", list(S.METRICS)) & enum_ok(r, ctx, "energy_carrier", list(S.ENERGY_CARRIER))
                r["energy_carrier"] = r.get("energy_carrier") or "미기재"
                if ok:
                    ok = _normalize_effect(r, ctx, issues)
            if sheet == "fmea":
                ok &= enum_ok(r, ctx, "burden_metric", list(S.BURDEN_METRICS))
                aff = [x.strip() for x in str(r.get("affected") or "").split(";") if x.strip()]
                bad = [a for a in aff if a not in S.AFFECTED]
                if bad:
                    issues.append({**ctx, "field": "affected", "level": "error", "msg": f"영향범주 오류 {bad}"})
                    ok = False
                r["affected_list"] = aff
                if ok:
                    ok = _normalize_burden(r, ctx, issues)
            if ok:
                clean[sheet].append(r)

    # ID 연결 검사
    lever_ids = {l["lever_id"] for l in clean["levers"]}
    src_ids = {s["source_id"] for s in clean["sources"]}
    for l in clean["levers"]:
        for c in l["covers_list"]:
            if c not in lever_ids:
                issues.append({"sheet": "levers", "row": None, "id": l["lever_id"], "field": "covers", "level": "error",
                               "msg": f"포함레버 '{c}'가 레버 목록에 없음"})
    for sheet in ("effects", "fmea"):
        keep = []
        for r in clean[sheet]:
            ctx = {"sheet": sheet, "row": None, "id": r[S.ID_COL[sheet]]}
            bad = False
            if r["lever_id"] not in lever_ids:
                issues.append({**ctx, "field": "lever_id", "level": "error", "msg": f"레버ID '{r['lever_id']}' 없음"})
                bad = True
            if r["source_id"] not in src_ids:
                issues.append({**ctx, "field": "source_id", "level": "error", "msg": f"근거ID '{r['source_id']}' 없음"})
                bad = True
            if not bad:
                keep.append(r)
        clean[sheet] = keep
    return clean, issues


def _normalize_effect(r, ctx, issues):
    m = S.METRICS[r["metric"]]
    unit = str(r.get("unit") or "").strip()
    if unit not in m["units"]:
        issues.append({**ctx, "field": "unit", "level": "error",
                       "msg": f"지표 {r['metric']}에 단위 '{unit}' 불가 (허용: {', '.join(m['units'])})"})
        return False
    f = m["units"][unit]
    flags = []
    if m["kind"] == "pair":
        b = _num(r.get("value_before"), issues, ctx, "value_before")
        a = _num(r.get("value_after"), issues, ctx, "value_after")
        if b is None or a is None:
            issues.append({**ctx, "field": "value_before", "level": "error", "msg": "개선전값·개선후값 둘 다 필요"})
            return False
        if b <= 0 or a < 0:
            issues.append({**ctx, "field": "value_before", "level": "error", "msg": "개선전값은 양수, 개선후값은 0 이상이어야 함"})
            return False
        if m["derives"] == "system_saving_ratio":
            v = 1.0 - a / b
        else:
            v = (a * f) / (b * f)
        r["metric_eff"] = m["derives"]
        lo = typ = hi = v
        flags.append("전·후 값에서 계산")
    else:
        vals = {k: _num(r.get(k), issues, ctx, k) for k in ("value_low", "value_typ", "value_high")}
        given = {k: v * f for k, v in vals.items() if v is not None}
        if not given:
            issues.append({**ctx, "field": "value_typ", "level": "error", "msg": "최솟값·대표값·최댓값 중 하나 이상 필요"})
            return False
        lo = given.get("value_low", given.get("value_typ", given.get("value_high")))
        hi = given.get("value_high", given.get("value_typ", given.get("value_low")))
        typ = given.get("value_typ", (lo + hi) / 2)
        if len(given) == 1:
            flags.append({"value_low": "하한값만", "value_high": "상한값만", "value_typ": "단일값"}[next(iter(given))])
        if not (lo <= typ + 1e-12 and typ <= hi + 1e-12):
            issues.append({**ctx, "field": "value_typ", "level": "error", "msg": f"최솟값 ≤ 대표값 ≤ 최댓값이 아님 ({lo}, {typ}, {hi})"})
            return False
        r["metric_eff"] = r["metric"]
    me = S.METRICS[r["metric_eff"]]
    for name, v in (("lo", lo), ("hi", hi)):
        if v < me.get("lo", -math.inf) - 1e-12 or v > me.get("hi", math.inf) + 1e-12:
            issues.append({**ctx, "field": "value", "level": "error",
                           "msg": f"{me['ko']} 값 {v:.4g}가 허용 범위 [{me.get('lo')}, {me.get('hi')}] 밖 (단위 확인)"})
            return False
    share = _num(r.get("boundary_share"), issues, ctx, "boundary_share")
    if share is not None and not 0 < share <= 1:
        issues.append({**ctx, "field": "boundary_share", "level": "error", "msg": "경계비중은 0 초과 1 이하"})
        return False
    me_ = _num(r.get("machine_elec_change"), issues, ctx, "machine_elec_change")
    mh_ = _num(r.get("machine_heat_change"), issues, ctx, "machine_heat_change")
    for nm, v in (("machine_elec_change", me_), ("machine_heat_change", mh_)):
        if v is not None and v < -1 - 1e-12:
            issues.append({**ctx, "field": nm, "level": "error", "msg": "설비 변화율은 -1(-100%) 미만일 수 없음 (비율로 입력: -65% → -0.65)"})
            return False
    r["lo"], r["typ"], r["hi"], r["share"], r["flags"] = lo, typ, hi, share, flags
    r["elec_change"], r["heat_change"] = me_, mh_
    return True


def _normalize_burden(r, ctx, issues):
    bm = S.BURDEN_METRICS[r["burden_metric"]]
    vals = {k: _num(r.get(k), issues, ctx, k) for k in ("burden_low", "burden_typ", "burden_high")}
    given = {k: v for k, v in vals.items() if v is not None}
    r["b_lo"] = r["b_typ"] = r["b_hi"] = None
    r["quantified"] = False
    if r["burden_metric"] == "none":
        return True
    if not given:
        return True   # 정량 미확인 (관리 부담 있음, 값 없음)
    unit = str(r.get("unit") or "").strip()
    if unit not in bm["units"]:
        issues.append({**ctx, "field": "unit", "level": "error",
                       "msg": f"부담지표 {r['burden_metric']}에 단위 '{unit}' 불가 (허용: {', '.join(u for u in bm['units'] if u)})"})
        return False
    f = bm["units"][unit]
    g = {k: v * f for k, v in given.items()}
    lo = g.get("burden_low", g.get("burden_typ", g.get("burden_high")))
    hi = g.get("burden_high", g.get("burden_typ", g.get("burden_low")))
    typ = g.get("burden_typ", (lo + hi) / 2)
    if lo < bm["lo"] or hi > bm["hi"] or not lo <= typ <= hi:
        issues.append({**ctx, "field": "burden_typ", "level": "error", "msg": f"부담 범위 오류 ({lo}, {typ}, {hi})"})
        return False
    r["b_lo"], r["b_typ"], r["b_hi"], r["quantified"] = lo, typ, hi, True
    return True


# ================================================================== 적용 조건·경계 환산
def applicability(r, target=None):
    """대상 공장 조건과의 일치. 반환 (transfer, reasons). 양극계가 다르면 제외."""
    t = target or S.TARGET_CONTEXT
    reasons = []
    ch = r.get("chemistry", "무관")
    if ch not in ("무관", t["chemistry"]):
        if ch in S.CHEMISTRY_SIMILAR.get(t["chemistry"], set()):
            reasons.append(f"양극계 유사({ch})")
        else:
            return "제외", [f"양극계 불일치({ch})"]
    fmt = r.get("cell_format", "무관")
    if fmt not in ("무관", t["cell_format"]):
        reasons.append(f"셀형태 상이({fmt})")
    sc = r.get("scale", "무관")
    if sc not in ("무관", t["scale"]):
        reasons.append(f"규모 상이({sc})")
    return ("직접" if not reasons else "조건부"), reasons


def share_evidence(clean, system):
    """KB의 계통 비중 근거 (공장전체 기준 절감률 환산용). 반환 (lo, typ, hi, ids) 또는 None."""
    rows = []
    for r in clean["effects"]:
        if r["metric_eff"] != "energy_share" or _lever(clean, r["lever_id"])["system"] != system:
            continue
        if r["verification"] == "미확인" or applicability(r)[0] == "제외":
            continue
        rows.append(r)
    if not rows:
        return None
    return (min(r["lo"] for r in rows), statistics.median(r["typ"] for r in rows), max(r["hi"] for r in rows),
            [r["effect_id"] for r in rows], sorted({r.get("energy_carrier", "미기재") for r in rows}))


def _lever(clean, lid):
    for l in clean["levers"]:
        if l["lever_id"] == lid:
            return l
    raise KBError(f"레버 없음: {lid}")


def to_system_basis(r, clean, w_share, allow_cross_share=False):
    """절감률 행을 '해당 계통 전체 대비'로 환산. 반환 dict(use, lo, typ, hi, how, flags)."""
    sys_ = _lever(clean, r["lever_id"])["system"]
    b = r["boundary"]
    flags = list(r["flags"])
    if b == "계통전체":
        return dict(use=USE_CALC, lo=r["lo"], typ=r["typ"], hi=r["hi"], how="계통 전체 기준(환산 없음)", flags=flags)
    if b == "공장전체":
        if r["share"] is not None:
            sl = st = sh = r["share"]
            how = f"같은 문헌의 계통 비중 {r['share']:.3f}로 나눔(경계비중 열)"
        else:
            ev = share_evidence(clean, sys_)
            if ev:
                sl, st, sh, ids, carriers = ev
                rng = f"{sl:.2f}" if abs(sh - sl) < 1e-12 else f"{sl:.2f}~{sh:.2f}"
                how = f"KB 계통 비중 근거 {rng}({', '.join(ids)})로 나눔 - 다른 문헌 비중 사용(조건부)"
                flags.append("타 문헌 비중 환산")
                if "1차에너지" in carriers:
                    flags.append("1차에너지 기준 비중 포함")
            else:
                sl = st = sh = w_share
                how = f"근거 비중 없음 → 과제 비중 {w_share:.2f}로 나눔(가정)"
                flags.append("과제 비중 환산(가정)")
        lo, typ, hi = r["lo"] / sh, r["typ"] / st, r["hi"] / sl
        if "타 문헌 비중 환산" in flags and not allow_cross_share:
            # 다른 연구의 계통 비중으로 나눈 값은 별도 가정 시나리오에서만 쓴다 (본 판정은 같은 문헌 비중·과제 비중만)
            return dict(use=USE_REF, lo=lo, typ=typ, hi=min(hi, 1.0), flags=flags,
                        how=how + " → 본 판정 제외(참고). 원문 계통 비중을 경계비중에 넣으면 계산에 사용")
        if typ > 1 + 1e-9:
            return dict(use=USE_EXCL, lo=lo, typ=typ, hi=hi, how=how,
                        flags=flags + [f"환산값 {typ:.0%} > 100% - 원문 계통 비중 필요"])
        if hi > 1:
            hi = 1.0
            flags.append("환산 상한 100%로 제한")
        return dict(use=USE_CALC, lo=lo, typ=typ, hi=hi, how=how, flags=flags)
    if b == "계통일부":
        if r["share"] is not None:
            s = r["share"]
            return dict(use=USE_CALC, lo=r["lo"] * s, typ=r["typ"] * s, hi=r["hi"] * s,
                        how=f"계통 중 해당 부분 비중 {s:.2f}를 곱함", flags=flags)
        return dict(use=USE_REF, lo=r["lo"], typ=r["typ"], hi=r["hi"],
                    how="계통 일부 기준 - 부분 비중 없어 환산 불가", flags=flags)
    return dict(use=USE_REF, lo=r["lo"], typ=r["typ"], hi=r["hi"],
                how=f"{b} 기준 - 계통 절감률로 환산 불가", flags=flags)


# v10은 모든 계통을 '전력 비중'으로 다루고 모드 A도 전기저항 가열(효율 1)을 가정한다 → 기본값: 가열은 전기식.
# 드라이룸 제습 재생을 가스로 하는 공장이면 {"드라이룸": False}로 바꾸면 열·합산 근거가 참고 전용으로 빠진다.
DEFAULT_ELECTRIC_HEATING = {s: True for s in S.SYSTEMS}


def _apply_carrier(row, r, sys_, eh):
    """목표는 전력 원단위 - 열·합산·1차에너지 수치를 그대로 전력 절감으로 쓰지 않는다."""
    c = r.get("energy_carrier", "미기재")
    row["energy_carrier"] = c
    if row["use"] != USE_CALC or c == "전력":
        return
    if c in ("열", "합산"):
        if eh.get(sys_, False):
            row["flags"].append(f"{c} 기준 수치 - {sys_} 가열을 전기식으로 가정해 전력 절감으로 인정")
            if row["transfer"] == "직접":
                row["transfer"] = "조건부"
            row["transfer_reasons"] = row["transfer_reasons"] + [f"에너지 종류 {c}"]
        elif r.get("elec_change") is not None:
            # 가열이 가스·스팀: 합산 절감률 대신 설비 '전기' 변화율로 계통 전력 효과를 계산 (전기 증가면 음의 절감)
            e = r["elec_change"]
            row.update(lo=-e, typ=-e, hi=-e)
            row["how"] += (f" / {sys_} 가열이 가스·스팀 → 합산 절감률 대신 설비 전기 변화율 {e * 100:+.0f}%로 계통 전력 효과 계산"
                           f"(계통 전력 절감 {-e * 100:+.0f}%)")
            row["flags"].append("전기·열 분리 계산(설비 단위 변화율을 계통 전력에 적용한 근사)")
            if row["transfer"] == "직접":
                row["transfer"] = "조건부"
            row["transfer_reasons"] = row["transfer_reasons"] + ["가스·스팀 가열 - 설비 전기 변화율 사용"]
        else:
            row["use"] = USE_REF
            row["how"] += f" / {sys_} 가열이 전기식이 아님 → {c} 수치를 전력 절감으로 환산 불가(설비 전기 변화율 없음)"
    elif c == "1차에너지":
        row["use"] = USE_REF
        row["how"] += " / 1차에너지 기준 → 전력 절감률로 쓰지 않음"
    else:   # 미기재·무관
        row["flags"].append("에너지 종류 미기재")
        if row["transfer"] == "직접":
            row["transfer"] = "조건부"


def plant_basis(clean, values):
    """전력 절대 증감(kWh/kWh_cell)을 계통 절감률로 바꾸는 데 필요한 값: 공장 전력 원단위 범위, q, 계통별 B."""
    rows = [r for r in clean["effects"] if r["metric_eff"] == "plant_electricity_intensity"
            and r.get("energy_carrier") == "전력" and r["verification"] != "미확인"]
    if not rows:
        return None
    q = values["q"]
    B = [wi * (fi + (1 - fi) * q) for wi, fi in zip(values["w"], values["f"])]
    return {"I_lo": min(r["lo"] for r in rows), "I_hi": max(r["hi"] for r in rows), "q": q, "B": B,
            "ids": [r["effect_id"] for r in rows]}


def classify_effects(clean, w, electric_heating=None, allow_cross_share=False, plant=None):
    """모든 정량효과 행에 사용 상태·적용 조건·계통 기준 값을 붙인다.

    plant: plant_basis() 결과. 가스·스팀 가열 시나리오에서 전력 절대 증감(electricity_delta_abs) 행을 환산할 때 쓴다.
    """
    eh = {**DEFAULT_ELECTRIC_HEATING, **(electric_heating or {})}
    out = []
    for r in clean["effects"]:
        lev = _lever(clean, r["lever_id"])
        sys_ = lev["system"]
        transfer, reasons = applicability(r)
        role = S.METRICS[r["metric_eff"]]["role"]
        row = {"effect_id": r["effect_id"], "lever_id": r["lever_id"], "system": sys_, "metric": r["metric_eff"],
               "role": role, "source_id": r["source_id"], "grade": r["evidence_grade"],
               "verification": r["verification"], "transfer": transfer, "transfer_reasons": reasons,
               "boundary": r["boundary"], "raw": (r["lo"], r["typ"], r["hi"]), "unit_note": r.get("unit"),
               "locator": r.get("locator", ""), "excerpt": r.get("excerpt", "")}
        if transfer == "제외":
            row.update(use=USE_EXCL, lo=None, typ=None, hi=None, how="적용 조건 불일치", flags=reasons)
        elif r["verification"] == "미확인":
            row.update(use=USE_EXCL, lo=None, typ=None, hi=None, how="확인상태 미확인 - 계산 제외", flags=[])
        elif role == "saving" and r["metric_eff"] == "electricity_delta_abs":
            # 절대값(kWh/kWh_cell)을 %로 옮겨 적는 실수 방지: 단위와 기준 대비 비율(조건메모)을 같이 표시
            rel = next((x.strip() for x in str(r.get("conditions_note") or "").split(". ") if "대비" in x), "")
            unit_txt = f" [절대값 {r['typ']:+.3g} kWh/kWh_cell - %가 아님" + (f"; {rel}" if rel else "") + "]"
            if eh.get(sys_, False):
                row.update(use=USE_REF, lo=r["lo"], typ=r["typ"], hi=r["hi"], flags=list(r["flags"]),
                           how=f"가스·스팀 가열 전용 근거 - {sys_} 가열이 전기식인 시나리오에서는 참고" + unit_txt)
            elif plant is None:
                row.update(use=USE_REF, lo=r["lo"], typ=r["typ"], hi=r["hi"], flags=list(r["flags"]),
                           how="공장 전력 원단위 근거가 없어 계통 효과로 환산 불가")
            else:
                j = SYS_IDX[sys_]
                k = 100.0 * plant["q"] / plant["B"][j]     # kWh/kWh_cell → 계통 B_j 대비 비율
                conv = lambda d, I: -d / I * k
                cands = [conv(d, I) for d in (r["lo"], r["hi"]) for I in (plant["I_lo"], plant["I_hi"])]
                row.update(use=USE_CALC, lo=min(cands), hi=max(cands),
                           typ=conv(r["typ"], (plant["I_lo"] + plant["I_hi"]) / 2), flags=list(r["flags"]) + ["가스·스팀 가열 전력 절대값"],
                           how=(f"가스·스팀 가열: 전력 {r['typ']:+.2f} kWh/kWh_cell ÷ 공장 전력 원단위 {plant['I_lo']:g}~{plant['I_hi']:g}"
                                f"({', '.join(plant['ids'])}) → 공장 전력 {r['typ'] / plant['I_hi'] * 100:+.1f}~{r['typ'] / plant['I_lo'] * 100:+.1f}%" + unit_txt),
                           energy_carrier="전력")
                if row["transfer"] == "직접":
                    row["transfer"] = "조건부"
        elif role == "saving":
            row.update(to_system_basis(r, clean, w[SYS_IDX[sys_]] / 100.0, allow_cross_share))
            _apply_carrier(row, r, sys_, eh)
        elif role == "plant":
            ok = r.get("energy_carrier") == "전력"
            row.update(use=USE_CALC if ok else USE_REF, lo=r["lo"], typ=r["typ"], hi=r["hi"],
                       how="공장 전력 원단위(연간 절감량 환산)" if ok else "전력 기준이 아님 → 연간 전력 환산에 쓰지 않음",
                       flags=list(r["flags"]), energy_carrier=r.get("energy_carrier"))
        elif role == "aging":
            use = USE_CALC if r["boundary"] in ("계통전체",) else USE_REF
            row.update(use=use, lo=r["lo"], typ=r["typ"], hi=r["hi"], how="에이징 기간 비(변경/기존)", flags=list(r["flags"]))
        elif role == "space":
            row.update(use=USE_CALC, lo=r["lo"], typ=r["typ"], hi=r["hi"], how="에이징 슬롯 확보율", flags=list(r["flags"]))
        elif role == "time":
            use = USE_CALC if r["boundary"] in ("계통전체",) else USE_REF
            row.update(use=use, lo=r["lo"], typ=r["typ"], hi=r["hi"], how="화성시간 비(변경/기존)", flags=list(r["flags"]))
        else:   # param, baseline
            row.update(use=USE_REF, lo=r["lo"], typ=r["typ"], hi=r["hi"],
                       how="파라미터·비중 근거(검증·환산용)", flags=list(r["flags"]))
        out.append(row)
    # 가스·스팀 가열 계통: 같은 레버에 '전력 절대 증감' 근거가 있으면 '설비 전기 변화율 × 계통 전력' 근사는 참고로 내린다
    # (비율을 C사 계통 전력에 곱하면 '가스 가열인데 그 계통이 공장 전력의 35%'라는 모순된 전제를 쓰게 됨)
    abs_levers = {e["lever_id"] for e in out if e["metric"] == "electricity_delta_abs" and e["use"] == USE_CALC}
    for e in out:
        if e["lever_id"] in abs_levers and e["use"] == USE_CALC and any("전기·열 분리" in f for f in e["flags"]):
            e["use"] = USE_REF
            e["how"] += " → 같은 레버에 전력 절대 증감 근거가 있어 그 값을 우선(이 행은 참고)"
    return out


def apply_effect_selection(eff, selection):
    """kb_effect_selection = {lever_id: [effect_id, ...]}: 팀이 실제로 고른 기술 구성의 근거만 계산에 쓴다.

    지정된 레버의 다른 계산 행은 '참고 전용'으로 내린다. 지정이 없으면 그대로(전체 근거의 중앙값).
    """
    if not selection:
        return eff
    out = []
    for e in eff:
        keep = selection.get(e["lever_id"])
        if keep and e["use"] == USE_CALC and e["effect_id"] not in keep:
            e = {**e, "use": USE_REF, "how": e["how"] + " [기술 선택(kb_effect_selection)에서 제외]"}
        out.append(e)
    return out


def selection_summary(eff_all, eff_sel, selection):
    rows = []
    for lid in (selection or {}):
        a, b = lever_saving(eff_all, lid), lever_saving(eff_sel, lid)
        rows.append({"lever_id": lid, "selected_ids": selection[lid], "all_typ": a and a["typ"], "selected_typ": b and b["typ"],
                     "all_ids": a and a["ids"]})
    return rows


# ================================================================== 레버·계통 집계
def lever_saving(effects_cls, lid):
    rows = [e for e in effects_cls if e["lever_id"] == lid and e["role"] == "saving" and e["use"] == USE_CALC]
    if not rows:
        return None
    return {"lo": min(e["lo"] for e in rows), "typ": statistics.median(e["typ"] for e in rows),
            "hi": max(e["hi"] for e in rows), "ids": [e["effect_id"] for e in rows],
            "best_grade": min((e["grade"] for e in rows), key=S.GRADE_ORDER.index),
            "conditional": any(e["transfer"] == "조건부" or e["flags"] for e in rows), "n": len(rows),
            "sources": sorted({e["source_id"] for e in rows})}


def effective_levers(clean, selected):
    """패키지 레버가 포함하는 레버는 따로 세지 않는다."""
    sel = [l for l in selected if l]
    covered = set()
    for lid in sel:
        covered |= set(_lever(clean, lid)["covers_list"])
    return [l for l in sel if l not in covered], sorted(covered & set(sel))


def system_ranges(clean, effects_cls, selected, kappa=1.0):
    """선택 레버로 계통별 절감률 범위(보수·대표·낙관)를 만든다.

    kappa(결합 이득 유지율): 한 계통 안에서 서로 다른 그룹의 레버를 함께 쓸 때, 독립 곱셈이 주는 '추가 이득'
    중 실제로 남는 비율. 1 = 독립 결합(기본), 0 = 가장 큰 레버 하나의 효과만. 근거가 확인되기 전까지는 민감도 변수.
    """
    eff_levers, dropped = effective_levers(clean, selected)
    out = {}
    for s in S.SYSTEMS:
        levs = [l for l in eff_levers if _lever(clean, l)["system"] == s and _lever(clean, l)["exclusive_group"] != "BASE"]
        groups, no_ev, trace = {}, [], []
        for lid in levs:
            ls = lever_saving(effects_cls, lid)
            if ls is None:
                no_ev.append(lid)
                continue
            g = _lever(clean, lid)["exclusive_group"]
            groups.setdefault(g, []).append((lid, ls))
            trace.extend(ls["ids"])
        vals = {}
        for k in ("lo", "typ", "hi"):
            prod = 1.0
            best = 0.0
            for g, items in groups.items():
                gm = max(ls[k] for _l, ls in items)   # 같은 그룹은 곱하지 않음
                prod *= 1.0 - gm
                best = max(best, gm)
            indep = 1.0 - prod
            vals[k] = best + kappa * (indep - best) if len(groups) > 1 else indep
        group_note = [f"{g}: {', '.join(l for l, _ in items)}" + (" (곱하지 않고 최대값)" if len(items) > 1 else "")
                      for g, items in groups.items()]
        out[s] = {"levers": levs, "no_evidence": no_ev, "groups": group_note, "trace": trace, "n_groups": len(groups),
                  "lo": vals["lo"], "typ": vals["typ"], "hi": vals["hi"],
                  "status": ("변경 없음" if not levs else "근거 없음" if not groups else
                             "일부 레버 근거 없음" if no_ev else "근거 있음")}
    return out, dropped


def burdens(clean, selected, B):
    """선택 레버의 FMEA 관리 부담 집계. added_power_ratio는 해당 계통 증산 후 전력 B_j 기준 → pt."""
    eff_levers, _ = effective_levers(clean, selected)
    occ = {"lo": 0.0, "typ": 0.0, "hi": 0.0}
    padd = {"lo": 0.0, "typ": 0.0, "hi": 0.0}
    ch = {"lo": 0.0, "typ": 0.0, "hi": 0.0}
    age = {"lo": 0.0, "typ": 0.0, "hi": 0.0}   # 추가 에이징 보관일수 (화성 채널 점유와 구분)
    pending, gates, used = [], [], []
    for r in clean["fmea"]:
        if r["lever_id"] not in eff_levers:
            continue
        if r.get("quality_gate"):
            gates.append({"fmea_id": r["fmea_id"], "lever_id": r["lever_id"], "gate": r["quality_gate"],
                          "failure_mode": r["failure_mode"], "grade": r["evidence_grade"]})
        if r["burden_metric"] == "none":
            continue
        if not r["quantified"]:
            pending.append({"fmea_id": r["fmea_id"], "lever_id": r["lever_id"], "metric": r["burden_metric"],
                            "failure_mode": r["failure_mode"]})
            continue
        used.append(r["fmea_id"])
        if r["burden_metric"] == "added_occupancy_h":
            tgt, mult = occ, 1.0
        elif r["burden_metric"] == "added_power_ratio":
            tgt, mult = padd, B[SYS_IDX[_lever(clean, r["lever_id"])["system"]]]
        elif r["burden_metric"] == "added_aging_days":
            tgt, mult = age, 1.0
        else:
            tgt, mult = ch, 1.0
        tgt["lo"] += r["b_lo"] * mult
        tgt["typ"] += r["b_typ"] * mult
        tgt["hi"] += r["b_hi"] * mult
    return {"occupancy_h": occ, "p_add_pt": padd, "extra_channel": ch, "aging_days": age,
            "pending": pending, "gates": gates, "used": used}


def time_check(effects_cls, values, selected):
    """화성시간 목표(formation_h/baseline)가 근거 범위와 어떤 관계인지."""
    target_ratio = values["formation_h"] / values["baseline_formation_h"]
    rows = [e for e in effects_cls if e["role"] == "time" and e["use"] == USE_CALC]
    if not rows:
        return {"status": "근거 없음", "target_ratio": target_ratio, "ids": []}
    lo, hi = min(e["lo"] for e in rows), max(e["hi"] for e in rows)
    if target_ratio >= hi - 1e-12:
        st = "근거 범위보다 보수적 (단축 폭이 문헌보다 작음)"
    elif target_ratio >= lo:
        st = "근거 범위 안"
    else:
        st = "근거 범위 밖 (문헌보다 더 공격적인 단축)"
    return {"status": st, "target_ratio": target_ratio, "evidence_lo": lo, "evidence_hi": hi,
            "ids": [e["effect_id"] for e in rows],
            "note": "문헌 기준 프로토콜이 길면(예: 56h) 비율이 과대해 보일 수 있음 - 20h 기준 공장에는 조건부",
            "selected": "FOR-FAST" in selected}


# ================================================================== 판정
def evaluate(values, kb=None, selected=None, kb_dir=None):
    """근거만으로 자동 판정. values는 core.resolve_inputs 결과(dict)."""
    import core   # 순환 import 방지: 계산식은 core만 사용

    raw = kb if kb is not None else load_kb(kb_dir)
    clean, issues = validate_kb(raw)
    errors = [i for i in issues if i["level"] == "error"]
    if selected is None:
        selected = values.get("kb_selected_levers") or [l["lever_id"] for l in clean["levers"]
                                                        if l.get("v10_adopted") == "예"]
    unknown = [l for l in selected if l not in {x["lever_id"] for x in clean["levers"]}]
    if unknown:
        raise KBError(f"선택 레버가 데이터셋에 없음: {unknown}")
    w, f, q = values["w"], values["f"], values["q"]
    B = [wi * (fi + (1 - fi) * q) for wi, fi in zip(w, f)]
    eh = {**DEFAULT_ELECTRIC_HEATING, **(values.get("kb_electric_heating") or {})}
    eff_all = classify_effects(clean, w, eh, bool(values.get("kb_allow_cross_share")), plant_basis(clean, values))
    eff = apply_effect_selection(eff_all, values.get("kb_effect_selection"))
    sysr, dropped, bur, cases = _run_cases(clean, eff, selected, values, B)
    verdict = _verdict(cases)
    pend = bur["pending"]
    occ_pending = [p for p in pend if p["metric"] == "added_occupancy_h"]
    for c in cases.values():
        c["capacity_upper_bound"] = bool(occ_pending)
    headroom = -cases["typical"]["gap"]   # 대표 경우 목표 여유(pt). 음수면 부족
    holds = []
    if pend:
        holds.append(f"관리 부담 미정량 {len(pend)}건({', '.join(p['fmea_id'] for p in pend)}) - 결과는 부담 하한 기준")
    no_ev = [l for s in S.SYSTEMS for l in sysr[s]["no_evidence"]]
    if no_ev:
        holds.append(f"선택 레버 중 계산 가능한 근거 없음 {len(no_ev)}건({', '.join(no_ev)}) - 절감 0으로 계산")

    # 부족분 역산 (대표 경우, 다른 계통 고정) + 근거 상한 비교 + 대안 레버
    pt = cases["typical"]["plant"]
    reverse = []
    for j, s in enumerate(S.SYSTEMS):
        others = sum(pt["E"]) - pt["E"][j]
        req = core.required_reduction(others, pt["P_add"], pt["target_energy"], pt["B"][j])
        hi_sel = sysr[s]["hi"]
        alts = []
        for l in clean["levers"]:
            if l["system"] != s or l["exclusive_group"] == "BASE" or l["lever_id"] in selected:
                continue
            ls = lever_saving(eff, l["lever_id"])
            if ls and req is not None and ls["hi"] >= req - 1e-12:
                alts.append({"lever_id": l["lever_id"], "name": l["name_ko"], "hi": ls["hi"], "typ": ls["typ"],
                             "best_grade": ls["best_grade"], "ids": ls["ids"], "horizon": l["horizon"]})
        if req is None:
            st = "역산 불가(B=0)"
        elif req <= sysr[s]["typ"] + 1e-12:
            st = "현재 근거 대표값으로 충분"
        elif req > 1:
            st = "단독 보완 불가(요구 >100%)"
        elif req <= hi_sel + 1e-12:
            st = "선택 레버 근거 상한 안"
        else:
            st = "선택 레버 근거 상한 초과"
        reverse.append({"system": s, "required": req, "selected_typ": sysr[s]["typ"], "selected_hi": hi_sel,
                        "status": st, "alternatives": sorted(alts, key=lambda a: -a["typ"])})

    # v10 가정 검증
    v10 = []
    for j, s in enumerate(S.SYSTEMS):
        a = values["r"][j]
        sr = sysr[s]
        if sr["status"] in ("변경 없음",) and a == 0:
            st = "변경 없음(가정 0)"
        elif sr["status"] == "근거 없음":
            st = "근거 없음" if a > 0 else "변경 없음(가정 0)"
        elif a > sr["hi"] + 1e-12:
            st = "근거 상한 초과"
        elif a < sr["lo"] - 1e-12:
            st = "근거 하한 미만(보수적)"
        else:
            st = "근거 범위 안"
        v10.append({"system": s, "v10_r": a, "lo": sr["lo"], "typ": sr["typ"], "hi": sr["hi"], "status": st})

    levers = lever_table(clean, eff, selected, bur)
    combos = search_additions(clean, eff, selected, values, B)
    best = next((x for x in combos["results"] if x["verdict"] != "근거상 미달"), None)
    rec = list(selected) + (best["add"] if best else [])
    # 증산(에이징) 축이 막히면, 계산 가능한 에이징 근거가 있는 미선택 레버를 하나씩 더해 본다
    prod_add = []
    base_prod = assess(clean, eff, rec, values, B)["production"]
    if not base_prod["aging_status"].startswith(("근거상", "추가")):
        rank = lambda st: 0 if st.startswith(("근거상", "추가")) else 1 if st.startswith("조건부") else 2
        cands = []
        for l in clean["levers"]:
            lid = l["lever_id"]
            if l["system"] != "에이징" or lid in rec or l["exclusive_group"] == "BASE":
                continue
            if not any(e["lever_id"] == lid and e["role"] in ("aging", "space") and e["use"] == USE_CALC for e in eff):
                continue
            pa = assess(clean, eff, rec + [lid], values, B)["production"]
            if rank(pa["aging_status"]) < rank(base_prod["aging_status"]):
                cands.append((rank(pa["aging_status"]), lid))
        if cands:
            prod_add = [sorted(cands)[0][1]]
            rec = rec + prod_add
    production = production_check(clean, eff, selected, values, cases)
    options = compare_options(clean, eff, selected, values, B, combos)
    rec_assess = assess(clean, eff, rec, values, B)
    sel_assess = assess(clean, eff, selected, values, B)
    sensitivity = combination_sensitivity(clean, eff, rec, values, B)
    import candidates   # A/B/C 동일 기준 비교 · 실패 경계 · 검증 우선순위
    cand = candidates.evaluate(values, clean, eff)
    return {
        "candidates": cand,
        "effect_selection": selection_summary(eff_all, eff, values.get("kb_effect_selection")),
        "verdict": verdict, "holds": holds, "headroom_pt": headroom, "cases": cases, "systems": sysr,
        "combos": combos, "production": production, "options": options,
        "overall": rec_assess["overall"], "overall_selected": sel_assess["overall"],
        "production_rec": rec_assess["production"],
        "quality": rec_assess["quality"], "sensitivity": sensitivity,
        "recommended": {"levers": rec, "add": best["add"] if best else [], "production_add": prod_add,
                        "verdict": best["verdict"] if best else verdict},
        "thresholds": flip_thresholds(clean, eff, selected, values, B, best["add"] if best else None, w, eh),
        "roadmap": roadmap(clean, eff, rec, values, B),
        "electric_heating": eh,
        "dropped_by_package": dropped, "burdens": bur, "time": time_check(eff, values, selected),
        "reverse": reverse, "v10_check": v10, "levers": levers, "effects": eff, "selected": list(selected),
        "issues": issues, "n_errors": len(errors),
        "counts": {"sources": len(clean["sources"]), "effects": len(clean["effects"]), "fmea": len(clean["fmea"]),
                   "calc": sum(e["use"] == USE_CALC for e in eff), "ref": sum(e["use"] == USE_REF for e in eff),
                   "excl": sum(e["use"] == USE_EXCL for e in eff),
                   "calc_sources": len({e["source_id"] for e in eff if e["use"] == USE_CALC})},
        "params": param_checks(eff, values),
        "clean": clean,
    }


def _run_cases(clean, eff, selected, values, B, drying_residual=None, scale=1.0, dry_scale=1.0):
    """선택 레버 집합으로 보수·대표·낙관 3개 경우를 계산한다 (계산식은 core만 사용).

    drying_residual: {case: 고형분 변경 후 남는 건조 계통 부하 비율} - 질량수지로 계산한 값(candidates.py).
        문헌 건조 레버 절감은 이 '남은 부하'에만 적용한다: r_건조 = 1 - (1 - r_문헌)·잔여비.
    scale: 문헌 절감 효과 전이율 α (1 = 문헌 대표값 그대로). 실패 경계·검증 우선순위 계산용.
    """
    import core
    w, f, q = values["w"], values["f"], values["q"]
    kappa = values.get("kb_combine_retention")
    kappa = 1.0 if kappa is None else float(kappa)
    extra_p = float(values.get("kb_extra_burden_pt") or 0.0)   # 아직 정량화 안 된 관리 전력(pt) - 민감도용
    extra_occ = float(values.get("kb_extra_occupancy_h") or 0.0)   # 아직 정량화 안 된 화성 추가 점유(h) - 민감도용
    sysr, dropped = system_ranges(clean, eff, selected, kappa)
    bur = burdens(clean, selected, B)
    cases = {}
    di = SYS_IDX["건조"]
    for c, k, bk in (("conservative", "lo", "hi"), ("typical", "typ", "typ"), ("optimistic", "hi", "lo")):
        r = [min(sysr[s][k] * scale, 1.0) for s in S.SYSTEMS]
        r[di] = min(r[di] * dry_scale, 1.0)
        if drying_residual is not None:
            r[di] = 1.0 - (1.0 - r[di]) * drying_residual[c]
        p_add = bur["p_add_pt"][bk] + extra_p
        pl = core.plant_energy(w, f, r, q, p_add, "pt", values["target_intensity_ratio"], q_good=values.get("q_good"))
        occ = bur["occupancy_h"][bk] + extra_occ
        fm = core.formation_capacity(values["formation_h"], occ, values["channel_ratio"], values["availability_ratio"],
                                     values["yield_ratio"], values["baseline_formation_h"], values["target_capacity_ratio"])
        cases[c] = {"r": r, "p_add": p_add, "occupancy_h": occ, "E_total": pl["E_total"], "saving": pl["saving_ratio"],
                    "gap": pl["gap"], "target_energy": pl["target_energy"], "plant_ok": pl["status"] == core.NUM_OK,
                    "capacity": fm["capacity_ratio"], "capacity_ok": fm["status"] == core.NUM_OK, "plant": pl}
    return sysr, dropped, bur, cases


def _verdict(cases):
    if cases["conservative"]["plant_ok"]:
        return "근거상 충족"
    if cases["typical"]["plant_ok"]:
        return "조건부 충족 (대표값 기준)"
    if cases["optimistic"]["plant_ok"]:
        return "근거 상한에서만 충족"
    return "근거상 미달"


MAX_ADD = 2   # 추가 레버 조합 크기 상한 (결정적 열거, 최적화 아님)


def search_additions(clean, eff, selected, values, B, include_long=False):
    """선택 조합에 근거 있는 미선택 레버를 1~2개 더했을 때의 판정을 모두 열거한다.

    최적화·확률 계산이 아니라, 근거가 있는 레버만 대상으로 한 결정적 '만약' 계산이다.
    반환: 목표를 대표값 이상으로 충족하는 조합 목록(추가 레버 수가 적고 보수 절감이 큰 순).
    """
    from itertools import combinations
    cands = []
    for l in clean["levers"]:
        lid = l["lever_id"]
        if lid in selected or l["exclusive_group"] == "BASE":
            continue
        if l["horizon"] == "장기" and not include_long:
            continue
        if lever_saving(eff, lid) is None:
            continue
        cands.append(lid)
    out = []
    for n in range(1, MAX_ADD + 1):
        for add in combinations(cands, n):
            sel = list(selected) + list(add)
            _s, _d, _b, cs = _run_cases(clean, eff, sel, values, B)
            v = _verdict(cs)
            out.append({"add": list(add), "verdict": v, "conservative": cs["conservative"]["saving"],
                        "typical": cs["typical"]["saving"], "optimistic": cs["optimistic"]["saving"],
                        "gap_typical": cs["typical"]["gap"],
                        "names": [_lever(clean, a)["name_ko"] for a in add]})
    rank = {"근거상 충족": 0, "조건부 충족 (대표값 기준)": 1, "근거 상한에서만 충족": 2, "근거상 미달": 3}
    out.sort(key=lambda x: (rank[x["verdict"]], len(x["add"]), -x["conservative"]))
    return {"candidates": cands, "results": out, "n_evaluated": len(out),
            "long_term_excluded": [l["lever_id"] for l in clean["levers"] if l["horizon"] == "장기"
                                   and l["lever_id"] not in selected and not include_long]}


def param_checks(eff, values):
    """파라미터 근거와 시나리오 가정 비교 (예: 모드 A의 COP_h)."""
    out = []
    cop = [e for e in eff if e["metric"] == "cop_h" and e["use"] != USE_EXCL]
    if cop:
        lo, hi = min(e["lo"] for e in cop), max(e["hi"] for e in cop)
        a = values["drying_a"]["cop_h"]
        out.append({"param": "건조 모드 A COP_h", "assumed": a, "lo": lo, "hi": hi,
                    "status": "근거 범위 안" if lo <= a <= hi else "근거 범위 밖", "ids": [e["effect_id"] for e in cop]})
    return out


def lever_table(clean, eff, selected, bur):
    """QFMEA 판정표에 해당하는 레버별 근거 판정 (점수 없이 범주만)."""
    fm_by = {}
    for r in clean["fmea"]:
        fm_by.setdefault(r["lever_id"], []).append(r)
    pend_by = {}
    for p in bur["pending"]:
        pend_by.setdefault(p["lever_id"], []).append(p["fmea_id"])
    rows = []
    for l in clean["levers"]:
        if l["exclusive_group"] == "BASE":
            continue
        lid = l["lever_id"]
        mine = [e for e in eff if e["lever_id"] == lid]
        if not mine and lid not in selected and lid not in fm_by:
            continue
        calc = [e for e in mine if e["role"] in ("saving", "aging", "space") and e["use"] == USE_CALC]
        ref = [e for e in mine if e["use"] == USE_REF]
        ls = lever_saving(eff, lid)
        strong = [e for e in calc if S.GRADE_ORDER.index(e["grade"]) <= S.GRADE_ORDER.index("C")]
        # 같은 논문의 여러 행(예: Degen 표의 NIR·레이저)은 독립 근거 1건으로 센다
        calc_src = sorted({e["source_id"] for e in calc})
        if len(calc_src) >= 2 and strong:
            judge = "근거 충분"
        elif calc:
            judge = "근거 약함"
        elif ref:
            judge = "참고 근거만"
        else:
            judge = "근거 없음"
        todo = []
        n2 = sum(e["verification"] in ("2차 인용", "초록 확인") for e in mine)
        if n2:
            todo.append(f"원문 확인 {n2}건")
        if any(e["boundary"] in ("계통일부",) and e["use"] == USE_REF for e in mine):
            todo.append("부분 경계비중 확보")
        if len(calc) > len(calc_src):
            todo.append(f"정량 {len(calc)}건이 논문 {len(calc_src)}편에서 나옴 - 독립 근거 추가")
        if any("타 문헌 비중" in " ".join(e["flags"]) for e in calc):
            todo.append("원문 계통 비중 확보")
        if any(e["transfer"] == "조건부" for e in calc):
            todo.append("대상 공장 조건 실측")
        if pend_by.get(lid):
            todo.append(f"관리 부담 정량화({', '.join(pend_by[lid])})")
        if judge == "근거 없음":
            todo.append("문헌 탐색 필요")
        rows.append({"lever_id": lid, "name": l["name_ko"], "system": l["system"], "selected": lid in selected,
                     "v10_adopted": l.get("v10_adopted") == "예", "judge": judge,
                     "range": (ls["lo"], ls["typ"], ls["hi"]) if ls else None,
                     "n_calc": len(calc), "n_ref": len(ref), "n_sources": len(calc_src), "sources": calc_src,
                     "best_grade": ls["best_grade"] if ls else (min((e["grade"] for e in mine), key=S.GRADE_ORDER.index) if mine else "-"),
                     "failure_modes": [r["failure_mode"] for r in fm_by.get(lid, [])],
                     "gates": len([r for r in fm_by.get(lid, []) if r.get("quality_gate")]),
                     "pending": pend_by.get(lid, []), "ids": ls["ids"] if ls else [e["effect_id"] for e in ref],
                     "todo": todo})
    order = {"근거 충분": 0, "근거 약함": 1, "참고 근거만": 2, "근거 없음": 3}
    rows.sort(key=lambda x: (not x["selected"], order[x["judge"]], x["system"]))
    return rows


# ================================================================== 결론 문장
def conclusion(ev, scenario_label="근거 기반"):
    """결론은 '추천안'부터: 무엇을 더하고, 전력·증산이 어떻게 되며, 무엇이 바뀌면 추천이 바뀌는지."""
    c = ev["cases"]
    pct = lambda x: f"{x * 100:.1f}%"
    s = []
    ok = [x for x in ev["combos"]["results"] if x["verdict"] != "근거상 미달"]
    prod = ev.get("production", {})
    ov = ev.get("overall")
    if ov:
        s.append(f"[종합] {'추천 조합' if ok else '현재 선택'} 기준 '{ov['label']}' - "
                 + " / ".join(f"{a['axis']} {a['status']}" for a in ov["axes"]) + ".")
    if ok:
        best = ok[0]
        s.append(f"[추천] v10 채택 레버에 '{' + '.join(best['names'])}'를 더하는 조합이 근거상 원단위 절감 대표 {pct(best['typical'])}"
                 f"(보수 {pct(best['conservative'])} ~ 낙관 {pct(best['optimistic'])})로 목표 30%에 '{best['verdict']}'이다.")
    else:
        s.append(f"[추천 없음] 근거 있는 3년 내 레버를 1~2개 더하는 조합 {ev['combos']['n_evaluated']}개 모두 목표에 미달 - "
                 "추가 근거 확보 또는 목표 재검토가 필요하다.")
    s.append(f"v10이 채택한 레버만으로는 근거상 대표 {pct(c['typical']['saving'])}(보수 {pct(c['conservative']['saving'])} ~ "
             f"낙관 {pct(c['optimistic']['saving'])})로 '{ev['verdict']}'이다 (근거 {ev['counts']['sources']}개 자료, 계산 사용 {ev['counts']['calc']}건).")
    gaps = [r for r in ev["v10_check"] if r["status"] in ("근거 없음", "근거 상한 초과")]
    if gaps:
        s.append("v10 가정 중 " + ", ".join(f"{r['system']} {pct(r['v10_r'])}({r['status']})" for r in gaps) + "는 현재 근거로 뒷받침되지 않는다.")
    pr = ev.get("production_rec") or prod
    padd = (ev.get("recommended") or {}).get("production_add") or []
    if pr:
        lead = f"[증산] 추천 조합(+{', '.join(padd)} 포함) " if padd else "[증산] "
        s.append(lead + f"{pr['verdict']}: 화성 처리능력 {'≤' if pr['formation_upper_bound'] else ''}{pr['formation_capacity']:.3f}배, "
                 f"에이징은 {pr['aging_status']} ({pr['note']})"
                 + (f" 현재 선택(v10 레버)만으로는 '{prod['aging_status']}'." if padd and prod else ""))
    sens = ev.get("sensitivity")
    if ok and sens and sens["applies"] and sens["kappa_min_typ"] is not None:
        kt, kc = sens["kappa_min_typ"], sens["kappa_min_cons"]
        head = f"[결합 조건] {', '.join(sens['multi_systems'])} 계통에서 함께 쓰는 레버의 결합 추가 이득(독립 결합 대비)이 "
        typ_txt = ("0%여도(가장 큰 레버 하나만으로도) 대표 기준 충족" if kt <= 1e-9 else f"{kt * 100:.0f}% 이상 유지돼야 대표 기준 충족")
        cons_txt = ("" if kc is None else ", 보수 기준은 결합 없이도 충족" if kc <= 1e-9 else f", 보수 기준은 {kc * 100:.0f}% 이상 필요")
        s.append(head + typ_txt + cons_txt + " - 독립 결합은 확인된 성능이 아니라 가정이다.")
    key = [t for t in ev.get("thresholds", []) if t["kind"] in ("근거 없는 레버의 기준값",) and t["value"] is not None and t["value"] <= 1]
    if key:
        s.append("[추천 전환 조건] " + key[0]["text"] + ".")
    hr = [t for t in ev.get("thresholds", []) if t["kind"] == "관리 부담 허용치"]
    if hr:
        s.append(hr[0]["text"] + ".")
    if ev["holds"]:
        s.append("판정 유보 요소: " + "; ".join(ev["holds"]) + ".")
    s.append("근거 범위는 확보된 성능이 아니며, 원문 확인·대상 공장 실측 전에는 조건부 결과로만 해석한다.")
    return " ".join(s)


# ================================================================== 의사결정 보조 (증산 성립·전환 조건·비교표·적용 순서)
CHANGE_ORDER = {"운영변경": 0, "설비개조": 1, "설비교체": 2, "공정전환": 3, "": 0}


def production_check(clean, eff, selected, values, cases):
    """증산 +20% 성립: 화성 처리능력과 에이징 보관능력을 함께 본다 (에너지 판정과 별개)."""
    q, cu, pu = values["q"], values["current_utilization"], values["planned_utilization"]
    days = values.get("aging_days") or 14
    need = q * cu / pu - 1.0
    allowed_days = days * pu / (q * cu)   # 슬롯을 늘리지 않을 때 허용되는 평균 에이징 점유 일수
    eff_levers, _ = effective_levers(clean, selected)
    rows = [e for e in eff if e["role"] == "space" and e["use"] == USE_CALC and e["lever_id"] in eff_levers]
    gain = None
    if rows:
        gain = (min(e["lo"] for e in rows), statistics.median(e["typ"] for e in rows), max(e["hi"] for e in rows))
    # 에이징 단축 근거(기간 비) - 작을수록 유리: 보수 = 최댓값
    arows = [e for e in eff if e["role"] == "aging" and e["use"] == USE_CALC and e["lever_id"] in eff_levers]
    ratio = None
    if arows:
        ratio = (min(e["lo"] for e in arows), statistics.median(e["typ"] for e in arows), max(e["hi"] for e in arows))
    g = gain or (0.0, 0.0, 0.0)
    rt = ratio or (1.0, 1.0, 1.0)
    bur_a = burdens(clean, selected, [1.0] * len(S.SYSTEMS))
    ad = bur_a["aging_days"]
    pend_age = [p["fmea_id"] for p in bur_a["pending"] if p["metric"] == "added_aging_days"]
    # 필요 슬롯 배수 = q·cu/pu × (기간비 × 기존일수 + 추가 보관일) / 기존일수 ≤ 1 + 슬롯 확보율 이면 성립
    ok_case = {c: q * cu / pu * (r_ * days + a_) / days - 1.0 <= gg + 1e-12
               for c, r_, gg, a_ in (("conservative", rt[2], g[0], ad["hi"]), ("typical", rt[1], g[1], ad["typ"]),
                                     ("optimistic", rt[0], g[2], ad["lo"]))}
    how = " + ".join(x for x, on in (("슬롯 확보", gain), ("에이징 단축", ratio)) if on)
    if need <= 1e-12:
        a_status, a_ok = "추가 슬롯 불필요", True
    weak = bool(rows + arows) and all(S.GRADE_ORDER.index(e["grade"]) >= S.GRADE_ORDER.index("D") for e in rows + arows)
    if need > 1e-12 and ok_case["conservative"] and (gain or ratio) and weak:
        a_status, a_ok = f"조건부 확보({how}, 근거 등급 D 이하만)", None
    elif ok_case["conservative"] and (gain or ratio):
        a_status, a_ok = f"근거상 확보({how})", True
    elif ok_case["typical"] and (gain or ratio):
        a_status, a_ok = f"조건부 확보({how}, 대표값 기준)", None
    elif ok_case["optimistic"] and (gain or ratio):
        a_status, a_ok = f"조건부 확보({how}, 근거 상한 기준)", None
    elif gain or ratio:
        a_status, a_ok = f"미확보 - {how} 근거가 요구량에 못 미침", False
    else:
        a_status, a_ok = "미확보 - 보관 공간 확보·에이징 단축 근거 없음", False
    if pend_age and (gain or ratio):
        a_status += f" [추가 보관일 미정량 {len(pend_age)}건 - 하한 기준]"
    t = cases["typical"]
    f_ok, f_ub = t["capacity_ok"], t.get("capacity_upper_bound", False)
    if f_ok and a_ok is True and not f_ub:
        verdict = "증산 성립"
    elif f_ok and a_ok is not False:
        verdict = "증산 조건부"
    elif f_ok:
        verdict = "증산 미완결 - 에이징 보관능력 미확보"
    else:
        verdict = "증산 미달 - 화성 처리능력 부족"
    return {"verdict": verdict, "formation_capacity": t["capacity"], "formation_ok": f_ok, "formation_upper_bound": f_ub,
            "aging_required_slot_gain": need, "aging_allowed_days_without_slots": allowed_days, "aging_days": days,
            "aging_gain": gain, "aging_ratio": ratio, "aging_status": a_status, "aging_added_days": ad,
            "aging_pending": pend_age,
            "aging_ids": [e["effect_id"] for e in rows + arows],
            "note": (f"에이징 {days:g}일을 유지하면 슬롯 +{need * 100:.1f}% 필요(현재 사용률 {cu:.0%}→계획 상한 {pu:.0%}). "
                     f"슬롯을 늘리지 않으려면 평균 점유 {allowed_days:.2f}일 이하가 필요하나, 이는 에이징 단축 근거가 아니라 요구조건이다.")}


def flip_thresholds(clean, eff, selected, values, B, best_add, w, eh):
    """추천이 바뀌는 조건 - 결정적 역산 (최적화·확률 아님)."""
    import core
    out = []
    sysr, _, _, cs = _run_cases(clean, eff, selected, values, B)
    pt = cs["typical"]["plant"]
    for j, s in enumerate(S.SYSTEMS):
        if not sysr[s]["no_evidence"]:
            continue
        others = sum(pt["E"]) - pt["E"][j]
        req = core.required_reduction(others, pt["P_add"], pt["target_energy"], pt["B"][j])
        lv = ", ".join(sysr[s]["no_evidence"])
        txt = (f"{s} 레버({lv})에 계통 기준 {req * 100:.1f}% 이상의 근거가 확보되면, 레버를 추가하지 않고도 현재 선택 조합으로 대표 기준 충족"
               if req is not None and req <= 1 else f"{s} 레버({lv})만으로는 목표 보완 불가(요구 {req * 100:.0f}%)")
        out.append({"kind": "근거 없는 레버의 기준값", "system": s, "value": req, "text": txt})
    if best_add:
        sel2 = list(selected) + list(best_add)
        sysr2, _, _, cs2 = _run_cases(clean, eff, sel2, values, B)
        pt2 = cs2["typical"]["plant"]
        for j, s in enumerate(S.SYSTEMS):
            if sysr2[s]["typ"] <= 0:
                continue
            others = sum(pt2["E"]) - pt2["E"][j]
            req = core.required_reduction(others, pt2["P_add"], pt2["target_energy"], pt2["B"][j])
            m = sysr2[s]["typ"] - req
            out.append({"kind": "추천 조합 유지 조건", "system": s, "value": req, "margin": m,
                        "text": f"{s} 절감 대표값이 {max(req, 0) * 100:.1f}% 아래로 내려가면 추천 조합도 대표 기준 미달 "
                                f"(현재 {sysr2[s]['typ'] * 100:.1f}%, 여유 {m * 100:+.1f}%p)"})
        hr = -cs2["typical"]["gap"]
        out.append({"kind": "관리 부담 허용치", "system": "공장", "value": hr,
                    "text": f"미정량 관리 부담(추가 전력) 합이 {hr:.2f} pt 이하여야 추천 조합이 대표 기준 충족을 유지"})
        cg = cs2["conservative"]["gap"]
        if cg > 0:
            out.append({"kind": "보수 기준 충족 조건", "system": "공장", "value": cg,
                        "text": f"보수(근거 하한) 기준까지 충족하려면 추가로 {cg:.2f} pt(기준 전력 100 대비) 절감 필요"})
        # 에너지 종류 가정이 바뀌면
        for s in ("드라이룸", "건조"):
            if eh.get(s):
                eff_alt = classify_effects(clean, w, {**eh, s: False}, bool(values.get("kb_allow_cross_share")),
                                           plant_basis(clean, values))
                sys_alt, _d, _b, cs_alt = _run_cases(clean, eff_alt, sel2, values, B)
                v = _verdict(cs_alt)
                worse = [l for l in (best_add or []) if _lever(clean, l)["system"] == s
                         and (lever_saving(eff_alt, l) or {}).get("typ", 0) < 0]
                txt = (f"{s} 가열이 가스·스팀이면 추천 조합 대표 {cs_alt['typical']['saving'] * 100:.1f}% → '{v}'"
                       f" ({s} 계통 전력 {'절감' if sys_alt[s]['typ'] >= 0 else '증가'} {abs(sys_alt[s]['typ']) * 100:.1f}%: 전력 절대 증감·설비 전기 변화율 근거로 계산)")
                if worse:
                    alt = search_additions(clean, eff_alt, selected, values, B)
                    ab = next(iter(alt["results"]), None)
                    txt += (f". {', '.join(worse)}는 열을 전기로 바꾸는 기술이라 전력이 오히려 늘어 제외해야 함"
                            + (f" → 그 경우 최선 조합은 +{'+'.join(ab['add'])} 대표 {ab['typical'] * 100:.1f}%('{ab['verdict']}')" if ab else ""))
                out.append({"kind": "에너지 종류 가정", "system": s, "value": cs_alt["typical"]["saving"], "text": txt})
    fm = core.formation_capacity(values["formation_h"], 0.0, values["channel_ratio"], values["availability_ratio"],
                                 values["yield_ratio"], values["baseline_formation_h"], values["target_capacity_ratio"])
    out.append({"kind": "화성 관리 부담 허용치", "system": "화성", "value": fm["allowed_added_h"],
                "text": f"화성 {values['formation_h']:g}h에서 진단·검사 등 추가 채널 점유 합이 {fm['allowed_added_h']:.2f} h 이하여야 처리능력 1.2배 유지"})
    return out


def plant_electricity(eff, values):
    rows = [e for e in eff if e["role"] == "plant" and e["use"] == USE_CALC]
    if not rows:
        return None
    lo, hi = min(e["lo"] for e in rows), max(e["hi"] for e in rows)
    cap = values.get("baseline_capacity_gwh") or 10.0
    return {"intensity_lo": lo, "intensity_hi": hi, "capacity_gwh": cap, "gwh_lo": lo * cap, "gwh_hi": hi * cap,
            "ids": [e["effect_id"] for e in rows]}


# ================================================================== 품질 확인 상태 · 종합 판정 · 결합 민감도
def _same(a, b):
    try:
        return abs(float(a) - float(b)) <= 1e-9 * max(1.0, abs(float(a)))
    except (TypeError, ValueError):
        return a == b


def quality_status(clean, selected, values):
    """선택 레버의 FMEA 품질 관문 확인 상태.

    values["kb_quality_confirmations"] = {fmea_id: {"status": "확인"|"불합격", "conditions": {입력키: 값}, "memo": str}}
    확인 당시 조건(conditions)과 현재 입력이 다르면 확인을 승계하지 않고 '재검증 필요'로 돌린다.
    """
    conf = values.get("kb_quality_confirmations") or {}
    eff_levers, _ = effective_levers(clean, selected)
    rows = []
    for r in clean["fmea"]:
        if r["lever_id"] not in eff_levers or not r.get("quality_gate"):
            continue
        c = conf.get(r["fmea_id"])
        changed = []
        cid = (c or {}).get("candidate_id")
        if c and cid not in (None, "*") and values.get("candidate_id") is not None and cid != values.get("candidate_id"):
            c, st = None, "미확인"                       # 다른 후보에서 한 확인은 승계하지 않음
        if not c:
            st = "미확인"
        elif c.get("status") == "불합격":
            st = "불합격"
        elif c.get("status") == "확인":
            changed = [f"{k} {v}→{values.get(k)}" for k, v in (c.get("conditions") or {}).items() if not _same(v, values.get(k))]
            st = "재검증 필요" if changed else "확인"
        else:
            st = "미확인"
        rows.append({"fmea_id": r["fmea_id"], "lever_id": r["lever_id"], "gate": r["quality_gate"],
                     "failure_mode": r["failure_mode"], "status": st, "changed": changed,
                     "memo": (c or {}).get("memo", "")})
    n = {k: sum(x["status"] == k for x in rows) for k in ("확인", "미확인", "재검증 필요", "불합격")}
    return {"rows": rows, "counts": n}


# 품질 관문을 '확인'으로 기록할 때 함께 저장하는 공정 조건 (이 값이 바뀌면 확인을 승계하지 않는다)
GATE_CONDITION_KEYS = {
    "화성": ["formation_h", "channel_ratio", "availability_ratio", "yield_ratio"],
    "에이징": ["aging_days", "current_utilization", "planned_utilization"],
    "건조": ["kb_electric_heating", "kb_combine_retention", "solids", "drying_profile"],
    "드라이룸": ["kb_electric_heating"],
    "기타": [],
}


def confirmation_record(clean, fmea_id, status, memo, values, candidate_id=None):
    """앱·스크립트에서 품질 관문 확인/불합격을 기록하는 표준 형식. 확인이면 현재 공정 조건을 같이 저장한다."""
    if status not in ("확인", "불합격"):
        raise ValueError("상태는 '확인' 또는 '불합격'")
    if status == "확인" and not str(memo or "").strip():
        raise ValueError("확인 기록에는 근거 메모가 필요합니다 (시험 번호·결과 등)")
    row = next((r for r in clean["fmea"] if r["fmea_id"] == fmea_id), None)
    if row is None:
        raise KBError(f"FMEA 없음: {fmea_id}")
    sys_ = _lever(clean, row["lever_id"])["system"]
    rec = {"status": status, "memo": str(memo or "").strip()}
    if candidate_id:
        rec["candidate_id"] = candidate_id
    if status == "확인":
        # 값이 없는 조건(예: 후보를 정하지 않은 화면의 고형분)은 저장하지 않는다 - 없는 값과 비교해 '재검증'이 되는 것 방지
        rec["conditions"] = {k: values.get(k) for k in GATE_CONDITION_KEYS.get(sys_, []) if values.get(k) is not None}
    return rec


OVERALL_OK = "입력 조건 내 동시 충족"


def overall_verdict(energy_verdict, prod, quality, drying=None):
    """에너지·건조·화성·에이징·품질을 한 줄로.

    우선순위: 품질 불합격 → 에너지 → 건조 → 화성 → 에이징 → 미확인(건조 속도·품질) → 조건부.
    axes[*]["state"]는 4상태(검증 완료 / 가정하 수치 충족 / 미확인 / 미달). '미확인'은 통과가 아니다.
    """
    qn = quality["counts"]
    aging_ok = prod["aging_status"].startswith(("근거상", "추가", "조건부"))
    axes = [
        {"axis": "에너지(원단위 -30%)", "status": energy_verdict, "ok": energy_verdict != "근거상 미달",
         "state": "미달" if energy_verdict == "근거상 미달" else "가정하 수치 충족"},
        {"axis": "화성 처리능력(1.2배)", "status": ("≤" if prod["formation_upper_bound"] else "") + f"{prod['formation_capacity']:.3f}배",
         "ok": bool(prod["formation_ok"]),
         "state": "미달" if not prod["formation_ok"] else "미확인" if prod["formation_upper_bound"] else "가정하 수치 충족"},
        {"axis": "에이징 보관능력", "status": prod["aging_status"], "ok": aging_ok,
         "state": "미달" if not aging_ok else "가정하 수치 충족" if prod["aging_status"].startswith(("근거상", "추가")) else "미확인"},
        {"axis": "품질 관문", "status": " · ".join(f"{k} {v}" for k, v in qn.items() if v) or "관문 없음",
         "ok": qn["불합격"] == 0,
         "state": "미달" if qn["불합격"] else "미확인" if (qn["미확인"] or qn["재검증 필요"] or not sum(qn.values())) else "검증 완료"},
    ]
    if drying is not None:
        axes.insert(1, {"axis": "건조 처리능력(속도 1.2배)", "status": drying["status"], "ok": drying["state"] != "미달",
                        "state": drying["state"]})
    dry_ax = next((a for a in axes if a["axis"].startswith("건조")), None)
    fail = [r["fmea_id"] for r in quality["rows"] if r["status"] == "불합격"]
    wait = []
    if dry_ax and dry_ax["state"] == "미확인":
        wait.append("건조 속도")
    if qn["미확인"] or qn["재검증 필요"]:
        wait.append("품질")
    if fail:
        label = f"적용 제외 - 품질 불합격({', '.join(fail)})"
    elif energy_verdict == "근거상 미달":
        label = "목표 미달 - 에너지"
    elif dry_ax and dry_ax["state"] == "미달":
        label = "목표 미달 - 건조 처리능력"
    elif not prod["formation_ok"]:
        label = "목표 미달 - 화성 처리능력"
    elif not aging_ok:
        label = "증산 미완결 - 에이징 보관능력"
    elif wait:
        label = "수치 충족 · 확인 대기(" + "·".join(wait) + ")"
    elif (energy_verdict != "근거상 충족" or prod["formation_upper_bound"]
          or not prod["aging_status"].startswith(("근거상", "추가"))):
        label = "조건부 동시 충족"
    else:
        label = OVERALL_OK
    return {"label": label, "axes": axes, "all_ok": label == OVERALL_OK}


def assess(clean, eff, sel, values, B):
    """한 레버 조합에 대한 종합 판정 묶음."""
    sysr, _d, bur, cs = _run_cases(clean, eff, sel, values, B)
    for c in cs.values():
        c["capacity_upper_bound"] = any(p["metric"] == "added_occupancy_h" for p in bur["pending"])
    prod = production_check(clean, eff, sel, values, cs)
    qual = quality_status(clean, sel, values)
    ev_v = _verdict(cs)
    import candidates   # 건조 처리능력 축 (기존 배합 기준, 질량수지)
    dry = candidates.drying_axis(eff, effective_levers(clean, sel)[0], values)
    return {"levers": list(sel), "energy_verdict": ev_v, "cases": cs, "production": prod, "quality": qual,
            "drying": dry, "overall": overall_verdict(ev_v, prod, qual, dry)}


KAPPA_GRID = [round(0.1 * i, 1) for i in range(11)]
P_GRID = [0.5 * i for i in range(21)]   # 0~10 pt


def combination_sensitivity(clean, eff, sel, values, B):
    """결합 이득 유지율 κ × 추가 미정량 관리 전력 P 격자에서 대표 절감률. 확률·분포가 아니라 결정적 격자 계산."""
    sysr, *_ = _run_cases(clean, eff, sel, values, B)
    multi = [s for s in S.SYSTEMS if sysr[s].get("n_groups", 0) > 1]
    target = 1.0 - values["target_intensity_ratio"]

    def saving(k, p, case="typical"):
        v = {**values, "kb_combine_retention": k, "kb_extra_burden_pt": (values.get("kb_extra_burden_pt") or 0.0) + p}
        return _run_cases(clean, eff, sel, v, B)[3][case]["saving"]

    grid = [[saving(k, p) for p in P_GRID] for k in KAPPA_GRID]

    def k_min(case):
        if saving(1.0, 0.0, case) < target - 1e-12:
            return None   # κ=1에서도 미달
        if saving(0.0, 0.0, case) >= target - 1e-12:
            return 0.0
        lo, hi = 0.0, 1.0
        for _ in range(50):
            mid = (lo + hi) / 2
            if saving(mid, 0.0, case) >= target - 1e-12:
                hi = mid
            else:
                lo = mid
        return hi

    def p_max(k):
        if saving(k, 0.0) < target - 1e-12:
            return None
        lo, hi = 0.0, 100.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if saving(k, mid) >= target - 1e-12:
                lo = mid
            else:
                hi = mid
        return lo

    return {"levers": list(sel), "multi_systems": multi, "applies": bool(multi), "target": target,
            "kappa_grid": KAPPA_GRID, "p_grid": P_GRID, "saving_typ": grid,
            "kappa_min_typ": k_min("typical"), "kappa_min_cons": k_min("conservative"),
            "p_max": {k: p_max(k) for k in (1.0, 0.75, 0.5)},
            "note": ("κ는 한 계통 안에서 서로 다른 그룹 레버를 함께 쓸 때 독립 결합 대비 추가 이득이 남는 비율(1=독립, 0=가장 큰 레버만). "
                     "P는 아직 정량화되지 않은 관리 전력(기준 공장 100 대비 pt). 근거 확인 전까지 둘 다 민감도 변수다.")}


def compare_options(clean, eff, selected, values, B, combos, n_top=3):
    """개선안 비교표: 생산능력 · 원단위(보수/대표/낙관) · 연간 전력·금액 절감 · 허용 투자비 · 품질 위험 · 적용 난이도."""
    import core
    w, f, q = values["w"], values["f"], values["q"]
    E0 = sum(B)   # 증산만 적용(절감 없음)
    pe = plant_electricity(eff, values)
    price = values.get("electricity_price_krw_per_kwh") or 100.0
    years = values.get("payback_years") or [3, 5]
    fm_by = {}
    for r in clean["fmea"]:
        fm_by.setdefault(r["lever_id"], []).append(r)
    opts = [("근거: v10 채택 레버", list(selected), [])]
    for x in combos["results"][:n_top]:
        opts.append(("근거: v10 + " + " + ".join(x["add"]), list(selected) + x["add"], x["add"]))
    rows = []

    def money(pt_saved):
        if pe is None or pt_saved is None:
            return None
        g_lo, g_hi = pt_saved / 100 * pe["gwh_lo"], pt_saved / 100 * pe["gwh_hi"]
        k_lo, k_hi = g_lo * 1e6 * price / 1e8, g_hi * 1e6 * price / 1e8   # 억원/년
        return {"gwh": (g_lo, g_hi), "krw_eok": (k_lo, k_hi),
                "invest_eok": {n: (k_lo * n, k_hi * n) for n in years}}

    # v10 가정 경로 (사람이 정한 r - 근거 미검증, 비교 기준)
    pa = values.get("p_add_aggregate")
    pv = core.plant_energy(w, f, values["r"], q, pa if pa is not None else 2.0, "pt", values["target_intensity_ratio"])
    rows.append({"option": "v10 가정 경로(근거 미검증)", "levers": [], "add": [], "verdict": "가정 기반",
                 "saving": (None, pv["saving_ratio"], None), "gap_typ": pv["gap"], "pt_saved_typ": E0 - pv["E_total"],
                 "pt_saved_cons": None, "money_typ": money(E0 - pv["E_total"]), "money_cons": None,
                 "production": None, "risks": None, "safety_risks": None, "difficulty": "-", "evidence": "사람이 정한 r"})
    for name, sel, add in opts:
        sysr, _d, bur, cs = _run_cases(clean, eff, sel, values, B)
        for c in cs.values():
            c["capacity_upper_bound"] = any(p["metric"] == "added_occupancy_h" for p in bur["pending"])
        eff_l, _ = effective_levers(clean, sel)
        fms = [r for l in eff_l for r in fm_by.get(l, [])]
        diff = max((_lever(clean, l).get("change_type", "") for l in eff_l), key=lambda c: CHANGE_ORDER.get(c, 0), default="")
        prod = production_check(clean, eff, sel, values, cs)
        n_ev = sum(1 for l in eff_l if lever_saving(eff, l) is not None)
        rows.append({"option": name, "levers": sel, "add": add, "verdict": _verdict(cs),
                     "saving": (cs["conservative"]["saving"], cs["typical"]["saving"], cs["optimistic"]["saving"]),
                     "gap_typ": cs["typical"]["gap"], "pt_saved_typ": E0 - cs["typical"]["E_total"],
                     "pt_saved_cons": E0 - cs["conservative"]["E_total"],
                     "money_typ": money(E0 - cs["typical"]["E_total"]), "money_cons": money(E0 - cs["conservative"]["E_total"]),
                     "production": prod["verdict"], "risks": len(fms),
                     "safety_risks": sum("안전" in r.get("affected_list", []) for r in fms),
                     "pending_burdens": len(bur["pending"]), "difficulty": diff or "-",
                     "evidence": f"근거 있는 레버 {n_ev}/{len([l for l in eff_l if _lever(clean, l)['exclusive_group'] != 'BASE'])}"})
    return {"rows": rows, "plant": pe, "price_krw_per_kwh": price, "payback_years": years, "E0": E0,
            "note": ("연간 절감은 '증산만 적용(절감 없음)' 대비 전력 감소분 × 현재 공장 연간 전력(KB 전력 원단위 × 기준 생산능력). "
                     f"단가 {price:g}원/kWh는 입력값(v10 예시 100원/kWh), 허용 투자비는 할인 없는 단순 회수기간 기준. "
                     "투자 견적이 아니라 '이 금액 이하일 때 회수 가능'이라는 역산값이다.")}


def roadmap(clean, eff, rec_levers, values, B):
    """3년 적용 순서: 변경유형으로 단계를 나누고, 근거FMEA 품질 관문을 다음 단계 진입 조건으로 쓴다."""
    eff_l, _ = effective_levers(clean, rec_levers)
    fm_by = {}
    for r in clean["fmea"]:
        fm_by.setdefault(r["lever_id"], []).append(r)
    bur = burdens(clean, rec_levers, B)
    stage_of = {"운영변경": 1, "설비개조": 2, "설비교체": 3, "공정전환": 9}
    stages = {1: [], 2: [], 3: [], 9: []}
    for l in eff_l:
        lv = _lever(clean, l)
        if lv["exclusive_group"] == "BASE":
            continue
        st = 9 if lv.get("horizon") == "장기" else stage_of.get(lv.get("change_type") or "운영변경", 1)
        ls = lever_saving(eff, l)
        stages[st].append({"lever_id": l, "name": lv["name_ko"], "system": lv["system"],
                           "change_type": lv.get("change_type") or "-", "has_evidence": ls is not None,
                           "gates": [g["quality_gate"] for g in fm_by.get(l, []) if g.get("quality_gate")]})
    pend = [f"{p['fmea_id']}({p['lever_id']}) {p['failure_mode']}" for p in bur["pending"]]
    plan = [
        {"year": "1년차", "title": "계측·파일럿 + 운영 변경",
         "actions": ["계통·구간별 전력과 열, 화성 채널 점유, 에이징 슬롯 사용률 실측 → KB 근거를 대상 공장 값으로 교체",
                     "근거 없는 레버(KB '근거 없음')는 파일럿 계측으로 효과 확인 후 데이터셋에 등급 B로 추가",
                     *(["관리 부담 정량화: " + "; ".join(pend)] if pend else [])],
         "levers": stages[1],
         "exit": "운영 변경 레버의 품질 관문 통과 + 실측 효과가 근거 보수값 이상 → 2년차 설비 개조 착수"},
        {"year": "2년차", "title": "설비 개조 (1년차 실측 부하에 맞춰 용량 선정)",
         "actions": ["1년차 실측 잔여 부하로 개조 설비 용량 선정 (과대 용량 방지)", "에이징 보관 공간 승인 슬롯 확정"],
         "levers": stages[2],
         "exit": "개조 레버의 품질 관문 통과 + 원단위가 목표 경계 안으로 진입 → 3년차 확대"},
        {"year": "3년차", "title": "확대·교체, 양품 1.2배 조건에서 평가",
         "actions": ["검증된 조건을 전 라인으로 확대", "양품 생산 1.2배 조건에서 원단위·장기 수명 확인, 잔여 격차 보고"],
         "levers": stages[3], "exit": "목표 미달 시 잔여 격차와 다음 투자 대안 제시"},
    ]
    if stages[9]:
        plan.append({"year": "중장기", "title": "공정 전환 후보 (3년 범위 밖)", "actions": ["별도 투자·검증 계획"],
                     "levers": stages[9], "exit": "-"})
    return plan
