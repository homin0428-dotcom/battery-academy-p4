"""Battery Process Change v10 - 순수 계산 엔진.

UI(app.py)·CLI(run.py)·보고서(reporting.py)가 모두 이 모듈의 함수만 사용한다.
모든 판정은 반올림 이전 값으로 수행하며, 표시용 반올림은 fmt_* 함수에서만 한다.

상태 구분
  수치 상태 : 충족 / 미달 / 계산 보류 / 입력 오류
  품질 상태 : 미확인 / 검증 중 / 충족 / 미충족   (수치 상태와 독립)
"""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import math
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = BASE_DIR / "configs" / "scenarios.json"
DEFAULT_PFMEA = BASE_DIR / "data" / "pfmea.csv"
DEFAULT_EVIDENCE = BASE_DIR / "data" / "evidence.csv"

TOL = 1e-9
SYSTEMS = ["건조", "드라이룸", "화성", "에이징", "기타"]
NUM_OK, NUM_FAIL, NUM_HOLD, NUM_ERR = "충족", "미달", "계산 보류", "입력 오류"
Q_STATES = ("미확인", "검증 중", "충족", "미충족")
ORIGINS = ("problem", "literature", "assumption", "requirement", "derived")
ACCT_LOCATIONS = ("included_in_process", "additional")

# 내부 단위 규약: 이 단위와 다르게 입력되면 계산을 차단한다.
EXPECTED_UNITS = {
    "baseline_formation_h": "h", "formation_h": "h", "added_occupancy_h": "h",
    "channel_ratio": "ratio", "availability_ratio": "ratio", "yield_ratio": "ratio",
    "target_capacity_ratio": "ratio", "target_intensity_ratio": "ratio", "q": "ratio",
    "aging_days": "day", "current_utilization": "ratio", "planned_utilization": "ratio",
    "old_wait_days": "day", "new_wait_days": "day", "conversion_fraction": "ratio",
    "w": "pt", "f": "ratio", "r": "ratio", "p_add_aggregate": "pt",
    "regen_independent_pt": "pt",
    "drying_b_global": "kWth/kWe", "drying_b_zones": "kWth/kWe",
}
MODE_B_UNIT = "kWth/kWe"
DRYING_SCOPES = ("system", "zone")

# 과제 표의 비교 조건 (화성 3개 + 공장 전력 3개)
FORMATION_CONDITIONS = [
    ("C1", "16h+0.25h, 채널 1.00", 16.0, 0.25, 1.00, "목표 사양"),
    ("C2", "16h+2h, 채널 1.00", 16.0, 2.0, 1.00, "비교 가정(추가 점유 영향)"),
    ("C3", "16h+2h, 채널 1.08", 16.0, 2.0, 1.08, "비교 가정(채널 보완 영향)"),
]


PARAM_KO = {
    "allowed_protocol_formation_h": "허용 프로토콜 화성시간", "channel_ratio_supplement": "채널 보강량",
    "added_occupancy_h": "추가 채널 점유시간", "replaceable_diagnostic_scope": "진단 대체 가능 범위",
    "auxiliary_heat": "품질 확보용 보조열", "auxiliary_power": "추가 전기 소모",
    "heat_source_capacity": "열원 가용량", "dryroom_environment_load": "드라이룸 환경부하",
    "conversion_fraction": "슬롯 전환 비율",
}
TARGET_KO = {
    "formation_h": "화성 본공정 시간", "channel_ratio": "채널비", "added_occupancy_h": "추가 점유시간 입력",
    "none": "계산 미연결(대체 후보 표시)", "drying_b_heating_demand": "건조 모드 B 가열 수요",
    "p_add": "추가 관리 전력 P_add", "drying_b_qsource": "건조 모드 B 열원", "conversion_fraction": "슬롯 전환 비율",
}


# PFMEA impact_value 허용 단위: 차원별 {입력 단위: 내부 단위로의 배율}. 그 외 단위는 차단한다.
PFMEA_DIMENSION = {
    "allowed_protocol_formation_h": "time", "added_occupancy_h": "time",
    "channel_ratio_supplement": "ratio", "replaceable_diagnostic_scope": "ratio", "conversion_fraction": "ratio",
    "auxiliary_power": "pt", "dryroom_environment_load": "pt",
    "auxiliary_heat": "heat", "heat_source_capacity": "heat",
}
PFMEA_TARGET_DIMENSION = {
    "formation_h": "time", "added_occupancy_h": "time", "channel_ratio": "ratio", "conversion_fraction": "ratio",
    "p_add": "pt", "drying_b_heating_demand": "heat", "drying_b_qsource": "heat",
}
PFMEA_UNITS = {
    "time": ("h", {"h": 1.0, "hr": 1.0, "min": 1.0 / 60.0}),
    "ratio": ("ratio", {"ratio": 1.0, "%": 0.01}),
    "pt": ("pt", {"pt": 1.0}),
    "heat": ("kWth", {"kWth": 1.0, "MWth": 1000.0}),
}

# PFMEA 효과의 계산 연결 방식. 자동 반영은 run_scenario가 직접 계산 입력으로 쓰는 경우만이다.
# 수동 항목은 대응 시나리오 입력을 사용자가 직접 바꿔 검토해야 하며, 자동 합산·배분하지 않는다.
MANUAL_LINK_KO = {
    "formation_h": "탭 2 '화성 본공정 시간 [h]' 입력으로 수동 검토",
    "channel_ratio": "탭 2 '채널비' 입력으로 수동 검토",
    "added_occupancy_h": "탭 2 '추가 점유시간' 직접 입력으로 수동 검토",
    "p_add": "탭 2 'P_add aggregate' 입력에 포함 여부를 수동 확인",
    "drying_b_heating_demand": "모드 B 구간별 heat_new_kwth에 수동 반영 (구간 지정 필요, 자동 합산·배분 안 함)",
    "drying_b_qsource": "모드 B 전체 qsource_kwth에 수동 반영",
    "conversion_fraction": "에이징 conversion_fraction 입력으로 수동 검토",
    "none": "계산 미연결 (대체 후보 표시용)",
}
LINK_AUTO, LINK_MANUAL, LINK_NONE, LINK_EXCLUDED = "자동 반영", "수동 반영 대상", "계산 미연결", "해당 없음"
LINK_AUTO_PENDING = "자동 반영 대상(값 미확인)"   # 자동 연결 경로는 있으나 impact_value가 없어 아직 합산되지 않음

# 화면·보고서 표시용 한국어 표현 (내부 키값은 계산·설정에만 사용)
KEY_KO = {"manual": "수동 입력", "mode_a": "모드 A", "mode_b": "모드 B",
          "aggregate": "합산 방식", "itemized": "항목별 합산 방식",
          "pfmea": "PFMEA 효과 합계", "input": "직접 입력"}


class InputError(ValueError):
    """부적절한 입력 값 (계산 차단)."""


# ---------------------------------------------------------------- helpers
def _isnum(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _need(x, name):
    if not _isnum(x):
        raise InputError(f"{name}: 숫자가 아닌 값({x!r})")
    return float(x)


_TRUE_STR = {"true", "t", "yes", "y", "1", "예", "네", "적합", "o"}
_FALSE_STR = {"false", "f", "no", "n", "0", "아니오", "아니요", "부적합", "x"}


def to_bool(v, name):
    """명시적 참·거짓 변환. bool("False")==True 같은 암묵 변환을 쓰지 않는다. None은 미확인으로 그대로 둔다."""
    if v is None or isinstance(v, bool):
        return v
    if isinstance(v, (int, float)) and not isinstance(v, bool) and v in (0, 1):
        return bool(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s == "":
            return None
        if s in _TRUE_STR:
            return True
        if s in _FALSE_STR:
            return False
    raise InputError(f"{name}: 참·거짓으로 해석할 수 없는 값({v!r}) - True/False 또는 예/아니오만 허용")


def _ge(a, b, tol=TOL):
    return a >= b - tol * max(1.0, abs(b))


def _hold(missing, reason=None):
    return {"status": NUM_HOLD, "missing": list(missing), "reason": reason or "필수 입력 미확인"}


def _err(msg):
    return {"status": NUM_ERR, "error": msg}


def _safe(fn, *a, **k):
    try:
        return fn(*a, **k)
    except InputError as e:
        return _err(str(e))


def fmt_ratio(x, n=4):
    return "-" if x is None else f"{x:.{n}f}"


def fmt_pct(x, n=2):
    return "-" if x is None else f"{x * 100:.{n}f}%"


def fmt_pct_up(x, n=1):
    """요구 사양(이상)은 표시 시 올림한다. 판정은 항상 원 값으로 수행."""
    if x is None:
        return "-"
    k = 10 ** (n + 2)
    return f"{math.ceil(x * k - 1e-9) / (k / 100):.{n}f}%"


def fmt_num(x, n=2, unit=""):
    return "-" if x is None else f"{x:.{n}f}{unit}"


# ---------------------------------------------------------------- 화성
def formation_capacity(formation_h, added_occupancy_h, channel_ratio, availability_ratio,
                       yield_ratio, baseline_h=20.0, target_ratio=1.2, baseline_channels=None):
    names = dict(formation_h=formation_h, added_occupancy_h=added_occupancy_h,
                 channel_ratio=channel_ratio, availability_ratio=availability_ratio,
                 yield_ratio=yield_ratio)
    missing = [k for k, v in names.items() if v is None]
    if missing:
        return _hold(missing)
    f = _need(formation_h, "formation_h")
    add = _need(added_occupancy_h, "added_occupancy_h")
    ch = _need(channel_ratio, "channel_ratio")
    av = _need(availability_ratio, "availability_ratio")
    yd = _need(yield_ratio, "yield_ratio")
    base = _need(baseline_h, "baseline_h")
    tgt = _need(target_ratio, "target_ratio")
    if f <= 0:
        raise InputError("formation_h는 양수여야 한다")
    if add < 0:
        raise InputError("added_occupancy_h는 음수일 수 없다")
    total = f + add
    if total <= 0:
        raise InputError("총 점유시간은 양수여야 한다")
    if ch <= 0:
        raise InputError("channel_ratio는 양수여야 한다")
    for n, v in (("availability_ratio", av), ("yield_ratio", yd)):
        if not 0 < v <= 1:
            raise InputError(f"{n}는 (0, 1] 범위의 비율이어야 한다")
    if base <= 0 or tgt <= 0:
        raise InputError("baseline_h와 target_ratio는 양수여야 한다")
    cap = ch * av * yd * base / total
    req = tgt * total / (base * av * yd)
    out = {
        "status": NUM_OK if _ge(cap, tgt) else NUM_FAIL,
        "total_occupancy_h": total,
        "capacity_ratio": cap,
        "required_channel_ratio": req,
        "extra_channel_ratio": max(0.0, req - 1.0),
        "allowed_added_h": base * ch * av * yd / tgt - f,  # 음수를 0으로 바꾸지 않는다
        "target_ratio": tgt,
        "scope": "화성 단독 처리능력 (전체 공장 생산능력 아님)",
        "required_channels": None,
    }
    if baseline_channels is not None:
        n = _need(baseline_channels, "baseline_channels")
        if n <= 0:
            raise InputError("baseline_channels는 양수여야 한다")
        out["required_channels"] = math.ceil(req * n - 1e-9)
    return out


# ---------------------------------------------------------------- 에이징
def aging_slots(q, current_utilization, planned_utilization, old_throughput_per_day=None,
                old_wait_days=None, new_throughput_per_day=None, new_wait_days=None,
                area_per_cell=None, slots_per_area=None, conversion_fraction=None, zones=None):
    """zones(구역별 입력 목록)가 있으면 구역별로 계산하고, 없으면 기존 단일 구역 계산을 유지한다."""
    q = _need(q, "q")
    cu = _need(current_utilization, "current_utilization")
    pu = _need(planned_utilization, "planned_utilization")
    if q <= 0:
        raise InputError("q는 양수여야 한다")
    if not 0 < cu <= 1 or not 0 < pu <= 1:
        raise InputError("슬롯 사용률은 (0, 1] 범위여야 한다")
    req = q * cu / pu
    out = {"status": NUM_OK, "required_slot_ratio": req,
           "additional_slot_ratio": max(0.0, req - 1.0),
           "freed_wip": None, "freed_area_m2": None, "convertible_slots": None,
           "space_status": "계산 보류", "space_note": "", "missing": [],
           "aging_days": 14, "zone_mode": False, "zones": []}
    if zones:
        return _aging_zones(out, q, cu, pu, zones)
    return _aging_space(out, old_throughput_per_day, old_wait_days, new_throughput_per_day,
                        new_wait_days, area_per_cell, slots_per_area, conversion_fraction)


def _aging_space(out, old_throughput_per_day, old_wait_days, new_throughput_per_day, new_wait_days,
                 area_per_cell, slots_per_area, conversion_fraction):
    """대기공간 -> 면적 -> 전환 슬롯 (단일 구역 또는 구역 하나). out에 결과를 채워 반환한다."""
    space = dict(old_throughput_per_day=old_throughput_per_day, old_wait_days=old_wait_days,
                 new_throughput_per_day=new_throughput_per_day, new_wait_days=new_wait_days,
                 area_per_cell=area_per_cell)
    miss = [k for k, v in space.items() if v is None]
    if miss:
        out["missing"] = miss
        out["space_note"] = "대기공간 입력 미확인 - 슬롯 비율만 출력 (공간 전환 가능성 확정 불가)"
        return out
    vals = {k: _need(v, k) for k, v in space.items()}
    if any(v < 0 for v in vals.values()):
        raise InputError("대기 공간 입력은 음수일 수 없다")
    freed_wip = (vals["old_throughput_per_day"] * vals["old_wait_days"]
                 - vals["new_throughput_per_day"] * vals["new_wait_days"])
    freed_area = freed_wip * vals["area_per_cell"]
    out["freed_wip"], out["freed_area_m2"] = freed_wip, freed_area
    if freed_area < 0:
        out["space_status"] = "추가 공간 필요"
        out["space_note"] = "freed_area가 음수 - 추가 공간이 필요 (0으로 바꾸지 않음)"
    if slots_per_area is None or conversion_fraction is None:
        if freed_area >= 0:
            out["space_note"] = "slots_per_area 또는 conversion_fraction 미확인 - 면적만 출력, 전환 슬롯 확정 불가"
        out["missing"] = [k for k, v in (("slots_per_area", slots_per_area),
                                         ("conversion_fraction", conversion_fraction)) if v is None]
        return out
    spa, cf = _need(slots_per_area, "slots_per_area"), _need(conversion_fraction, "conversion_fraction")
    if spa < 0 or not 0 <= cf <= 1:
        raise InputError("slots_per_area는 0 이상, conversion_fraction은 0~1이어야 한다")
    out["convertible_slots"] = max(0.0, freed_area) * spa * cf
    if freed_area >= 0:
        out["space_status"] = "조건부"
        out["space_note"] = ("조건부 전환 가능성 - 최소 버퍼 시간·동선·방재·온도 균일성·추적성·설비 접근성 "
                             "검증 전에는 확정 공간이 아님")
    return out


ZONE_KEYS = ("name", "current_utilization", "planned_utilization", "old_throughput_per_day", "old_wait_days",
             "new_throughput_per_day", "new_wait_days", "area_per_cell", "slots_per_area", "conversion_fraction")


def _aging_zones(out, q, cu, pu, zones):
    """구역별 슬롯·공간 계산. 구역마다 따로 계산하고 구역 간 상쇄하지 않는다.

    총 에이징 기간은 구역과 무관하게 14일이며, 고온·상온 기간을 임의로 나누지 않는다.
    구역별 사용률이 없으면 전체 사용률(cu, pu)을 쓴다. 한 구역의 음수 freed_area는
    다른 구역의 전환 슬롯으로 메우지 않는다(전환 슬롯은 구역별 max(0, area)의 합).
    """
    if not isinstance(zones, (list, tuple)) or not all(isinstance(z, dict) for z in zones):
        raise InputError("aging_zones는 구역 입력(dict)의 목록이어야 한다")
    unknown = {k for z in zones for k in z} - set(ZONE_KEYS)
    if unknown:
        raise InputError(f"aging_zones: 알 수 없는 항목 {sorted(unknown)}")
    names = [str(z.get("name") or f"구역 {i}") for i, z in enumerate(zones, 1)]
    if len(set(names)) != len(names):
        raise InputError("aging_zones: 구역 이름이 중복되었다")
    res = []
    for nm, z in zip(names, zones):
        zcu = cu if z.get("current_utilization") is None else _need(z["current_utilization"], f"{nm}.current_utilization")
        zpu = pu if z.get("planned_utilization") is None else _need(z["planned_utilization"], f"{nm}.planned_utilization")
        if not 0 < zcu <= 1 or not 0 < zpu <= 1:
            raise InputError(f"{nm}: 슬롯 사용률은 (0, 1] 범위여야 한다")
        req = q * zcu / zpu
        zo = {"name": nm, "required_slot_ratio": req, "additional_slot_ratio": max(0.0, req - 1.0),
              "freed_wip": None, "freed_area_m2": None, "convertible_slots": None,
              "space_status": "계산 보류", "space_note": "", "missing": []}
        try:
            _aging_space(zo, *(z.get(k) for k in ZONE_KEYS[3:]))
        except InputError as e:
            raise InputError(f"{nm}: {e}") from None
        res.append(zo)
    out["zone_mode"], out["zones"] = True, res
    done = [z for z in res if z["freed_area_m2"] is not None]
    out["missing"] = [f"{z['name']}.{m}" for z in res for m in z["missing"]]
    if len(done) == len(res):
        out["freed_wip"] = sum(z["freed_wip"] for z in res)
        out["freed_area_m2"] = sum(z["freed_area_m2"] for z in res)
    if all(z["convertible_slots"] is not None for z in res):
        out["convertible_slots"] = sum(z["convertible_slots"] for z in res)
    sts = {z["space_status"] for z in res}
    if "계산 보류" in sts:
        out["space_status"] = "계산 보류"
        out["space_note"] = "일부 구역의 입력이 미확인 - 합계를 확정하지 않음(구역별 결과만 유효)"
    elif sts == {"추가 공간 필요"}:
        out["space_status"] = "추가 공간 필요"
        out["space_note"] = "모든 구역에서 freed_area가 음수 - 추가 공간이 필요"
    elif "추가 공간 필요" in sts:
        out["space_status"] = "일부 구역 추가 공간 필요"
        out["space_note"] = ("일부 구역은 추가 공간이 필요하며 다른 구역의 여유로 상쇄하지 않음. 전환 슬롯은 구역별 "
                             "조건부 값의 합이며 구역별 버퍼·동선·방재 검증 전에는 확정 공간이 아님")
    else:
        out["space_status"] = "조건부"
        out["space_note"] = ("구역별 조건부 전환 가능성 - 최소 버퍼 시간·동선·방재·온도 균일성·추적성·설비 접근성 "
                             "검증 전에는 확정 공간이 아님")
    return out


# ---------------------------------------------------------------- 팬
def fan_affinity(fan_base, airflow_ratio):
    """팬 상사법칙: 적용 조건이 확인된 경우에만 사용한다 (fan_new = base * ratio^3)."""
    b, a = _need(fan_base, "fan_base"), _need(airflow_ratio, "airflow_ratio")
    if b < 0 or a < 0:
        raise InputError("팬 전력·풍량비는 음수일 수 없다")
    return b * a ** 3


# ---------------------------------------------------------------- 건조 모드 A
def drying_mode_a(a, s, b, cop_h, cop_c):
    a, s, b = _need(a, "a"), _need(s, "s"), _need(b, "b")
    cop_h, cop_c = _need(cop_h, "COP_h"), _need(cop_c, "COP_c")
    if not 0 < a <= 1:
        raise InputError("풍량비 a는 (0, 1] 범위여야 한다")
    if not 0 <= s <= 1 or not 0 <= b <= 1:
        raise InputError("s, b는 0~1 비율이어야 한다")
    if cop_h <= 1:
        raise InputError("COP_h는 1보다 커야 한다")
    if cop_c <= 0:
        raise InputError("COP_c는 양수여야 한다")
    H = 60.0 * (1.0 - s * (1.0 - a))
    Qh = b * H
    W = Qh / cop_h
    Qc = Qh - W
    cooling = max(0.0, 25.0 - Qc / cop_c)
    fan = 15.0 * a ** 3
    e_new = (H - Qh) + W + cooling + fan
    return {"status": NUM_OK, "mode": "A", "H": H, "Qh": Qh, "W": W, "Qc": Qc,
            "heating_resistive": H - Qh, "cooling": cooling, "fan": fan,
            "E_new": e_new, "saving_ratio": 1.0 - e_new / 100.0,
            "note": "v10 단순화 시나리오(기준 가열60/냉각25/팬15, 전기저항 효율 1). 운전 최적화 모델 아님"}


# ---------------------------------------------------------------- 건조 모드 B
ZONE_FIELDS = ("fan_base_kwe", "heat_base_kwth", "heat_new_kwth", "aux_electric_kwe",
               "hp_eligible_kwth", "supply_temp_ok", "fan_affinity")
GLOBAL_FIELDS = ("qset_kwth", "qsource_kwth", "cop_h", "cop_c", "heater_eff",
                 "compatible_cooling_kwth", "total_cooling_kwth", "aux_base_kwe")


def drying_mode_b(zones, g, unit=None):
    if unit is not None and unit != MODE_B_UNIT:
        raise InputError(f"단위 불일치: 모드 B 입력은 '{MODE_B_UNIT}' 이어야 하는데 '{unit}' 로 입력됨")
    if not isinstance(zones, (list, tuple)) or len(zones) != 3:
        raise InputError("모드 B는 정확히 3개의 건조 구간 입력이 필요하다")
    g = g or {}
    # 참·거짓 항목은 명시적으로 변환한다 (문자열 "False"를 True로 해석하지 않음)
    zones = [dict(z) for z in zones]
    for i, z in enumerate(zones, 1):
        for k in ("supply_temp_ok", "fan_affinity"):
            z[k] = to_bool(z.get(k), f"구간{i}.{k}")
    missing = [f"전체.{k}" for k in GLOBAL_FIELDS if g.get(k) is None]
    for i, z in enumerate(zones, 1):
        for k in ZONE_FIELDS:
            if z.get(k) is None:
                missing.append(f"구간{i}.{k}")
        if z.get("fan_affinity") is True:
            if z.get("airflow_ratio") is None:
                missing.append(f"구간{i}.airflow_ratio")
        elif z.get("fan_affinity") is False and z.get("fan_new_kwe") is None:
            missing.append(f"구간{i}.fan_new_kwe")
    if missing:
        return {**_hold(missing, "모드 B 필수 입력 미확인 (모드 A 값으로 채우지 않음)"), "mode": "B"}

    for k in GLOBAL_FIELDS:
        _need(g[k], k)
        if g[k] < 0:
            raise InputError(f"{k}: 음수 열량·전력 금지")
    cop_h, cop_c, eff = g["cop_h"], g["cop_c"], g["heater_eff"]
    if cop_h <= 1:
        raise InputError("COP_h는 1보다 커야 한다")
    if cop_c <= 0:
        raise InputError("COP_c는 양수여야 한다")
    if eff <= 0:
        raise InputError("heater_efficiency는 양수여야 한다")
    if g["compatible_cooling_kwth"] > g["total_cooling_kwth"] + TOL:
        raise InputError("적합 냉각수요가 전체 냉각수요를 초과할 수 없다")

    fan_base = fan_new = heat_base = heat_new = aux = hp_demand = 0.0
    rows = []
    for i, z in enumerate(zones, 1):
        fb = _need(z["fan_base_kwe"], f"구간{i}.fan_base_kwe")
        hb = _need(z["heat_base_kwth"], f"구간{i}.heat_base_kwth")
        hn = _need(z["heat_new_kwth"], f"구간{i}.heat_new_kwth")
        ax = _need(z["aux_electric_kwe"], f"구간{i}.aux_electric_kwe")
        hp = _need(z["hp_eligible_kwth"], f"구간{i}.hp_eligible_kwth")
        if min(fb, hb, hn, ax, hp) < 0:
            raise InputError(f"구간{i}: 음수 열량·전력 금지")
        if hp > hn + TOL:
            raise InputError(f"구간{i}: 히트펌프 사용 가능 가열수요가 변경 가열수요를 초과")
        if z["fan_affinity"] is True:
            fn = fan_affinity(fb, z["airflow_ratio"])
        else:
            fn = _need(z["fan_new_kwe"], f"구간{i}.fan_new_kwe")
            if fn < 0:
                raise InputError(f"구간{i}: 음수 열량·전력 금지")
        temp_ok = z["supply_temp_ok"]   # to_bool로 검증된 실제 bool
        usable = hp if temp_ok else 0.0   # 공급 온도 부적합 구간은 열공급 불허
        fan_base += fb; fan_new += fn; heat_base += hb; heat_new += hn; aux += ax; hp_demand += usable
        rows.append({"zone": z.get("name", f"구간 {i}"), "fan_base": fb, "fan_new": fn,
                     "heat_base": hb, "heat_new": hn, "hp_usable": usable, "temp_ok": temp_ok})

    q_cap = g["qsource_kwth"] / (1.0 - 1.0 / cop_h)
    Qh = min(g["qset_kwth"], hp_demand, q_cap)
    W = Qh / cop_h
    Qc = Qh - W
    q_cool = min(Qc, g["compatible_cooling_kwth"])
    rem_heat = heat_new - Qh
    rem_cool = g["total_cooling_kwth"] - q_cool
    # 기존 보조부하(aux_base_kwe)는 변경 전·후에 모두 남는 부하라 E_base와 E_new에 같이 넣는다.
    # 구간별 aux_electric_kwe는 변경안에서 추가되는 보조 전기부하이므로 E_new에만 넣는다.
    aux_base = g["aux_base_kwe"]
    e_new = rem_heat / eff + W + rem_cool / cop_c + fan_new + aux + aux_base
    e_base = fan_base + heat_base / eff + g["total_cooling_kwth"] / cop_c + aux_base
    if e_base <= 0:
        raise InputError("기준 전력 합이 0 이하라 절감률을 계산할 수 없다")
    qset, mode_b_warnings = g["qset_kwth"], []
    over = [(n, v) for n, v in (("Qset", qset), ("Qdemand", hp_demand)) if v > q_cap + TOL * max(1.0, q_cap)]
    for n, v in over:
        mode_b_warnings.append(f"{n}={v:.2f} kWth가 열원 한계 {q_cap:.2f} kWth(=Qsource/(1-1/COP_h))를 초과하여 "
                               f"Qh를 {Qh:.2f} kWth로 제한함 (열원 부족으로 히트펌프가 공급하지 못한 요구 "
                               f"{max(0.0, min(qset, hp_demand) - Qh):.2f} kWth는 보조 가열로 처리)")
    return {"status": NUM_OK, "mode": "B", "zones": rows, "Qh": Qh, "W": W, "Qc": Qc,
            "Qcool_used": q_cool, "remaining_heating": rem_heat, "remaining_cooling": rem_cool,
            "limit_by": min((("Qset", qset), ("수요", hp_demand), ("열원", q_cap)), key=lambda t: t[1])[0],
            "source_limit_kwth": q_cap, "source_limited": bool(over), "exceeded": [n for n, _ in over],
            "unmet_hp_kwth": max(0.0, min(qset, hp_demand) - Qh), "warnings": mode_b_warnings,
            "aux_base": aux_base, "aux_added": aux,
            "E_new": e_new, "E_base": e_base, "saving_ratio": 1.0 - e_new / e_base,
            "note": "구간 입력 3행 합산 후 히트펌프 1회 계산. 입력 열부하는 사용자 시나리오 조건"}


# ---------------------------------------------------------------- 공장 에너지
def validate_accounting(drying_sources=(), regen=None, zone_savings_applied_globally=False):
    """같은 절감 효과가 두 번 반영되지 않도록 회계 규칙을 검사한다."""
    srcs = list(drying_sources)
    if len(srcs) != 1:
        raise InputError(f"건조 절감률 출처는 정확히 하나여야 한다(현재 {srcs}) - 모드 A/B·수동 중복 금지")
    if srcs[0] not in ("manual", "mode_a", "mode_b"):
        raise InputError(f"알 수 없는 건조 절감률 출처: {srcs[0]}")
    if zone_savings_applied_globally:
        raise InputError("특정 구간 절감을 전체 건조 계통에 중복 적용할 수 없다 (구간 합산 결과만 전달)")
    if regen:
        mode = regen.get("accounting")
        if mode not in ("in_r", "independent"):
            raise InputError("화성 회생 회계는 in_r 또는 independent 중 하나여야 한다")
        ind = regen.get("independent_pt")
        if mode == "in_r" and ind not in (None, 0, 0.0):
            raise InputError("화성 회생이 계통 r에 포함되어 있는데 독립 수지에도 입력됨(중복 차감)")
        if mode == "independent":
            if ind is None:
                raise InputError("독립 수지 선택 시 regen_independent_pt가 필요하다")
            if _need(ind, "regen_independent_pt") < 0:
                raise InputError("regen_independent_pt는 음수일 수 없다")
            if regen.get("r_includes_regen"):
                raise InputError("화성 회생이 r과 독립 수지에 모두 반영됨(중복 차감)")
            if regen.get("usable") is not True and ind > 0:
                raise InputError("사용 가능 여부가 확인되지 않은 회생 전력은 공장 절감으로 계산할 수 없다")


def plant_energy(w, f, r, q, p_add, p_add_unit="pt", target_intensity=0.70, regen_pt=0.0, q_good=None):
    """q = 투입 부하비(설비가 처리하는 양), q_good = 양품 출하비(원단위 분모). q_good=None이면 q와 같다(기존과 동일)."""
    if p_add is None:
        return _hold(["p_add"], "추가 관리 전력 미확인")
    if p_add_unit != "pt":
        raise InputError("P_add 단위는 기준 전력 100에 대한 포인트(pt)여야 한다")
    for name, v in (("w", w), ("f", f), ("r", r)):
        if not isinstance(v, (list, tuple)) or len(v) != 5 or not all(_isnum(x) for x in v):
            raise InputError(f"{name}: 5개 계통 숫자 배열이 필요하다")
    q, p_add = _need(q, "q"), _need(p_add, "P_add")
    if q <= 0:
        raise InputError("q는 양수여야 한다")
    if abs(sum(w) - 100.0) > 1e-9:
        raise InputError(f"계통 전력 비중 합이 100이 아니다({sum(w)})")
    if any(x < 0 for x in w):
        raise InputError("전력 비중은 음수일 수 없다")
    if any(not 0 <= x <= 1 for x in f):
        raise InputError("고정부하 비율 f는 0~1이어야 한다")
    # r<0은 해당 계통 전력 증가(예: 모드 B 보조부하 증가)로 유효한 Trade-off 결과다. r>1만 물리적으로 불가능.
    if any(x > 1 for x in r):
        raise InputError("절감률 r은 1(100%)을 넘을 수 없다")
    if p_add < 0:
        raise InputError("P_add는 음수일 수 없다")
    regen_pt = _need(regen_pt if regen_pt is not None else 0.0, "regen_pt")
    if regen_pt < 0:
        raise InputError("회생 전력은 음수일 수 없다")
    B = [wi * (fi + (1 - fi) * q) for wi, fi in zip(w, f)]
    E = [bi * (1 - ri) for bi, ri in zip(B, r)]
    # 독립 회생전력은 화성 계통 전력(절감 반영 후) 안에서만 회수할 수 있다.
    if regen_pt > E[2] + TOL * max(1.0, E[2]):
        raise InputError(f"회생 전력 {regen_pt:.2f} pt가 회수 가능 상한(화성 계통 전력 {E[2]:.2f} pt)을 초과")
    e_total = sum(E) + p_add - regen_pt
    if e_total <= 0:
        raise InputError(f"총전력이 {e_total:.2f} pt로 0 이하 - 물리적으로 불가능한 입력 조합")
    qg = q if q_good is None else _need(q_good, "q_good")
    if qg <= 0:
        raise InputError("q_good은 양수여야 한다")
    target = 100.0 * qg * target_intensity
    ratio = e_total / (100.0 * qg)
    increase = [SYSTEMS[i] for i, x in enumerate(r) if x < 0]
    return {"status": NUM_OK if e_total <= target + TOL * max(1, target) else NUM_FAIL,
            "B": B, "E": E, "P_add": p_add, "regen_pt": regen_pt, "E_total": e_total,
            "E_before_reduction": sum(B), "intensity_ratio": ratio,
            "saving_ratio": 1.0 - ratio, "target_energy": target, "gap": e_total - target,
            "target_saving_ratio": 1.0 - target_intensity,
            "increase_systems": increase,
            "energy_increase": ratio > 1.0 or bool(increase)}


def required_reduction(sum_others, p_add, target_energy, b_j):
    """r_j = 1 + (sum(E_i, i!=j) + P_add - target) / B_j   (+1 항 포함, README 참조)."""
    if b_j == 0:
        return None
    return 1.0 + (sum_others + p_add - target_energy) / b_j


def interpret_required(x):
    if x is None:
        return "역산 불가능(B_j=0)"
    if x < 0:
        return "추가 절감 불필요"
    if x > 1:
        return "해당 계통 단독 보완 불가능(요구값>1, 클리핑하지 않음)"
    return "수학적으로 가능한 요구 절감률"


def reverse_requirements(plant, r_in):
    rows = []
    for j, name in enumerate(SYSTEMS):
        others = sum(plant["E"]) - plant["E"][j]
        req = required_reduction(others, plant["P_add"] - plant["regen_pt"],
                                 plant["target_energy"], plant["B"][j])
        rows.append({"system": name, "B_j": plant["B"][j], "r_input": r_in[j],
                     "r_required": req,
                     "diff": None if req is None else req - r_in[j],
                     "interpretation": interpret_required(req),
                     "note": "다른 계통 조건 고정, 요구값은 확보된 성능이 아님"})
    return rows


# ---------------------------------------------------------------- 설정·입력 해석
def load_config(path=None):
    with open(path or DEFAULT_CONFIG, encoding="utf-8") as fh:
        return json.load(fh)


def resolve_inputs(config, scenario="representative", overrides=None):
    """base_inputs -> 시나리오 override -> 사용자 override 순으로 합쳐 (values, meta)를 만든다."""
    if scenario not in config["scenarios"]:
        raise InputError(f"알 수 없는 시나리오: {scenario}")
    meta = copy.deepcopy(config["base_inputs"])
    for layer, tag in ((config["scenarios"][scenario].get("overrides", {}), "시나리오 조건"),
                       (overrides or {}, "사용자 입력")):
        for k, v in layer.items():
            if k not in meta:
                raise InputError(f"알 수 없는 입력 항목: {k}")
            if isinstance(v, dict) and set(v) >= {"value", "unit"}:
                meta[k]["value"], meta[k]["unit"] = copy.deepcopy(v["value"]), v["unit"]
            else:
                meta[k]["value"] = copy.deepcopy(v)
            if tag == "사용자 입력":
                meta[k]["origin"] = "assumption"
            meta[k]["note"] = f"{meta[k]['note']} [{tag}]"
    for k, m in meta.items():
        if m["origin"] not in ORIGINS:
            raise InputError(f"{k}: origin 값 오류({m['origin']})")
    values = {k: m["value"] for k, m in meta.items()}
    return values, meta


def check_units(meta):
    for k, unit in EXPECTED_UNITS.items():
        if k in meta and meta[k]["value"] is not None and meta[k]["unit"] != unit:
            raise InputError(f"단위 불일치: {k}는 '{unit}' 이어야 하는데 '{meta[k]['unit']}' 로 입력됨 "
                             "(% 는 0~1 비율로 변환 후 입력)")


def config_hash(values):
    return hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


# ---------------------------------------------------------------- PFMEA
def load_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _quantified(row):
    v = row.get("impact_value")
    return v not in (None, "")


def analyze_pfmea(rows, values, quality_overrides=None):
    """PFMEA 행을 검증·집계한다. 확률·RPN·AP 등은 생성하지 않는다."""
    rows = [dict(r) for r in rows]
    seen = set()
    for r in rows:
        key = (r["action_id"], r["impact_parameter"])
        if key in seen:
            raise InputError(f"중복 action_id 효과: {key} (같은 효과를 두 번 반영할 수 없다)")
        seen.add(key)
        if r["accounting_location"] not in ACCT_LOCATIONS:
            raise InputError(f"{r['action_id']}: accounting_location 오류({r['accounting_location']})")
        if r["quality_status"] not in Q_STATES:
            raise InputError(f"{r['risk_id']}: 품질 상태 오류({r['quality_status']})")
        _normalize_pfmea_unit(r)
    for rid, ov in (quality_overrides or {}).items():
        if ov["status"] not in Q_STATES:
            raise InputError(f"{rid}: 품질 상태 오류({ov['status']})")
        for r in rows:
            if r["risk_id"] == rid and r["quality_status"] != ov["status"]:
                if not str(ov.get("note", "")).strip():
                    raise InputError(f"{rid}: 품질 상태 변경에는 근거 메모가 필요하다")
                r["quality_status"], r["quality_note"] = ov["status"], ov["note"]

    mode, src = values.get("p_add_mode"), values.get("added_occupancy_source")
    if mode not in ("aggregate", "itemized"):
        raise InputError(f"p_add_mode 오류: {mode}")
    if src not in ("pfmea", "input"):
        raise InputError(f"added_occupancy_source 오류: {src}")
    live = [r for r in rows if r["quality_status"] != "미충족" and r["accounting_location"] == "additional"]
    p_items = [r for r in live if r["calc_target"] == "p_add"]
    if mode == "itemized" and values.get("p_add_aggregate") is not None:
        raise InputError("P_add aggregate와 itemized가 동시에 입력됨 - 한 방식만 사용해야 한다")
    if mode == "aggregate" and any(_quantified(r) for r in p_items):
        raise InputError("aggregate 모드인데 PFMEA에 개별 P_add 효과가 정량 입력됨 - 이중 합산 위험")

    for r in rows:
        wired = (r["calc_target"] == "added_occupancy_h" and src == "pfmea") or \
                (r["calc_target"] == "p_add" and mode == "itemized")
        if r["quality_status"] == "미충족":
            r["calc_status"] = "적용 제외(품질 미충족)"
        elif r["accounting_location"] == "included_in_process":
            r["calc_status"] = "공정 값에 포함(추가 반영 안 함)"
        elif not _quantified(r):
            r["calc_status"] = "정량 부담 미확인(계산 미반영)"
        elif wired:
            r["calc_status"] = "계산 반영"
        else:
            r["calc_status"] = "수치 기록(계산 미연결: 시나리오 입력 사용)"
        # 연결 방식: 자동 반영 / 수동 반영 대상 / 계산 미연결 (품질 미충족·공정 포함은 해당 없음)
        if r["quality_status"] == "미충족" or r["accounting_location"] == "included_in_process":
            r["link_type"], r["link_note"] = LINK_EXCLUDED, ""
        elif r["calc_target"] == "none":
            r["link_type"], r["link_note"] = LINK_NONE, MANUAL_LINK_KO["none"]
        elif wired and not _quantified(r):
            r["link_type"] = LINK_AUTO_PENDING
            r["link_note"] = f"{TARGET_KO.get(r['calc_target'], r['calc_target'])}에 자동 합산 대상이나 값 미확인이라 미반영"
        elif wired:
            r["link_type"], r["link_note"] = LINK_AUTO, f"{TARGET_KO.get(r['calc_target'], r['calc_target'])}에 자동 합산"
        else:
            r["link_type"] = LINK_MANUAL
            r["link_note"] = MANUAL_LINK_KO.get(r["calc_target"], f"{r['calc_target']} 입력으로 수동 검토")

    added = [r for r in live if r["calc_target"] == "added_occupancy_h"]
    added_q = [r for r in added if _quantified(r)]
    p_q = [r for r in p_items if _quantified(r)]
    risk_q = risk_quality(rows)
    return {
        "rows": rows,
        "added_occupancy_pfmea_h": sum(r["impact_value"] for r in added_q) if added_q else None,
        "added_occupancy_unquantified": [r["action_id"] for r in added if not _quantified(r)],
        "p_add_itemized_pt": sum(r["impact_value"] for r in p_q) if p_q else None,
        "p_add_unquantified": [r["action_id"] for r in p_items if not _quantified(r)],
        "risk_quality": risk_q,
        "quality_overall": quality_overall(rows),
        "unmet_risks": [rid for rid, s in risk_q.items() if s == "미충족"],
        "manual_pending": [r["action_id"] for r in rows if r["link_type"] == LINK_MANUAL],
        "auto_linked": [r["action_id"] for r in rows if r["link_type"] == LINK_AUTO and r["calc_status"] == "계산 반영"],
        "counts": {
            "risks": len(risk_q),
            "reflected": sum(r["calc_status"] == "계산 반영" for r in rows),
            "burden_unknown": sum(r["calc_status"].startswith("정량 부담 미확인") for r in rows),
            "quality_open": sum(s in ("미확인", "검증 중") for s in risk_q.values()),
            "excluded": sum(s == "미충족" for s in risk_q.values()),
            "manual_pending": sum(r["link_type"] == LINK_MANUAL for r in rows),
        },
    }


def _normalize_pfmea_unit(r):
    """impact_value를 내부 단위로 변환한다. 허용되지 않은 단위는 차단 (15 min을 15 h로 계산하지 않음)."""
    dim = PFMEA_DIMENSION.get(r["impact_parameter"]) or PFMEA_TARGET_DIMENSION.get(r["calc_target"])
    unit = str(r.get("impact_unit") or "").strip()
    r["impact_unit_input"] = unit
    if not _quantified(r):
        if dim and unit and unit not in PFMEA_UNITS[dim][1]:
            raise InputError(f"{r['action_id']}: 단위 '{unit}'는 {r['impact_parameter']}에 허용되지 않음 "
                             f"(허용: {', '.join(PFMEA_UNITS[dim][1])})")
        if dim:
            r["impact_unit"] = PFMEA_UNITS[dim][0]
        return
    try:
        val = float(r["impact_value"])
    except (TypeError, ValueError):
        raise InputError(f"{r['action_id']}: impact_value가 숫자가 아님({r['impact_value']!r})") from None
    if not math.isfinite(val):
        raise InputError(f"{r['action_id']}: impact_value가 유한한 숫자가 아님")
    if dim is None:
        raise InputError(f"{r['action_id']}: {r['impact_parameter']}의 단위 차원이 정의되지 않아 정량값을 쓸 수 없음")
    canon, table = PFMEA_UNITS[dim]
    if unit not in table:
        raise InputError(f"{r['action_id']}: 단위 '{unit or '(없음)'}'는 {r['impact_parameter']}에 허용되지 않음 "
                         f"(허용: {', '.join(table)})")
    if val < 0:
        raise InputError(f"{r['action_id']}: 관리 부담 값은 음수일 수 없다")
    r["impact_value"], r["impact_unit"] = val * table[unit], canon


def _combine_quality(states):
    """여러 조치·위험의 품질 상태를 하나로 집계한다. 미충족이 하나라도 있으면 미충족."""
    st = list(states)
    if not st:
        return "미확인"
    if "미충족" in st:
        return "미충족"
    if all(s == "충족" for s in st):
        return "충족"
    if any(s in ("검증 중", "충족") for s in st):
        return "검증 중"
    return "미확인"


def risk_quality(rows):
    """위험 경로별 품질 상태. 첫 행만 쓰지 않고 해당 위험의 모든 조치를 집계한다."""
    by = {}
    for r in rows:
        by.setdefault(r["risk_id"], []).append(r["quality_status"])
    return {rid: _combine_quality(s) for rid, s in by.items()}


def quality_overall(rows):
    return _combine_quality(risk_quality(rows).values())


def resolve_added_occupancy(values, pf):
    if values["added_occupancy_source"] == "input":
        v = values.get("added_occupancy_h")
        return (v, None) if v is not None else (None, ["added_occupancy_h"])
    v = pf["added_occupancy_pfmea_h"] if pf else None
    if v is None:
        return None, ["PFMEA 추가 점유 효과"]
    return v, None


def apply_occupancy_lower_bound(fm, values, pf):
    """PFMEA 추가 점유 중 시간이 미확인인 조치가 있으면, 알려진 합계는 하한이다.

    처리능력은 점유시간이 늘수록 줄어들므로 하한 기준 '미달'은 확정 미달이지만,
    하한 기준 '충족'은 확정할 수 없어 '계산 보류'로 바꾼다. 수치는 상한값으로 남긴다.
    """
    if not pf or values.get("added_occupancy_source") != "pfmea":
        return fm
    unq = pf.get("added_occupancy_unquantified") or []
    if not unq or fm.get("status") not in (NUM_OK, NUM_FAIL):
        return fm
    fm = dict(fm)
    fm["occupancy_lower_bound"] = True
    fm["unquantified_actions"] = list(unq)
    fm["capacity_is_upper_bound"] = True
    if fm["status"] == NUM_OK:
        fm["status"] = NUM_HOLD
        fm["missing"] = list(unq)
        fm["reason"] = (f"추가 점유 시간 미확인 조치 {unq} - 알려진 값은 하한이며 처리능력은 상한값. "
                        "전체 부담 확인 전 충족 판정 보류")
    else:
        fm["reason"] = f"추가 점유 하한만으로도 목표 미달 (미확인 조치 {unq}를 더하면 더 낮아짐)"
    return fm


def _formation_shown(fm):
    """처리능력 수치를 표시할 수 있는 상태 (확정 충족·미달 또는 하한 기준 보류)."""
    return fm["status"] in (NUM_OK, NUM_FAIL) or bool(fm.get("occupancy_lower_bound"))


def resolve_p_add(values, pf):
    mode = values["p_add_mode"]
    if mode == "aggregate":
        v = values.get("p_add_aggregate")
        return {"mode": mode, "value": v, "complete": v is not None,
                "note": "대표 가정(총 추가 관리부하)" if v is not None else "미확인"}
    unq = pf["p_add_unquantified"] if pf else []
    v = pf["p_add_itemized_pt"] if pf else None
    if unq or v is None:
        return {"mode": mode, "value": None, "complete": False, "lower_bound": v,
                "note": f"정량 미확인 항목 {unq} - 합계를 확정할 수 없어 계산 보류"}
    return {"mode": mode, "value": v, "complete": True, "note": "PFMEA 개별 전력 효과 합계"}


# ---------------------------------------------------------------- 시나리오 실행
def build_comparison(values, r_eff, p_add):
    """과제 표의 비교 조건. 바꾸지 않은 입력은 시나리오와 동일하게 유지한다."""
    rows = []
    for cid, label, fh, add, ch, origin in FORMATION_CONDITIONS:
        res = _safe(formation_capacity, fh, add, ch, values["availability_ratio"], values["yield_ratio"],
                    values["baseline_formation_h"], values["target_capacity_ratio"])
        rows.append({"id": cid, "group": "화성", "condition": label, "basis": origin,
                     "formation_h": fh, "added_occupancy_h": add, "channel_ratio": ch,
                     "capacity_ratio": res.get("capacity_ratio"), "status": res["status"],
                     "E_total": None, "saving_ratio": None, "gap": None})
    q, w, f = values["q"], values["w"], values["f"]
    p2 = 2.0
    plants = [("E0", "증산만 적용(절감 없음)", "기준", [0] * 5, f, 0.0),
              ("E1", "P_add=0 (관리 전력 제외)", "비교", r_eff, f, 0.0),
              ("E2", "P_add=2 (관리 전력 포함)", "가정 기반", r_eff, f, p2),
              ("E3", "모든 f=0 (비례 부하 민감도)", "민감도", r_eff, [0] * 5, p2)]
    for cid, label, basis, r, ff, pa in plants:
        res = _safe(plant_energy, w, ff, r, q, pa, "pt", values["target_intensity_ratio"])
        rows.append({"id": cid, "group": "공장 전력", "condition": label, "basis": basis,
                     "formation_h": None, "added_occupancy_h": None, "channel_ratio": None,
                     "capacity_ratio": None, "status": res["status"], "E_total": res.get("E_total"),
                     "saving_ratio": res.get("saving_ratio"), "gap": res.get("gap")})
    return rows


def run_scenario(config, scenario="representative", overrides=None, pfmea_rows=None,
                 quality_overrides=None):
    values, meta = resolve_inputs(config, scenario, overrides)
    res = {"scenario": scenario, "scenario_label": config["scenarios"][scenario]["label_ko"],
           "inputs": values, "meta": meta, "warnings": [], "config_hash": config_hash(values)}
    try:
        check_units(meta)
    except InputError as e:
        res["blocked"] = str(e)
        res["warnings"].append(str(e))
        return res
    rows = pfmea_rows if pfmea_rows is not None else load_csv(DEFAULT_PFMEA)

    pf, pf_err = None, None
    try:
        pf = analyze_pfmea(rows, values, quality_overrides)
    except InputError as e:
        pf_err = str(e)
        res["warnings"].append(f"PFMEA: {pf_err}")
    res["pfmea"] = pf if pf else {"status": NUM_ERR, "error": pf_err, "rows": [],
                                  "quality_overall": "미확인", "counts": {}}

    added_h, added_missing = (None, ["PFMEA 오류"]) if pf_err else resolve_added_occupancy(values, pf)
    res["added_occupancy_h"] = added_h
    res["formation"] = _hold(added_missing) if added_missing else _safe(
        formation_capacity, values["formation_h"], added_h, values["channel_ratio"],
        values["availability_ratio"], values["yield_ratio"], values["baseline_formation_h"],
        values["target_capacity_ratio"], values["baseline_channels"])
    res["formation"] = apply_occupancy_lower_bound(res["formation"], values, pf)
    res["added_occupancy_lower_bound"] = bool(res["formation"].get("occupancy_lower_bound"))
    res["aging"] = _safe(aging_slots, values["q"], values["current_utilization"],
                         values["planned_utilization"], values["old_throughput_per_day"],
                         values["old_wait_days"], values["new_throughput_per_day"],
                         values["new_wait_days"], values["area_per_cell"], values["slots_per_area"],
                         values["conversion_fraction"], values.get("aging_zones"))
    da = values["drying_a"]
    res["drying_a"] = _safe(drying_mode_a, da["a"], da["s"], da["b"], da["cop_h"], da["cop_c"])
    res["drying_b"] = _safe(drying_mode_b, values["drying_b_zones"], values["drying_b_global"],
                            meta["drying_b_global"]["unit"])
    for w in res["drying_b"].get("warnings", []):
        res["warnings"].append(f"건조 모드 B: {w}")

    # 공장 모델: 건조 절감률 출처는 하나만 (이중 계산 방지)
    src = values["drying_r_source"]
    r_eff = list(values["r"])
    drying_src_status = None
    try:
        scope = values.get("drying_a_airflow_scope", "system")
        if scope not in DRYING_SCOPES:
            raise InputError(f"drying_a_airflow_scope 오류: {scope} (system 또는 zone)")
        # 모드 A의 풍량 감소가 특정 구간 값(zone)인데 건조 계통 전체 절감률로 쓰이면 중복 적용으로 차단한다.
        validate_accounting([src], {"accounting": values["regen_accounting"],
                                    "independent_pt": values["regen_independent_pt"],
                                    "usable": values["regen_usable"]},
                            zone_savings_applied_globally=(src == "mode_a" and scope == "zone"))
        if src == "mode_a":
            r_eff[0] = res["drying_a"].get("saving_ratio")
        elif src == "mode_b":
            r_eff[0] = res["drying_b"].get("saving_ratio")
        if r_eff[0] is None:
            drying_src_status = f"건조 {src} 결과가 {res['drying_a' if src == 'mode_a' else 'drying_b']['status']}"
    except InputError as e:
        drying_src_status = str(e)
        r_eff[0] = None
        res["warnings"].append(drying_src_status)
    res["r_effective"] = r_eff
    res["drying_r_source"] = src

    p_info = resolve_p_add(values, pf) if pf else {"mode": values["p_add_mode"], "value": None,
                                                    "complete": False, "note": "PFMEA 오류"}
    res["p_add"] = p_info
    regen_pt = values["regen_independent_pt"] if values["regen_accounting"] == "independent" else 0.0
    if drying_src_status:
        res["plant"] = _hold(["건조 절감률"], drying_src_status) if "결과가" in drying_src_status \
            else _err(drying_src_status)
    else:
        res["plant"] = _safe(plant_energy, values["w"], values["f"], r_eff, values["q"], p_info["value"],
                             "pt", values["target_intensity_ratio"], regen_pt or 0.0)
    if res["plant"]["status"] in (NUM_OK, NUM_FAIL):
        res["reverse"] = reverse_requirements(res["plant"], r_eff)
    else:
        res["reverse"] = []
    comp_r = r_eff if r_eff[0] is not None else None
    res["comparison"] = build_comparison(values, comp_r, p_info["value"]) if comp_r else []

    res["before_after"] = build_before_after(res, values)
    res["quality_status"] = res["pfmea"].get("quality_overall", "미확인")
    res["requirements"] = requirement_rows(res)
    res["kpi"] = build_kpi(res)
    res["conclusion"] = build_conclusion(res)
    res["evidence"] = run_evidence(values)
    res["calculation_mode"] = (f"건조 절감률 출처={KEY_KO[src]} (모드 A 참고값 {fmt_pct(res['drying_a'].get('saving_ratio'), 2)} "
                               f"[{drying_a_condition(values['drying_a'])}; 건조 {fmt_pct(values['r'][0], 0)} 수동 입력과 다른 값], "
                               f"모드 B {res['drying_b']['status']}); P_add 집계={KEY_KO.get(p_info['mode'], p_info['mode'])}; "
                               f"추가 점유 출처={KEY_KO[values['added_occupancy_source']]}")
    for k in ("formation", "plant", "drying_b"):
        if res[k]["status"] == NUM_ERR:
            res["warnings"].append(f"{k}: {res[k]['error']}")
    return res


def run_evidence(values, kb_dir=None):
    """근거 FMEA 데이터셋 기반 자동 판정 (evidence_engine). 데이터셋 오류는 계산 전체를 막지 않고 상태로 남긴다."""
    try:
        import evidence_engine as ee
        ev = ee.evaluate(values, kb_dir=kb_dir)
        ev["status"] = NUM_OK
        ev["conclusion"] = ee.conclusion(ev)
        return ev
    except (InputError, ValueError, FileNotFoundError, KeyError) as e:
        return {"status": NUM_ERR, "error": f"근거 판정 불가: {e}"}


def drying_a_condition(da):
    """모드 A 적용 조건 표시 문자열 (표시 전용)."""
    d = (da["a"] - 1.0) * 100
    air = "풍량 변화 없음" if abs(d) < 1e-9 else f"풍량 {d:+.0f}%".replace("+", "+")
    return f"{air}, s={da['s']:g}, COP_h={da['cop_h']:g}, COP_c={da['cop_c']:g}, b={da['b']:g}"


def requirement_rows(res):
    """보완 요구 사양 표 (UI·CSV·PDF 공용). 요구값은 확보된 성능이 아니다."""
    v, rows = res["inputs"], []
    sup = _safe(formation_capacity, 16.0, 2.0, v["channel_ratio"], v["availability_ratio"], v["yield_ratio"],
                v["baseline_formation_h"], v["target_capacity_ratio"])
    fm = res["formation"]
    if sup["status"] in (NUM_OK, NUM_FAIL):
        rows.append({"item": "화성 채널 보완(16h+2h 비교 가정)", "current": v["channel_ratio"],
                     "required": sup["required_channel_ratio"], "unit": "채널비",
                     "note": "추가 점유 2h가 현장 측정값이라는 뜻이 아니라 비교 가정"})
    if _formation_shown(fm):
        lb = fm.get("occupancy_lower_bound")
        rows.append({"item": "화성 허용 추가 점유(현재 채널비)", "current": res["added_occupancy_h"],
                     "required": fm["allowed_added_h"], "unit": "h",
                     "note": ("현재 입력은 하한(미확인 조치 " + ", ".join(fm["unquantified_actions"]) + " 제외). "
                              if lb else "") + "음수면 추가 점유 없이도 목표 미달(0으로 바꾸지 않음)"})
    ag = res["aging"]
    if ag["status"] == NUM_OK:
        rows.append({"item": "에이징 추가 슬롯비(14일 유지)", "current": 0.0,
                     "required": ag["additional_slot_ratio"], "unit": "비율",
                     "note": "q·현재 사용률/계획 사용률. 대기공간 전환은 조건부"})
        for z in ag["zones"]:
            rows.append({"item": f"에이징 {z['name']} 추가 슬롯비", "current": 0.0,
                         "required": z["additional_slot_ratio"], "unit": "비율",
                         "note": f"구역별 계산. 공간: {z['space_status']}"})
    for x in res["reverse"]:
        if x["system"] in ("건조", "드라이룸", "기타"):
            rows.append({"item": f"{x['system']} 요구 절감률(단독 보완)", "current": x["r_input"],
                         "required": x["r_required"], "unit": "비율", "note": x["interpretation"]})
    return rows


def build_before_after(res, values):
    """관리조치 전·후·보완 요구 비교 (바꾸지 않은 입력은 동일 유지)."""
    rows = []
    r_eff, q, w, f = res["r_effective"], values["q"], values["w"], values["f"]
    if r_eff[0] is None or res["plant"]["status"] not in (NUM_OK, NUM_FAIL):
        return rows
    tgt = values["target_intensity_ratio"]
    p_after = res["p_add"]["value"]
    pe = plant_energy(w, f, [0] * 5, q, 0.0, "pt", tgt)
    pb = plant_energy(w, f, r_eff, q, 0.0, "pt", tgt)
    fm_before = _safe(formation_capacity, values["formation_h"], 0.0, values["channel_ratio"],
                      values["availability_ratio"], values["yield_ratio"], values["baseline_formation_h"],
                      values["target_capacity_ratio"])
    fa = res["formation"]
    rows.append({"stage": "증산만 적용(절감 없음)", "capacity_ratio": 1.0, "E_total": pe["E_total"],
                 "saving_ratio": pe["saving_ratio"], "gap": pe["gap"],
                 "note": "기존 20h 화성 · 관리조치 없음"})
    rows.append({"stage": "공정 개선만(관리조치 전)", "capacity_ratio": fm_before.get("capacity_ratio"),
                 "E_total": pb["E_total"], "saving_ratio": pb["saving_ratio"], "gap": pb["gap"],
                 "note": "추가 점유 0h · P_add=0"})
    if fa.get("capacity_ratio") is not None and p_after is not None:
        pa = res["plant"]
        occ = (f"추가 점유 ≥{res['added_occupancy_h']:.2f}h(하한, 처리능력은 상한값)"
               if fa.get("occupancy_lower_bound") else f"추가 점유 {res['added_occupancy_h']:.2f}h")
        rows.append({"stage": "관리조치 반영 후", "capacity_ratio": fa["capacity_ratio"],
                     "E_total": pa["E_total"], "saving_ratio": pa["saving_ratio"], "gap": pa["gap"],
                     "note": f"{occ} · P_add={p_after:.2f}pt"})
    return rows


def build_kpi(res):
    fm, pl = res["formation"], res["plant"]
    k = []
    if fm["status"] in (NUM_OK, NUM_FAIL) and not fm.get("occupancy_lower_bound"):
        k.append({"title": "화성 처리능력", "value": f"{fm['capacity_ratio']:.3f}배",
                  "sub": f"목표 1.2배 {fm['status']} · 화성 단독(전체 공장 능력 미확인)",
                  "label": "목표 사양"})
    elif fm.get("occupancy_lower_bound"):
        k.append({"title": "화성 처리능력", "value": f"≤{fm['capacity_ratio']:.3f}배",
                  "sub": (f"목표 1.2배 {fm['status']} · 추가 점유 미확인 조치 {len(fm['unquantified_actions'])}건 "
                          "(상한값, 화성 단독)"),
                  "label": "검증 필요"})
    else:
        k.append({"title": "화성 처리능력", "value": fm["status"], "sub": fm.get("reason") or fm.get("error", ""),
                  "label": "검증 필요"})
    if pl["status"] in (NUM_OK, NUM_FAIL):
        k.append({"title": "전력 원단위 절감", "value": fmt_pct(pl["saving_ratio"], 2),
                  "sub": f"목표 {fmt_pct(pl['target_saving_ratio'], 0)} {pl['status']} · E={pl['E_total']:.2f}",
                  "label": "가정 기반"})
        k.append({"title": "목표까지의 격차", "value": f"{pl['gap']:+.2f} pt",
                  "sub": f"목표 전력 {pl['target_energy']:.2f} 대비(기준 전력 100)", "label": "과제 조건"})
    else:
        k.append({"title": "전력 원단위 절감", "value": pl["status"], "sub": pl.get("reason") or pl.get("error", ""),
                  "label": "검증 필요"})
        k.append({"title": "목표까지의 격차", "value": pl["status"], "sub": "-", "label": "검증 필요"})
    c = res["pfmea"].get("counts", {})
    unmet = res["pfmea"].get("unmet_risks", [])
    k.append({"title": "품질 확인 상태", "value": res["quality_status"],
              "sub": (f"품질 미충족 위험 {', '.join(unmet)} - 현재 조건 적용 제외" if unmet else
                      f"위험 경로 {c.get('risks', 0)}건 중 확인 필요 {c.get('quality_open', 0)}건"),
              "label": "검증 필요"})
    return k


def build_conclusion(res):
    fm, pl = res["formation"], res["plant"]
    pf = res.get("pfmea", {})
    unmet = pf.get("unmet_risks", [])
    s = []
    # 1) 품질 미충족이 있으면 수치와 무관하게 해당 전환안은 현재 조건에서 적용 제외
    if unmet:
        s.append(f"품질 미충족 위험 경로({', '.join(unmet)})의 관리조치가 필요한 전환안이므로, 이 조건"
                 f"({res['scenario_label']})의 전환안은 현재 조건에서 적용 제외로 판정한다. 아래 수치는 참고용이다.")
    fm_ok = _formation_shown(fm)
    if fm_ok and pl["status"] in (NUM_OK, NUM_FAIL):
        if fm.get("occupancy_lower_bound"):
            cap = (f"화성 처리능력은 최대 {fm['capacity_ratio']:.3f}배(추가 점유 미확인 조치 "
                   f"{', '.join(fm['unquantified_actions'])} 제외한 상한값)로 목표 1.2배 "
                   + ("미달이 확정이고" if fm["status"] == NUM_FAIL else "충족 여부는 보류이고"))
        else:
            cap = f"화성 처리능력은 {fm['capacity_ratio']:.3f}배로 목표 1.2배에 {fm['status']}이고"
        s.append(f"이 조건({res['scenario_label']})에서 {cap}, 공장 원단위 절감은 {pl['saving_ratio'] * 100:.2f}%로 목표 "
                 f"{pl['target_saving_ratio'] * 100:.0f}%에 {pl['status']}(격차 {pl['gap']:+.2f} pt)이다.")
        if pl.get("increase_systems"):
            s.append(f"{', '.join(pl['increase_systems'])} 계통은 변경안에서 전력이 증가하는 조건(전력 증가·목표 미달 요인)이다.")
        need = {x["system"]: x["r_required"] for x in res["reverse"]}
        if pl["status"] == NUM_FAIL:
            def _req(x):
                if x is None:
                    return "역산 불가"
                return f"{fmt_pct_up(x)}(단독 보완 불가)" if x > 1 else fmt_pct_up(x)
            s.append(f"같은 조건에서 목표 도달에 필요한 보완 요구 사양은 건조 {_req(need['건조'])}, "
                     f"드라이룸 {_req(need['드라이룸'])} 또는 기타 {_req(need['기타'])} 절감이며, "
                     "이는 확보된 성능이 아니라 가정 기반의 요구값이다.")
        else:
            s.append("수치 목표는 입력 가정 하에서 충족되지만 확보된 성능이 아니라 가정 기반 결과이다.")
    else:
        s.append(f"일부 계산이 완료되지 않았다(화성: {fm['status']}, 공장 전력: {pl['status']}).")
        s.append("필수 입력이 확인될 때까지 해당 결론은 보류한다.")
    # 2) PFMEA 연결 범위: 자동 반영과 수동 반영 대상을 구분해 미반영 사실을 남긴다
    auto, manual = pf.get("auto_linked", []), pf.get("manual_pending", [])
    if pf.get("rows"):
        msg = f"PFMEA 관리조치 중 계산에 자동 반영된 효과는 {len(auto)}건"
        msg += f"({', '.join(auto)})" if auto else ""
        if manual:
            msg += (f"이며, {len(manual)}건({', '.join(manual)})은 자동 연결되지 않아 해당 시나리오 입력으로 "
                    "수동 검토해야 하는 미반영 항목이다.")
        else:
            msg += "이다."
        s.append(msg)
    # 3) 품질 상태 해석
    if not unmet:
        s.append(f"품질 상태는 '{res['quality_status']}'이므로 수치 충족 여부와 무관하게 현장 적용 완료가 아니라 "
                 "검증 후보 또는 조건부 결과로만 해석해야 한다." if res["quality_status"] != "충족" else
                 "품질 상태는 '충족'으로 기록되었으나 입력 근거 메모의 범위 안에서만 유효하다.")
    return " ".join(s)


# ---------------------------------------------------------------- 그래프용 데이터 (최대 5,000 격자)
MAX_GRID = 5000


def _check_grid(n):
    if n > MAX_GRID:
        raise InputError(f"격자 계산 {n}개가 한도 {MAX_GRID}개를 초과")


def formation_boundary_data(values):
    import numpy as np
    xs = np.round(np.arange(14.0, 20.0001, 0.1), 6)
    chans = (1.00, 1.08)
    _check_grid(len(xs) * len(chans))
    base, tgt = values["baseline_formation_h"], values["target_capacity_ratio"]
    av, yd = values["availability_ratio"], values["yield_ratio"]
    out = []
    for ch in chans:
        for x in xs:
            out.append({"channel_ratio": ch, "formation_h": float(x),
                        "allowed_added_h": base * ch * av * yd / tgt - float(x)})
    return out


def energy_boundary_data(values, r_eff=None, p_adds=None):
    import numpy as np
    xs = np.round(np.arange(0.0, 0.6001, 0.01), 6)
    p_adds = p_adds or [0.0, values["p_add_aggregate"] if values["p_add_aggregate"] is not None else 2.0]
    _check_grid(len(xs) * len(p_adds))
    r = list(r_eff or values["r"])
    w, f, q, tgt = values["w"], values["f"], values["q"], values["target_intensity_ratio"]
    out = []
    for pa in p_adds:
        for x in xs:
            rr = list(r)
            rr[1] = float(x)
            p = plant_energy(w, f, rr, q, pa, "pt", tgt)
            others = sum(p["E"]) - p["E"][0]
            out.append({"P_add": pa, "r_dryroom": float(x),
                        "r_drying_required": required_reduction(others, pa, p["target_energy"], p["B"][0])})
    return out


# ---------------------------------------------------------------- 자체 검산
def self_check():
    """대표 검산값 회귀 확인 (실제 계산 결과를 반환)."""
    items = []

    def add(name, expected, actual, tol=1e-6):
        items.append({"name": name, "expected": expected, "actual": actual,
                      "pass": abs(expected - actual) <= tol})

    mk = lambda fh, ad, ch: formation_capacity(fh, ad, ch, 1.0, 1.0)
    add("화성 16h+0.25h 처리능력", 1.2307692308, mk(16, 0.25, 1.0)["capacity_ratio"], 1e-9)
    add("화성 16h+2h 처리능력", 1.1111111111, mk(16, 2, 1.0)["capacity_ratio"], 1e-9)
    add("화성 16h+2h 채널 1.08", 1.2, mk(16, 2, 1.08)["capacity_ratio"], 1e-9)
    add("허용 추가 점유(16h) [h]", 0.6666666667, mk(16, 0.25, 1.0)["allowed_added_h"], 1e-9)
    add("에이징 추가 슬롯비", 0.1368421053, aging_slots(1.2, 0.9, 0.95)["additional_slot_ratio"], 1e-9)
    add("팬 0.9^3", 0.729, 0.9 ** 3, 1e-12)
    add("건조 A 케이스1 절감률", 0.30795, drying_mode_a(1.0, 0.7, 0.52, 3.85, 3.0)["saving_ratio"], 5e-6)
    add("건조 A 케이스2 절감률", 0.42204, drying_mode_a(0.8, 0.7, 0.52, 3.85, 3.0)["saving_ratio"], 5e-6)
    w, f = [35, 25, 10, 5, 25], [0.2, 0.8, 0.1, 0.7, 0.5]
    add("증산만 총전력", 111.2, plant_energy(w, f, [0] * 5, 1.2, 0)["E_total"], 1e-9)
    p = plant_energy(w, f, [0.4, 0.3, 0.3, 0, 0], 1.2, 2)
    add("대표 총전력", 85.62, p["E_total"], 1e-9)
    add("대표 절감률", 0.2865, p["saving_ratio"], 1e-9)
    add("P_add=0 총전력", 83.62, plant_energy(w, f, [0.4, 0.3, 0.3, 0, 0], 1.2, 0)["E_total"], 1e-9)
    req = {x["system"]: x["r_required"] for x in reverse_requirements(p, [0.4, 0.3, 0.3, 0, 0])}
    add("요구 절감률 건조", 0.4399014778, req["건조"], 1e-9)
    add("요구 절감률 드라이룸", 0.3623076923, req["드라이룸"], 1e-9)
    add("요구 절감률 기타", 0.0589090909, req["기타"], 1e-9)
    return items


# ---------------------------------------------------------------- PFMEA 요약표 (UI·PDF 공용)
def pfmea_table(res):
    """위험 경로(risk_id)별 6열 요약. 전체 필드는 pfmea_summary.csv에 저장한다."""
    by = {}
    for r in res.get("pfmea", {}).get("rows", []):
        by.setdefault(r["risk_id"], []).append(r)

    def one(x):
        val = (f"{float(x['impact_value']):g} {x['impact_unit']}" if x["impact_value"] not in ("", None)
               else f"미확인 ({x['impact_unit']})")
        link = x.get("link_type")
        tag = f" ({link})" if link and link != LINK_EXCLUDED else ""
        return (f"{PARAM_KO.get(x['impact_parameter'], x['impact_parameter'])} {val} → "
                f"{TARGET_KO.get(x['calc_target'], x['calc_target'])} [{x['calc_status']}]{tag}")

    rq = res.get("pfmea", {}).get("risk_quality") or {}
    out = []
    for rid, rs in by.items():
        st = rq.get(rid) or _combine_quality(x["quality_status"] for x in rs)
        mixed = len({x["quality_status"] for x in rs}) > 1
        detail = (" (조치별: " + ", ".join(f"{x['action_id']} {x['quality_status']}" for x in rs) + ")") if mixed else ""
        out.append({"risk_id": rid, "공정 변경": f"{rid} {rs[0]['process_change']}", "실패 경로": rs[0]["failure_path"],
                    "관리조치": "; ".join(dict.fromkeys(x["control_action"] for x in rs)),
                    "계산 영향": "\n".join(one(x) for x in rs),
                    "확인 상태": f"품질 {st}{detail}" + (" · 적용 제외" if st == "미충족" else ""),
                    "다음 검증": "; ".join(dict.fromkeys(x["next_check"] for x in rs)), "rows": rs,
                    "quality": st})
    return out
