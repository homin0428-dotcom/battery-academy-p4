"""팀원이 채운 근거 FMEA 엑셀 템플릿 → 데이터셋 CSV 가져오기·검증.

사용:
  python kb_import.py 입력.xlsx            # 검증만 (오류 보고서 출력, 파일 변경 없음)
  python kb_import.py 입력.xlsx --merge    # 검증 통과 행을 data/kb/*.csv 에 병합 (같은 ID는 엑셀 값으로 교체)
  python kb_import.py 입력.xlsx --merge --out 다른폴더

머리글은 '한국어(key)' 형식이며 괄호 안 key로 열을 찾는다. 'EX-'로 시작하는 예시 행은 무시한다.
오류 행은 병합하지 않고 kb_import_report.csv 에 행 번호·열·사유를 남긴다.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

import evidence_engine as ee
import kb_schema as S

KEY_RE = re.compile(r"\(([A-Za-z0-9_]+)\)\s*$")


def read_xlsx(path):
    from openpyxl import load_workbook
    wb = load_workbook(path, data_only=True, read_only=True)
    kb = {}
    for sheet, ko in S.SHEET_KO.items():
        if ko not in wb.sheetnames:
            raise ee.KBError(f"엑셀에 '{ko}' 시트가 없음 (템플릿을 사용했는지 확인)")
        rows = list(wb[ko].iter_rows(values_only=True))
        hdr_i = next((i for i, r in enumerate(rows) if r and any(isinstance(c, str) and KEY_RE.search(c) for c in r)), None)
        if hdr_i is None:
            raise ee.KBError(f"'{ko}' 시트에서 머리글 행을 찾지 못함")
        keys = [(KEY_RE.search(c).group(1) if isinstance(c, str) and KEY_RE.search(c) else None) for c in rows[hdr_i]]
        unknown = [k for k in keys if k and k not in S.columns(sheet)]
        if unknown:
            raise ee.KBError(f"'{ko}' 시트에 알 수 없는 열 {unknown}")
        unparsed = [c for c, k in zip(rows[hdr_i], keys) if k is None and isinstance(c, str) and c.strip()]
        if unparsed:
            raise ee.KBError(f"'{ko}' 시트 머리글을 해석하지 못함 {unparsed} - '한국어(key)' 형식을 유지하세요")
        required = [c[0] for c in S.SHEETS[sheet] if c[2]]
        missing = [k for k in required if k not in keys]
        if missing:
            raise ee.KBError(f"'{ko}' 시트에 열이 없음 {missing} - 최신 템플릿을 사용하세요")
        # 선택 열(예: 에너지종류·변경유형)이 없는 이전 템플릿도 받되, 빈 값으로 채운다
        out = []
        for r in rows[hdr_i + 1:]:
            d = {k: ("" if v is None else v) for k, v in zip(keys, r) if k}
            if all(str(v).strip() == "" for v in d.values()):
                continue
            out.append({k: (str(v) if not isinstance(v, str) else v) for k, v in d.items()})
        kb[sheet] = out
    return kb


def merge(base, new):
    """같은 ID는 새 값으로 교체, 나머지는 추가."""
    out = {}
    for sheet in S.SHEETS:
        idc = S.ID_COL[sheet]
        by = {r[idc]: r for r in base.get(sheet, [])}
        for r in new.get(sheet, []):
            by[r[idc]] = r
        out[sheet] = list(by.values())
    return out


def write_kb(kb, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for sheet in S.SHEETS:
        cols = S.columns(sheet)
        with open(out_dir / f"{sheet}.csv", "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for r in kb[sheet]:
                w.writerow({c: r.get(c, "") for c in cols})


def import_xlsx(xlsx, kb_dir=None, do_merge=False, out_dir=None):
    new_raw = read_xlsx(xlsx)
    base_raw = ee.load_kb(kb_dir)
    merged_raw = merge(base_raw, new_raw)
    _clean, issues = ee.validate_kb(merged_raw)
    new_ids = {(s, r[S.ID_COL[s]]) for s in S.SHEETS for r in new_raw.get(s, [])}
    bad_ids = {(i["sheet"], i["id"]) for i in issues if i["level"] == "error"}
    accepted = {s: [r for r in new_raw.get(s, []) if (s, r[S.ID_COL[s]]) not in bad_ids
                    and not str(r[S.ID_COL[s]]).startswith("EX-")] for s in S.SHEETS}
    report = {"new_rows": sum(len(v) for v in new_raw.values()),
              "accepted": {s: len(v) for s, v in accepted.items()},
              "errors": [i for i in issues if i["level"] == "error" and (i["sheet"], i["id"]) in new_ids],
              "base_errors": [i for i in issues if i["level"] == "error" and (i["sheet"], i["id"]) not in new_ids],
              "issues": issues}
    if do_merge:
        write_kb(merge(base_raw, accepted), out_dir or kb_dir or ee.KB_DIR)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description="근거 FMEA 엑셀 → 데이터셋 가져오기·검증")
    ap.add_argument("xlsx")
    ap.add_argument("--merge", action="store_true", help="검증 통과 행을 data/kb 에 병합")
    ap.add_argument("--kb", default=None, help="기존 데이터셋 폴더 (기본 data/kb)")
    ap.add_argument("--out", default=None, help="병합 결과 저장 폴더 (기본 = --kb)")
    a = ap.parse_args(argv)
    rep = import_xlsx(a.xlsx, a.kb, a.merge, a.out)
    print(f"엑셀 행 {rep['new_rows']}개 · 통과 {rep['accepted']} · 오류 {len(rep['errors'])}건")
    with open("kb_import_report.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["sheet", "row", "id", "field", "level", "msg"])
        w.writeheader()
        for i in rep["errors"]:
            w.writerow({k: i.get(k) for k in w.fieldnames})
    for i in rep["errors"][:30]:
        print(f"  [{S.SHEET_KO.get(i['sheet'], i['sheet'])}] {i['id']} · {i['field']}: {i['msg']}")
    if rep["errors"]:
        print("전체 오류 목록: kb_import_report.csv")
    print("병합 완료" if a.merge else "검증만 수행 (병합하려면 --merge)")
    return 1 if rep["errors"] and not a.merge else 0


if __name__ == "__main__":
    sys.exit(main())
