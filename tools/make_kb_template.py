"""팀원용 근거 FMEA 데이터셋 입력 템플릿(엑셀) 생성.

사용: python tools/make_kb_template.py [출력경로]
스키마는 kb_schema.py, 레버 목록은 data/kb/levers.csv 에서 읽는다.
'EX-' 로 시작하는 ID 행은 예시이며 가져오기(kb_import.py)에서 무시된다.
"""
import csv
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import kb_schema as S  # noqa: E402

FONT = "맑은 고딕"
F_BASE = Font(name=FONT, size=10)
F_HEAD = Font(name=FONT, size=10, bold=True, color="FFFFFF")
F_EX = Font(name=FONT, size=10, italic=True, color="808080")
F_TITLE = Font(name=FONT, size=14, bold=True, color="1F3B4D")
F_H2 = Font(name=FONT, size=11, bold=True, color="1F3B4D")
FILL_HEAD_REQ = PatternFill("solid", fgColor="1F3B4D")
FILL_HEAD_OPT = PatternFill("solid", fgColor="5B7F95")
FILL_REQ = PatternFill("solid", fgColor="FFF5CC")   # 필수 입력 칸
FILL_EX = PatternFill("solid", fgColor="F2F2F2")
THIN = Side(style="thin", color="C9D3DB")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
N_INPUT_ROWS = 300
STYLE_ROWS = 300

EXAMPLES = {
    "sources": [{
        "source_id": "EX-R8", "citation": "Lechner, M. et al. (2025). Energy Technology 13, 2402311.",
        "title": "Cost Model for the Footprint Planning of Production Environments in Lithium-Ion Battery Production",
        "doi": "10.1002/ente.202402311", "year": 2025, "source_type": "논문", "access": "2차",
        "note": "예시 행 - 실제 입력 시 EX- 없이 작성"}],
    "effects": [{
        "effect_id": "EX-EF-001", "lever_id": "DRM-LOCAL", "metric": "energy_before_after",
        "value_before": 46.74, "value_after": 37.28, "unit": "kWh/kWh_cell",
        "basis": "드라이룸 총에너지(가스+전력), 셀 kWh당", "boundary": "계통전체", "energy_carrier": "합산", "chemistry": "무관", "cell_format": "무관", "scale": "모델",
        "conditions_note": "이슬점 -60°C 사례(대상 공장 -40°C와 다름)", "source_id": "EX-R8", "locator": "v10 p.6 표 인용",
        "excerpt": "일부 공정 국소화 시 드라이룸 총에너지 46.74→37.28 kWh/kWh셀(-20.2%)", "evidence_grade": "C",
        "verification": "2차 인용", "entered_by": "예시", "note": "예시 행 - 가져오기에서 무시됨"}],
    "fmea": [{
        "fmea_id": "EX-FM-001", "lever_id": "FOR-FAST", "failure_mode": "SEI 불균일·가스 발생 증가",
        "mechanism": "고율 화성에서 전해질 환원 반응이 불균일하게 진행", "affected": "품질;시간",
        "control_action": "전류·전압창·온도 조합별 초기효율·가스·저항 비교",
        "detection_method": "초기 쿨롱효율, 가스량, DCIR, 장기 사이클 수명", "burden_metric": "added_occupancy_h",
        "burden_typ": 0.25, "unit": "h", "quality_gate": "16h 프로토콜의 초기효율·저항·수명이 기존 대비 동등",
        "source_id": "TEAM", "evidence_grade": "E", "verification": "미확인", "entered_by": "예시",
        "note": "예시 행 - 0.25h는 v10 목표 사양(측정값 아님)"}],
}


def _lists_sheet(wb, levers):
    ws = wb.create_sheet("목록")
    lists = {
        "lever_id": [l["lever_id"] for l in levers], "metric": list(S.METRICS),
        "burden_metric": list(S.BURDEN_METRICS), "evidence_grade": list(S.EVIDENCE_GRADES),
        "verification": list(S.VERIFICATION), "chemistry": S.CHEMISTRY, "cell_format": S.CELL_FORMAT,
        "scale": S.SCALE, "boundary": list(S.BOUNDARY), "energy_carrier": list(S.ENERGY_CARRIER),
        "change_type": list(S.CHANGE_TYPES), "horizon": ["3년내", "장기"], "source_type": S.SOURCE_TYPES, "access": S.ACCESS, "system": S.SYSTEMS,
        "v10_adopted": ["예", "아니오"],
    }
    refs = {}
    for i, (k, vals) in enumerate(lists.items(), 1):
        col = get_column_letter(i)
        ws.cell(1, i, k).font = Font(name=FONT, bold=True)
        for j, v in enumerate(vals, 2):
            ws.cell(j, i, v).font = F_BASE
        # 레버는 팀원이 레버 시트에 추가할 수 있으므로 레버 시트 범위를 직접 참조
        refs[k] = f"=목록!${col}$2:${col}${len(vals) + 1}"
    refs["lever_id"] = f"=레버!$A$3:$A${N_INPUT_ROWS + 2}"
    ws.sheet_state = "hidden"
    return refs


def _data_sheet(wb, key, refs, rows=None):
    ws = wb.create_sheet(S.SHEET_KO[key])
    cols = S.SHEETS[key]
    ws.cell(1, 1, f"{S.SHEET_KO[key]} - 노란 칸은 필수, 회색 행은 예시(EX-)입니다. 머리글에 마우스를 올리면 설명이 보입니다.").font = F_H2
    for i, (k, ko, req, desc) in enumerate(cols, 1):
        c = ws.cell(2, i, S.header(ko, k))
        c.font, c.fill, c.border, c.alignment = F_HEAD, FILL_HEAD_REQ if req else FILL_HEAD_OPT, BORDER, WRAP
        if desc:
            c.comment = Comment(desc, "템플릿")
        width = 14 if k not in ("excerpt", "citation", "title", "basis", "mechanism", "control_action",
                                "detection_method", "quality_gate", "description", "conditions_note",
                                "failure_mode", "name_ko", "note") else 34
        ws.column_dimensions[get_column_letter(i)].width = width
    r0 = 3
    for row in rows or []:
        for i, (k, *_rest) in enumerate(cols, 1):
            c = ws.cell(r0, i, row.get(k))
            ex = str(row.get(S.ID_COL[key], "")).startswith("EX-")
            c.font, c.border, c.alignment = (F_EX if ex else F_BASE), BORDER, WRAP
            if ex:
                c.fill = FILL_EX
        r0 += 1
    for r in range(r0, r0 + min(N_INPUT_ROWS, STYLE_ROWS)):   # 서식은 앞쪽 일부 행만 (파일 크기), 드롭다운은 전체 행
        for i, (k, ko, req, _d) in enumerate(cols, 1):
            c = ws.cell(r, i)
            c.font, c.border = F_BASE, BORDER
            if req:
                c.fill = FILL_REQ
    for i, (k, *_r) in enumerate(cols, 1):
        if k in refs and not (key == "levers" and k == "lever_id"):
            dv = DataValidation(type="list", formula1=refs[k], allow_blank=True, showErrorMessage=True,
                                errorTitle="목록 값", error="목록에 있는 값을 고르세요")
            dv.add(f"{get_column_letter(i)}3:{get_column_letter(i)}{r0 + N_INPUT_ROWS}")
            ws.add_data_validation(dv)
    ws.freeze_panes = "B3"
    ws.row_dimensions[2].height = 32
    return ws


def _guide(wb):
    ws = wb.active
    ws.title = "작성가이드"
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 100
    lines = [
        ("근거 FMEA 데이터셋 입력 템플릿", None, F_TITLE),
        ("목적", "논문·자료의 수치를 '근거 1건 = 1행'으로 모으면, 도구가 이 데이터셋만으로 12GWh 증산·원단위 30% 절감 목표의 "
                 "충족 가능성을 자동 판정하고 부족분을 역산합니다. 사람이 '건조 40%'처럼 숫자를 정하지 않습니다.", None),
        ("작성 순서", "① 근거자료 시트에 문헌 등록 → ② 정량효과 시트에 수치 입력 → ③ 근거FMEA 시트에 고장모드·관리 부담 입력. "
                     "레버가 목록에 없으면 레버 시트에 새 행 추가", None),
        ("가장 중요한 규칙", "수치 1개마다 근거ID와 위치(쪽·그림·표)를 반드시 적습니다. 위치를 모르면 확인상태를 '초록 확인' 또는 '미확인'으로 둡니다. "
                           "근거 없는 숫자는 근거등급 E(팀 가정)로만 입력합니다.", None),
        ("노란 칸 / 회색 행", "노란 칸 = 필수. 회색 'EX-' 행은 형식을 보여주는 예시이며 가져올 때 무시됩니다. 머리글 칸에 설명 메모가 있습니다.", None),
        ("값 입력 (direct 지표)", "범위가 있으면 최솟값·최댓값, 대표값이 하나만 있으면 대표값에만. 백분율은 단위를 % 로 고르고 30 처럼 쓰거나, "
                               "단위를 ratio 로 고르고 0.30 처럼 씁니다.", None),
        ("값 입력 (pair 지표)", "논문이 개선 전·후 값을 주면 지표를 energy_before_after 또는 time_before_after 로 고르고 개선전값·개선후값을 씁니다. "
                             "절감률(또는 시간비)은 도구가 계산합니다. 두 값은 같은 단위·같은 기준이어야 합니다.", None),
        ("중복 방지", "같은 절감을 두 번 세지 않도록 레버마다 중복방지그룹이 있습니다. 예: FOR-FAST와 FOR-REGEN은 같은 그룹이라 곱하지 않습니다. "
                     "논문이 계통 전체 절감만 주면 DRY-PKG / DRM-PKG 같은 패키지 레버로 입력합니다.", None),
        ("측정범위 (중요)", "논문 절감률이 '무엇 대비'인지 고릅니다. 공장전체 대비 값(예: Degen 2023의 −16.1%)을 계통 절감률로 착각하면 크게 틀립니다. "
                          "공장전체면 원문의 계통 비중을 경계비중에, 계통일부(예: NMP 증발 에너지만)면 계통 중 그 부분의 비중을 경계비중에 적습니다. "
                          "모르면 비워 두세요 - 도구가 환산 가능 여부를 판단하고, 불가능하면 참고 근거로만 씁니다.", None),
        ("에너지종류", "과제 목표는 '전력' 원단위입니다. 수치가 전력만인지, 열(가스·증기)인지, 둘을 합친 값인지, 1차에너지인지 고릅니다. "
                      "열·합산 값은 해당 계통 가열이 전기식일 때만 전력 절감으로 인정되고, 1차에너지는 참고로만 씁니다. 모르면 비워 두세요.", None),
        ("에이징 근거 (1순위)", "증산을 막는 유일한 축은 에이징입니다(14일 유지 시 보관 슬롯 +13.7% 필요). "
                             "에이징 단축 근거는 레버 AGE-EARLY, 지표 aging_days_before_after(예: 14 → 3, 단위 day) 또는 aging_time_ratio로 입력합니다. "
                             "짧게 판정해도 자가방전·미세단락 불량을 놓치지 않았다는 검출력 결과가 있으면 근거FMEA 시트에 함께 적습니다. "
                             "보관 공간 근거는 레버 AGE-RACK, 지표 slot_gain_ratio(같은 면적에서 늘어나는 슬롯 비율)로 입력합니다.", None),
        ("적용 조건", "양극계·셀형태·규모는 원문 조건 그대로. 대상 공장은 NCM·파우치·양산입니다. 양극계가 다르면 자동 판정에서 제외되고, "
                     "규모·셀형태가 다르면 '조건부'로 표시됩니다.", None),
        ("금지", "RPN·AP·CEI 같은 점수나 고장확률은 넣지 않습니다. 근거 등급과 확인 상태만 범주로 적습니다.", None),
        ("다 쓰면", "파일을 그대로 보내 주세요. kb_import.py가 검증(필수값·단위·범위·ID 연결)하고 오류 목록을 돌려줍니다.", None),
        (None, None, None),
        ("측정범위", None, F_H2),
        *[(k, v, None) for k, v in S.BOUNDARY.items()],
        (None, None, None),
        ("근거등급", None, F_H2),
        *[(k, v, None) for k, v in S.EVIDENCE_GRADES.items()],
        (None, None, None),
        ("확인상태", None, F_H2),
        *[(k, v, None) for k, v in S.VERIFICATION.items()],
        (None, None, None),
        ("정량효과 지표", None, F_H2),
        *[(k, f"{m['ko']} · 허용 단위: {', '.join(m['units'])} · {m['help']}", None) for k, m in S.METRICS.items()],
        (None, None, None),
        ("FMEA 부담지표", None, F_H2),
        *[(k, f"{m['ko']} · 허용 단위: {', '.join(u for u in m['units'] if u)}", None) for k, m in S.BURDEN_METRICS.items()],
    ]
    for i, (a, b, font) in enumerate(lines, 1):
        if a is not None:
            ws.cell(i, 1, a).font = font or Font(name=FONT, size=10, bold=True)
        if b is not None:
            c = ws.cell(i, 2, b)
            c.font, c.alignment = F_BASE, WRAP
    return ws


def build(out_path):
    with open(ROOT / "data" / "kb" / "levers.csv", encoding="utf-8") as fh:
        levers = list(csv.DictReader(fh))
    wb = Workbook()
    _guide(wb)
    refs = _lists_sheet(wb, levers)
    _data_sheet(wb, "sources", refs, EXAMPLES["sources"])
    _data_sheet(wb, "effects", refs, EXAMPLES["effects"])
    _data_sheet(wb, "fmea", refs, EXAMPLES["fmea"])
    _data_sheet(wb, "levers", refs, levers)
    # 시트 순서: 가이드, 근거자료, 정량효과, 근거FMEA, 레버, (숨김)목록
    order = ["작성가이드", "근거자료", "정량효과", "근거FMEA", "레버", "목록"]
    wb._sheets = [wb[n] for n in order]
    for ws in wb.worksheets:   # 인쇄 시 열이 여러 쪽으로 나뉘지 않게 가로 맞춤
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
    wb.save(out_path)
    return out_path


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "근거FMEA_입력템플릿.xlsx"
    print(build(out))
