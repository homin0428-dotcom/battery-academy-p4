"""근거 FMEA 데이터셋(지식베이스) 스키마 - 단일 정의.

엑셀 입력 템플릿 생성(tools/make_kb_template.py), 가져오기·검증(kb_import.py),
자동 판정 엔진(evidence_engine.py)이 모두 이 정의만 사용한다.

데이터셋 구성
  sources   : 근거 자료 목록 (논문·리뷰·보고서·기술자료·과제 출제서)
  levers    : 공정 변경 레버 목록 (어느 계통에 작용하는지, 중복 방지 그룹)
  effects   : 정량 효과 근거 - 레버 1개 × 지표 1개 × 근거 1건 = 1행
  fmea      : 근거 FMEA - 레버별 고장모드·관리조치와 그 관리 부담(시간·전력·채널)

설계 원칙
  * 수치 1개는 반드시 근거 1건(source_id + 위치)에 연결한다. 근거 없는 수치는 등급 E(팀 가정)로만 허용.
  * 점수·확률(RPN/AP/CEI 등)은 만들지 않는다. 근거 등급과 적용 조건 일치는 범주로만 표시한다.
  * 같은 중복 방지 그룹(exclusive_group)의 레버는 곱하지 않는다 (같은 절감을 두 번 세지 않음).
"""
from __future__ import annotations

SYSTEMS = ["건조", "드라이룸", "화성", "에이징", "기타"]   # core.SYSTEMS 와 같은 순서

# ------------------------------------------------------------------ 범주 값
EVIDENCE_GRADES = {
    "A": "산업 규모(GWh급 양산) 실측·운영 데이터",
    "B": "파일럿·실험 실측 (같은 계열 셀·공정)",
    "C": "공정 모델·시뮬레이션·설계 추정치",
    "D": "리뷰·2차 인용 또는 다른 셀·다른 산업 사례",
    "E": "팀 가정·전문가 판단 (출처 수치 없음)",
}
GRADE_ORDER = "ABCDE"   # 앞일수록 강한 근거

VERIFICATION = {
    "원문 확인": "원문을 직접 읽고 쪽·그림·표 위치를 기재함",
    "초록 확인": "초록·요약만 확인함 (본문 수치 미확인)",
    "2차 인용": "다른 문헌·자료가 인용한 값을 옮김",
    "미확인": "아직 확인하지 않음",
}

# 측정 범위(경계): 문헌 수치가 '무엇 대비' 값인지. 계통 절감률로 바꾸는 방법이 달라진다.
BOUNDARY = {
    "계통전체": "해당 계통(건조·드라이룸 등) 전체 에너지 대비 → 그대로 사용",
    "공장전체": "셀 공장 전체 생산 에너지 대비 → 계통 비중으로 나눠 환산 (비중: 경계비중 열 → KB 비중 근거 → 과제 비중 순)",
    "계통일부": "계통의 일부(예: NMP 증발 에너지만) 대비 → 경계비중(계통 중 그 부분의 비율)을 곱해 환산. 비중 없으면 참고 전용",
    "복합계통": "여러 계통 합산(예: 건조+드라이룸 열부하) 대비 → 계통별로 나눌 수 없어 참고 전용",
    "장비단위": "장비·셀 몇 개 수준의 값(예: 충방전기 효율) → 공장 절감률로 쓰지 않고 참고 전용",
}

# 에너지 종류: 과제 목표는 '전력' 원단위. 열(가스·증기)이 섞인 수치는 그대로 전력 절감으로 쓰면 틀린다.
ENERGY_CARRIER = {
    "전력": "전기 에너지만",
    "열": "열 에너지만 (가스·증기·열부하 kWth). 해당 계통 가열이 전기식일 때만 전력 절감으로 인정",
    "합산": "전력+열 합산 (최종 에너지). 해당 계통 가열이 전기식일 때만 조건부로 인정",
    "1차에너지": "1차 에너지(발전 손실 포함) 기준 → 전력 절감률로 직접 쓰지 않고 참고 전용",
    "무관": "에너지 지표가 아님 (시간·비율 등)",
}
CHANGE_TYPES = {
    "운영변경": "레시피·운전 조건·관리 방식 변경 (설비 그대로) → 1년차 적용 후보",
    "설비개조": "기존 설비에 모듈·회수 장치 추가, 부분 개조 → 2년차 적용 후보",
    "설비교체": "주요 설비 교체 → 2~3년차",
    "공정전환": "공정 자체 변경 (예: 건식 전극) → 장기",
}

CHEMISTRY = ["NCM", "NCA", "LFP", "LMO", "기타", "무관"]
CELL_FORMAT = ["파우치", "각형", "원통형", "기타", "무관"]
SCALE = ["양산", "파일럿", "실험실", "모델", "무관"]
SOURCE_TYPES = ["논문", "리뷰", "보고서", "기술자료", "과제", "기타"]
ACCESS = ["원문", "초록", "2차"]
AFFECTED = ["품질", "시간", "전력", "공간", "안전"]

# ------------------------------------------------------------------ 지표 정의
# kind: direct = value_low/typ/high 직접 입력, pair = 개선 전·후 값(value_before/value_after)에서 계산
# derives: pair 지표가 계산해 내는 지표
METRICS = {
    "system_saving_ratio": {
        "ko": "해당 계통 전력 절감률", "kind": "direct", "units": {"ratio": 1.0, "%": 0.01},
        "canon": "ratio", "lo": -1.0, "hi": 1.0, "role": "saving",
        "help": "레버를 적용했을 때 해당 계통(건조·드라이룸·화성 등) 전력이 줄어드는 비율. 30% 절감 = 0.30",
    },
    "energy_before_after": {
        "ko": "개선 전·후 에너지(절감률 자동 계산)", "kind": "pair", "derives": "system_saving_ratio",
        "units": {"kWh/kWh_cell": 1.0, "MJ/kWh_cell": 1.0, "kWh/m2": 1.0, "kWh/kg": 1.0, "kW": 1.0, "MW": 1.0,
                  "kWh": 1.0, "MWh": 1.0, "GJ": 1.0}, "canon": None, "role": "saving",
        "help": "논문이 개선 전·후 에너지 값을 주는 경우. 절감률 = 1 - 후/전 으로 자동 계산 (같은 단위·같은 기준이어야 함)",
    },
    "formation_time_ratio": {
        "ko": "화성시간 비(변경/기존)", "kind": "direct", "units": {"ratio": 1.0, "%": 0.01},
        "canon": "ratio", "lo": 0.0, "hi": 2.0, "role": "time",
        "help": "변경 프로토콜 화성시간 ÷ 기존 프로토콜 화성시간. 20h→16h 이면 0.80",
    },
    "time_before_after": {
        "ko": "개선 전·후 화성시간(비율 자동 계산)", "kind": "pair", "derives": "formation_time_ratio",
        "units": {"h": 1.0, "min": 1 / 60, "day": 24.0}, "canon": "h", "role": "time",
        "help": "논문이 기존·변경 화성시간을 주는 경우. 비율 = 후/전",
    },
    "cop_h": {
        "ko": "난방 COP", "kind": "direct", "units": {"-": 1.0}, "canon": "-", "lo": 1.0, "hi": 10.0,
        "role": "param", "help": "히트펌프 난방 성적계수 (공급열/소비전력). 통합 성능지표(COP_sys 등)와 섞지 말 것",
    },
    "regen_efficiency": {
        "ko": "회생(에너지 재사용) 효율", "kind": "direct", "units": {"ratio": 1.0, "%": 0.01},
        "canon": "ratio", "lo": 0.0, "hi": 1.0, "role": "param",
        "help": "방전 에너지 중 다른 채널 충전에 다시 쓰이는 비율 (장비 단위 값이며 공장 절감률 아님)",
    },
    "electricity_delta_abs": {
        "ko": "가스·스팀 가열 공장에서의 전력 절대 증감 (셀 kWh당 kWh)", "kind": "direct", "units": {"kWh/kWh_cell": 1.0},
        "canon": "kWh/kWh_cell", "lo": -100.0, "hi": 100.0, "role": "saving",
        "help": "가열이 가스·스팀일 때 이 기술이 공장 전력을 얼마나 늘리거나(+) 줄이는지(-) 셀 kWh당 kWh로. "
                "공장 전력 원단위 근거로 나눠 계통 전력 효과로 바꾼다. 가스 가열 시나리오에서만 쓰이고, 있으면 비율 근거보다 우선",
    },
    "drying_time_ratio": {
        "ko": "건조시간 비(변경/기존)", "kind": "direct", "units": {"ratio": 1.0, "%": 0.01},
        "canon": "ratio", "lo": 0.0, "hi": 2.0, "role": "param",
        "help": "같은 건조로에서 필요한 건조시간 ÷ 기존 건조시간. 코팅속도 1.2배 대응에는 0.83 이하가 필요 (참고 전용)",
    },
    "aging_time_ratio": {
        "ko": "에이징 기간 비(변경/기존)", "kind": "direct", "units": {"ratio": 1.0, "%": 0.01},
        "canon": "ratio", "lo": 0.0, "hi": 2.0, "role": "aging",
        "help": "불량 검출력을 유지하면서 줄인 에이징 기간 ÷ 기존 기간. 14일→10일이면 0.71. 검출력 근거 없이 넣지 말 것",
    },
    "aging_days_before_after": {
        "ko": "개선 전·후 에이징 기간(비율 자동 계산)", "kind": "pair", "derives": "aging_time_ratio",
        "units": {"day": 1.0, "h": 1 / 24}, "canon": "day", "role": "aging",
        "help": "논문·특허가 기존·변경 에이징(또는 자가방전 판정) 기간을 주는 경우. 비율 = 후/전",
    },
    "energy_share": {
        "ko": "공정 단계 에너지 비중", "kind": "direct", "units": {"ratio": 1.0, "%": 0.01},
        "canon": "ratio", "lo": 0.0, "hi": 1.0, "role": "baseline",
        "help": "셀 제조 전체 에너지 중 해당 계통이 차지하는 비중 (과제 비중 w 검증용, 계산에는 쓰지 않음)",
    },
    "fixed_load_fraction": {
        "ko": "고정부하 비율 f", "kind": "direct", "units": {"ratio": 1.0, "%": 0.01},
        "canon": "ratio", "lo": 0.0, "hi": 1.0, "role": "baseline",
        "help": "생산량과 무관하게 일정한 부하 비율 (드라이룸 공조 등). 과제 가정 f 검증용",
    },
    "slot_gain_ratio": {
        "ko": "에이징 보관 슬롯 확보율 (기존 슬롯 대비)", "kind": "direct", "units": {"ratio": 1.0, "%": 0.01},
        "canon": "ratio", "lo": 0.0, "hi": 2.0, "role": "space",
        "help": "랙·버퍼 전환 등으로 기존 공간 안에서 추가 확보 가능한 에이징 슬롯 비율. 승인된 공간만",
    },
    "plant_electricity_intensity": {
        "ko": "공장 전력 원단위 (셀 kWh당 전력 kWh)", "kind": "direct", "units": {"kWh/kWh_cell": 1.0, "MJ/kWh_cell": 1 / 3.6},
        "canon": "kWh/kWh_cell", "lo": 0.0, "hi": 500.0, "role": "plant",
        "help": "셀 1 kWh 생산에 드는 공장 전력. 연간 절감 전력량·금액 환산에만 사용 (반드시 전력 기준)",
    },
}

# FMEA 관리 부담 지표
BURDEN_METRICS = {
    "added_occupancy_h": {"ko": "추가 채널 점유시간", "units": {"h": 1.0, "min": 1 / 60}, "canon": "h", "lo": 0.0, "hi": 48.0},
    "added_power_ratio": {"ko": "추가 전력(해당 계통 기준 전력 대비)", "units": {"ratio": 1.0, "%": 0.01},
                          "canon": "ratio", "lo": 0.0, "hi": 1.0},
    "extra_channel_ratio": {"ko": "추가 채널 비율", "units": {"ratio": 1.0, "%": 0.01}, "canon": "ratio", "lo": 0.0, "hi": 2.0},
    "added_aging_days": {"ko": "추가 에이징 보관일수(셀당 평균, 사전 안정화·재검 대기 포함)", "units": {"day": 1.0, "h": 1 / 24},
                         "canon": "day", "lo": 0.0, "hi": 30.0},
    "none": {"ko": "정량 부담 없음(품질 관문만)", "units": {"-": 1.0, "": 1.0}, "canon": "-", "lo": 0.0, "hi": 0.0},
}

# ------------------------------------------------------------------ 시트별 열 정의
# (key, 한국어 머리글, 필수 여부, 설명)
SHEETS = {
    "sources": [
        ("source_id", "근거ID", True, "R1, R12, T01 처럼 고유하게. 팀원이 추가할 때는 이니셜+번호 권장(예: JS01)"),
        ("citation", "서지사항", True, "저자, 연도, 학술지, 권, 쪽"),
        ("title", "제목", True, "원문 제목"),
        ("doi", "DOI", False, "없으면 비워 둠"),
        ("year", "연도", True, "숫자"),
        ("source_type", "자료유형", True, " / ".join(SOURCE_TYPES)),
        ("access", "확인범위", True, "원문 / 초록 / 2차"),
        ("url", "URL", False, ""),
        ("note", "비고", False, ""),
    ],
    "levers": [
        ("lever_id", "레버ID", True, "예: DRY-HP. 새 레버는 계통약어-이름 형식"),
        ("name_ko", "레버명", True, ""),
        ("system", "적용계통", True, " / ".join(SYSTEMS)),
        ("exclusive_group", "중복방지그룹", True, "같은 그룹 레버끼리는 절감을 곱하지 않고 하나만(가장 보수적인 조합) 반영"),
        ("covers", "포함레버", False, "패키지 레버일 때 포함하는 레버ID를 ;로 구분. 패키지를 고르면 포함 레버는 따로 세지 않음"),
        ("v10_adopted", "v10채택", False, "예 / 아니오 (v10 제안서가 채택한 레버인지)"),
        ("horizon", "적용시기", False, "3년내 / 장기 (장기 레버는 대안 탐색에서 따로 표시. 비우면 3년내)"),
        ("change_type", "변경유형", False, " / ".join(CHANGE_TYPES) + " (적용 난이도·3년 적용 순서에 사용)"),
        ("description", "설명", False, ""),
    ],
    "effects": [
        ("effect_id", "효과ID", True, "EF-001 처럼 고유하게"),
        ("lever_id", "레버ID", True, "levers 시트의 레버ID"),
        ("metric", "지표", True, " / ".join(METRICS)),
        ("value_low", "최솟값", False, "범위가 있으면 하한 (direct 지표)"),
        ("value_typ", "대표값", False, "논문의 대표·중앙 값 (direct 지표). 하나만 있으면 여기에"),
        ("value_high", "최댓값", False, "범위가 있으면 상한 (direct 지표)"),
        ("value_before", "개선전값", False, "pair 지표일 때 기존 값"),
        ("value_after", "개선후값", False, "pair 지표일 때 개선 값"),
        ("unit", "단위", True, "지표별 허용 단위 (작성가이드 참고)"),
        ("basis", "기준·정의", True, "무엇 대비 몇 %인지 (예: 건조 공정 전기에너지 기준, 셀 kWh당)"),
        ("boundary", "측정범위", True, " / ".join(BOUNDARY) + " (절감·시간 지표에서 필수)"),
        ("boundary_share", "경계비중", False, "공장전체: 원문에서 그 계통이 공장 에너지에서 차지하는 비중 / 계통일부: 계통 에너지 중 그 부분의 비중 (0~1)"),
        ("energy_carrier", "에너지종류", False, " / ".join(ENERGY_CARRIER) + " (과제 목표는 전력. 비우면 '미기재'로 조건부 처리)"),
        ("machine_elec_change", "설비전기변화", False, "원문이 설비 전기 사용 변화를 따로 주면 비율로 (예: +566% → 5.66, -65% → -0.65). 가열이 가스·스팀일 때 전력 효과 계산에 사용"),
        ("machine_heat_change", "설비열변화", False, "원문이 설비 열(가스·스팀) 사용 변화를 따로 주면 비율로 (예: -100% → -1). 참고 기록용"),
        ("chemistry", "양극계", True, " / ".join(CHEMISTRY)),
        ("cell_format", "셀형태", True, " / ".join(CELL_FORMAT)),
        ("scale", "규모", True, " / ".join(SCALE)),
        ("conditions_note", "조건메모", False, "이슬점, 코팅 두께, 공급온도 등 적용 조건"),
        ("source_id", "근거ID", True, "sources 시트의 근거ID"),
        ("locator", "위치", True, "쪽·그림·표 번호 (예: p.1288 Fig.3b)"),
        ("excerpt", "근거요약", True, "수치가 나온 문장 요약 (한두 문장)"),
        ("evidence_grade", "근거등급", True, "A / B / C / D / E"),
        ("verification", "확인상태", True, " / ".join(VERIFICATION)),
        ("entered_by", "입력자", False, ""),
        ("note", "비고", False, ""),
    ],
    "fmea": [
        ("fmea_id", "FMEA_ID", True, "FM-001 처럼 고유하게"),
        ("lever_id", "레버ID", True, "levers 시트의 레버ID"),
        ("failure_mode", "고장모드", True, "레버 적용 시 생길 수 있는 문제 (예: SEI 불균일)"),
        ("mechanism", "메커니즘", True, "왜 생기는지"),
        ("affected", "영향범주", True, " / ".join(AFFECTED) + " (여러 개면 ;로)"),
        ("control_action", "관리조치", True, "이 문제를 막는 조치"),
        ("detection_method", "검출·검증방법", True, "어떻게 확인하는지 (측정 항목)"),
        ("burden_metric", "부담지표", True, " / ".join(BURDEN_METRICS)),
        ("burden_low", "부담최솟값", False, ""),
        ("burden_typ", "부담대표값", False, ""),
        ("burden_high", "부담최댓값", False, ""),
        ("unit", "단위", False, "부담지표별 허용 단위"),
        ("quality_gate", "품질관문", True, "적용 전에 반드시 통과해야 할 조건"),
        ("source_id", "근거ID", True, "sources 시트의 근거ID (팀 판단이면 TEAM)"),
        ("locator", "위치", False, "쪽·그림·표"),
        ("excerpt", "근거요약", False, ""),
        ("evidence_grade", "근거등급", True, "A / B / C / D / E"),
        ("verification", "확인상태", True, " / ".join(VERIFICATION)),
        ("entered_by", "입력자", False, ""),
        ("note", "비고", False, ""),
    ],
}

SHEET_KO = {"sources": "근거자료", "levers": "레버", "effects": "정량효과", "fmea": "근거FMEA"}
ID_COL = {"sources": "source_id", "levers": "lever_id", "effects": "effect_id", "fmea": "fmea_id"}


# 대상 공장 조건 (v10 p.2: NCM 파우치 10GWh → 12GWh). 적용 조건 일치 판정의 기준
TARGET_CONTEXT = {"chemistry": "NCM", "cell_format": "파우치", "scale": "양산"}
# 같은 Ni계 층상 양극은 '유사'로 본다
CHEMISTRY_SIMILAR = {"NCM": {"NCA"}, "NCA": {"NCM"}}


def header(key_ko, key):
    """엑셀 머리글: '한국어(key)' - 가져오기에서 괄호 안 key로 열을 찾는다."""
    return f"{key_ko}({key})"


def columns(sheet):
    return [c[0] for c in SHEETS[sheet]]
