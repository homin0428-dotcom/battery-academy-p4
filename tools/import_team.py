"""팀원 엑셀 → 팀 데이터 층(data/kb_team/*.csv) 만들기.

seed_kb.py가 Claude 조사분(data/kb)을 다시 써도 팀원 입력이 사라지지 않도록, 팀 입력은 별도 층에 둔다.
seed_kb.py 마지막에 이 층을 합친다(같은 ID는 팀 값으로 교체, 나머지는 추가).

처리 규칙
- 같은 DOI를 다른 ID로 등록한 자료는 기존 ID로 바꾼다(REMAP). 해당 자료 행은 버리고, 팀 비고는 기존 행 비고 뒤에 붙인다.
- 'EX-' 예시 행, 보조 시트(추가조사_요약 등)는 읽지 않는다.
- 레버 시트는 여기서 다루지 않는다(data/kb/levers.csv를 직접 관리).

사용: python tools/import_team.py 팀원파일.xlsx [--drop ID ...]
"""
import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import kb_import as K  # noqa: E402
import kb_schema as S  # noqa: E402

TEAM_DIR = ROOT / "data" / "kb_team"
ACCESS_RANK = {"2차": 0, "초록": 1, "원문": 2}


def remap_by_doi(team_sources, master_sources):
    norm = lambda d: str(d or "").strip().lower().replace("https://doi.org/", "").replace("http://doi.org/", "")
    by_doi = {norm(s["doi"]): s["source_id"] for s in master_sources if norm(s.get("doi"))}
    return {s["source_id"]: by_doi[norm(s["doi"])] for s in team_sources
            if norm(s.get("doi")) in by_doi and by_doi[norm(s["doi"])] != s["source_id"]}


def _read_levers():
    return list(csv.DictReader(open(ROOT / "data" / "kb" / "levers.csv", encoding="utf-8-sig")))


def build(xlsx, drop=()):
    team = K.read_xlsx(xlsx)
    master = {s: list(csv.DictReader(open(ROOT / "data" / "kb" / f"{s}.csv", encoding="utf-8-sig"))) for s in ("sources",)}
    m_src = {s["source_id"]: s for s in master["sources"]}
    remap = remap_by_doi(team["sources"], master["sources"])
    lever_sys = {l["lever_id"]: l["system"] for l in _read_levers()}
    out = {"sources": [], "effects": [], "fmea": []}
    for s in team["sources"]:
        sid = s["source_id"]
        if sid.startswith("EX-") or sid in drop:
            continue
        if sid in remap:   # 중복 자료 → 기존 행에 팀 비고·더 높은 확인범위만 반영
            base = dict(m_src[remap[sid]])
            if s.get("note") and s["note"] not in (base.get("note") or ""):
                base["note"] = f"{base.get('note', '')} [팀 검토 {sid}] {s['note']}".strip()
            if ACCESS_RANK.get(s.get("access"), -1) > ACCESS_RANK.get(base.get("access"), -1):
                base["access"] = s["access"]
            out["sources"].append(base)
            continue
        out["sources"].append(s)
    for sheet in ("effects", "fmea"):
        idc = S.ID_COL[sheet]
        for r in team[sheet]:
            if str(r[idc]).startswith("EX-") or r[idc] in drop:
                continue
            r = dict(r)
            r["source_id"] = remap.get(r.get("source_id"), r.get("source_id"))
            if sheet == "fmea" and r.get("burden_metric") == "added_occupancy_h" and lever_sys.get(r.get("lever_id")) == "에이징":
                # 에이징 레버의 추가 시간은 화성 채널 점유가 아니라 에이징 보관일수 → 지표 교정 (h 값은 day로 환산)
                r["burden_metric"] = "added_aging_days"
                for k in ("burden_low", "burden_typ", "burden_high"):
                    if str(r.get(k) or "").strip():
                        r[k] = float(r[k]) / 24 if str(r.get("unit")).strip() in ("h", "") else r[k]
                r["unit"] = "day"
                r["note"] = (str(r.get("note") or "") + " [지표 교정: added_occupancy_h → added_aging_days]").strip()
            out[sheet].append(r)
    TEAM_DIR.mkdir(parents=True, exist_ok=True)
    for sheet, rows in out.items():
        cols = S.columns(sheet)
        with open(TEAM_DIR / f"{sheet}.csv", "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow({c: r.get(c, "") for c in cols})
    return remap, {k: len(v) for k, v in out.items()}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("--drop", nargs="*", default=[])
    a = ap.parse_args()
    remap, n = build(a.xlsx, set(a.drop))
    print("DOI 중복 → 기존 ID:", remap)
    print("팀 층 행 수:", n, "→", TEAM_DIR)
