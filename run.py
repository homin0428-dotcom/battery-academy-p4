"""독립 CLI: core 계산 엔진을 호출해 결과 파일을 생성한다.

  python run.py --scenario representative --out outputs [--run-tests] [--set KEY=JSON ...]
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import core
import reporting
from candidates import sys_change

BASE = Path(__file__).resolve().parent


def run_pytest(out_dir=None):
    """pytest를 같은 실행 안에서 돌리고 명령·종료코드·요약·로그를 함께 남긴다 (manifest와 같은 실행).

    status: passed(종료코드 0, 통과>0) / failed(실패 있음) / error(수집 오류·pytest 미설치·시험 0개 등 실행 자체 문제)
    """
    import hashlib
    from datetime import datetime
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"]
    started = datetime.now().isoformat(timespec="seconds")
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=BASE)
        rc, text = p.returncode, (p.stdout or "") + ("\n[stderr]\n" + p.stderr if p.stderr else "")
    except OSError as e:
        rc, text = -1, f"pytest 실행 불가: {e}"
    cnt = {k: int(m.group(1)) if (m := re.search(rf"(\d+) {k}", text)) else 0 for k in ("passed", "failed", "error", "errors")}
    errors = cnt["error"] + cnt["errors"]
    if rc == 0 and cnt["passed"] > 0 and cnt["failed"] == 0:
        status = "passed"
    elif cnt["failed"] > 0:
        status = "failed"
    else:
        status = "error"
    lines = [l for l in text.strip().splitlines() if l.strip()]
    summary = next((l for l in reversed(lines) if re.search(r"passed|failed|error|no tests ran", l)), lines[-1] if lines else "")
    res = {"status": status, "passed": cnt["passed"], "failed": cnt["failed"], "errors": errors, "exit_code": rc,
           "summary": summary.strip("= "), "command": "python " + " ".join(cmd[1:]), "started": started}
    if status == "error":
        res["hint"] = ("pytest가 설치돼 있는지(pip install -r requirements.txt), tests 폴더가 있는지 확인. "
                       "로그 test_log.txt 참조")
    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        log = out_dir / "test_log.txt"
        log.write_text(f"# command: {' '.join(cmd)}\n# started: {started}\n# exit_code: {rc}\n\n{text}", encoding="utf-8")
        res["log_file"] = log.name
        res["log_sha256"] = hashlib.sha256(log.read_bytes()).hexdigest()
    return res


def parse_sets(items):
    out = {}
    for it in items or []:
        key, _, raw = it.partition("=")
        try:
            out[key.strip()] = json.loads(raw)
        except json.JSONDecodeError:
            raise SystemExit(f"--set {it}: 값은 JSON 이어야 한다 (예: formation_h=17, f=[0,0,0,0,0])")
    return out


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="PFMEA 연계 공정 전환 검토 CLI")
    ap.add_argument("--scenario", default="representative", choices=["representative", "all_proportional", "custom"])
    ap.add_argument("--out", default="outputs")
    ap.add_argument("--config", default=None)
    ap.add_argument("--set", action="append", help="입력 override, KEY=JSON (예: --set channel_ratio=1.08)")
    ap.add_argument("--run-tests", action="store_true", help="pytest를 실행하고 결과를 manifest에 기록")
    ap.add_argument("--no-export", action="store_true", help="파일 생성 없이 요약만 출력")
    a = ap.parse_args(argv)

    cfg = core.load_config(a.config)
    res = core.run_scenario(cfg, a.scenario, parse_sets(a.set))
    if res.get("blocked"):
        print("입력 오류로 계산 차단:", res["blocked"])
        return 2
    ev = res.get("evidence", {})
    old_lines = [f"[{res['scenario_label']}] {res['calculation_mode']}"]
    for k in res["kpi"]:
        old_lines.append(f"  {k['title']}: {k['value']}  ({k['sub']}; 근거: {k['label']})")
    old_lines.append("  결론: " + str(res["conclusion"]))
    for w in res["warnings"]:
        old_lines.append("  경고: " + str(w))
    if ev.get("status") == core.NUM_OK:
        c = ev["cases"]
        ov = ev.get("overall") or {}
        rec = ev.get("recommended") or {}
        adds = rec.get("add", []) + (rec.get("production_add") or [])
        old_lines.append(f"  [근거 기반 종합 판정] 추천 조합(+{' + '.join(adds) or '없음'}): {ov.get('label', '-')}")
        old_lines.append(f"  v10 레버만: {ev['verdict']} - 원단위 절감 보수 {c['conservative']['saving'] * 100:.1f}% · "
                         f"대표 {c['typical']['saving'] * 100:.1f}% · 낙관 {c['optimistic']['saving'] * 100:.1f}% "
                         f"(근거 {ev['counts']['sources']}개 자료, 계산 사용 {ev['counts']['calc']}건)")
        old_lines.append("  근거 결론: " + str(ev["conclusion"]))
        cd = ev.get("candidates")
        if cd:
            print(f"[v12.2 공식 결론 - A/B/C 후보 비교 · 설계 고정] {cd['status']}")
            for c in cd["candidates"]:
                st = " / ".join(f"{a['axis'].split('(')[0]} {a['state']}" for a in c["axes"])
                print(f"  {c['id']:<3}{'★' if c['id'] == cd['selected'] else ' '} {c['name']}: 대표 {c['saving'][1] * 100:.1f}% "
                      f"(보수 {c['saving'][0] * 100:.1f}~낙관 {c['saving'][2] * 100:.1f}), 고형분 {c['solids'] * 100:.1f}% "
                      f"{'' if c['eligible'] else '[대기] '}→ {c['label']}")
                print(f"       {st}")
            hs = cd.get("heat")
            if hs:
                sel_id = cd["selected"]
                print(f"  {sel_id} 열원 민감도: " + " / ".join(
                    f"{r['case']} {r['saving'][1] * 100:.1f}%(건조 {sys_change(r['r_drying'])})"
                    for r in hs["rows"] if r["candidate"] == sel_id))
            stt = (cd.get("capacity") or {}).get("stages")
            if stt:
                print(f"  {stt['candidate']} 단계별(연차 생산비 q_t 반영): " + " → ".join(
                    f"{x['stage']} {x['at_q_t']['saving'] * 100:.1f}%(q {x['q_t']:.3f}; 슬롯 확보 시 {x['at_q_if_slots']['saving'] * 100:.1f}%)"
                    for x in stt["stages"]))
            wf = (cd.get("baseline_model") or {}).get("waterfall")
            if wf:
                print(f"  절감 구성: 공정 개조 {wf['tech_pp']:.2f}%p + 고정부하 희석 {wf['dilution_pp']:.2f}%p(팀 가정 f) - 관리 전력 {wf['burden_pp']:.2f}%p")
            cp = (cd.get("capacity") or {}).get("plant")
            if cp:
                print(f"  공장 처리능력 {cp['plant']:.3f}배 (병목 {cp['bottleneck']}; " + ", ".join(f"{k} {v:.3f}" for k, v in cp["caps"].items()) + ")")
            rm = cd.get("roadmap") if isinstance(cd.get("roadmap"), dict) and "space" in cd.get("roadmap", {}) else None
            if rm:
                print("  생산능력: " + rm["space"]["sentence"])
            lc = ((cd.get("baseline_model") or {}).get("literature_cases") or {}).get("rows") if isinstance(cd.get("baseline_model"), dict) else None
            if lc:
                print("  문헌 사례 재계산: " + " / ".join(f"{r['label'].split(' (')[0]} {r['saving'] * 100:.2f}%" for r in lc[1:3]))
            dz = cd.get("design") if isinstance(cd.get("design"), dict) and "error" not in cd.get("design") else None
            if dz:
                print("  설계 고정 비교: " + " / ".join(f"{r['label'].split(' ')[0]}{'★' if r['official'] else ''} {r['saving'][1] * 100:.2f}%(여유 {r['margin_pt']:+.2f} pt)"
                                                    for r in dz["compare"]["rows"]))
                print("  두 목표 신호등: " + " / ".join(f"{r['cond']} → {r['overall']}" for r in dz["signal"]["rows"][:3]))
                print("  금액: " + " / ".join(f"{c['title']} 연 {c['krw_eok'][0]:.0f}~{c['krw_eok'][1]:.0f}억" for c in dz["money"]["cards"]))
            top = cd["priority"]["tests"][:3]
            print("  먼저 확인할 것: " + " / ".join(f"{t['priority']}. {t['question']}({t['impact']})" for t in top))
        if ev["n_errors"]:
            print(f"  데이터셋 검증 오류 {ev['n_errors']}건 - 해당 행은 판정에서 제외됨")
    else:
        print("  근거 판정:", ev.get("error", "실행 안 됨"))
    print("[부록 A. 이전 모델 - 본문·PPT에 쓰지 말 것]")
    for ln in old_lines:
        print("  " + ln)
    if a.no_export:
        return 0
    ts = run_pytest(Path(a.out)) if a.run_tests else None
    if ts:
        print(f"  pytest: {ts['status']} (통과 {ts['passed']}, 실패 {ts['failed']}, 오류 {ts['errors']}, 종료코드 {ts['exit_code']}) - {ts['summary']}")
        if ts.get("hint"):
            print("  ", ts["hint"])
    info = reporting.make_run_info("cli", ts)
    r = reporting.export_all(res, Path(a.out), info, a.config)
    print(f"  산출물: {Path(a.out).resolve()} (PDF {r['pdf_pages']}쪽"
          + (f", 근거 판정 보고서 {r['evidence']['pages']}쪽" if r.get("evidence") else "") + ", results.json)")
    chk = r.get("consistency")
    if chk is not None:
        bad = [c["item"] for c in chk["checks"] if not c["ok"]]
        print(f"  숫자 일치 검사(results.json ↔ CSV ↔ PDF): {'통과' if chk['ok'] else '실패 - ' + ', '.join(bad)} ({len(chk['checks'])}개 항목)")
    ok_tests = not ts or ts["status"] == "passed"
    ok_check = chk is None or chk["ok"]
    return 0 if ok_tests and ok_check else 1


if __name__ == "__main__":
    sys.exit(main())
