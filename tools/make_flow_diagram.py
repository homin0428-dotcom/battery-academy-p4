"""PPT용 흐름도 1장: 논문 → 근거 데이터셋 → 환산·검증 → 자동 판정 → 역산·추천 → 보고서·로드맵.

실행: python tools/make_flow_diagram.py [출력 경로]  (기본 outputs/flow_diagram.png)
숫자는 현재 데이터셋으로 실제 계산한 값을 넣는다 (그림이 결과와 어긋나지 않게).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

import core  # noqa: E402
import evidence_engine as ee  # noqa: E402
import reporting as R  # noqa: E402  (폰트 등록)

AMBER = "#B7791F"


def build(out):
    cfg = core.load_config()
    v, _ = core.resolve_inputs(cfg)
    ev = ee.evaluate(v)
    c = ev["counts"]
    rec = next((x for x in ev["combos"]["results"] if x["verdict"] != "근거상 미달"), None)
    pct = lambda x: f"{x * 100:.1f}%"

    steps = [
        ("① 근거 수집", "출제 논문 6편\n+ 공개 자료\n팀원이 템플릿에 입력\n(쪽·표 위치,\n측정범위, 에너지종류)"),
        ("② 근거 데이터셋", f"자료 {c['sources']}개\n정량효과 {c['effects']}행\n근거FMEA {c['fmea']}행\n가져올 때\n형식·범위 자동 검증"),
        ("③ 환산·적용성", "측정범위 → 계통 기준\n(같은 논문 비중 우선)\n전력 / 열 구분\nNCM·파우치·양산\n적합성 검사"),
        ("④ 자동 판정", "보수·대표·낙관 3경우\n4개 축 동시 판정\n(에너지·화성·\n에이징·품질)\n중복 효과는 안 곱함"),
        ("⑤ 역산·추천", "부족분 역산\n보완 조합 탐색\n추천이 바뀌는 조건\n결합 효과(κ)·\n관리부담(P) 경계"),
        ("⑥ 보고·로드맵", "개선안 비교표\n(효과·위험·투자)\n3년 적용 순서\nFMEA 품질 관문\n= 단계 진입 조건"),
    ]
    fig, ax = plt.subplots(figsize=(13.3, 5.2))
    ax.set_xlim(0, 13.3)
    ax.set_ylim(-0.2, 5.2)
    ax.axis("off")
    ax.text(0.35, 4.85, "근거 기반 공정 전환 판정 도구 - 분석 흐름", fontsize=17, fontweight="bold", color=R.NAVY)
    ax.text(0.35, 4.48, "숫자를 사람이 정하지 않고, 논문 근거 데이터셋으로 목표 충족 여부와 부족분을 자동으로 계산한다",
            fontsize=10.5, color=R.GRAY)
    bw, bh, gap, y0 = 1.98, 2.55, 0.15, 1.45
    for i, (t, body) in enumerate(steps):
        x = 0.35 + i * (bw + gap)
        fc = R.LIGHT if i not in (3, 4) else "#E6F0F7"
        ax.add_patch(FancyBboxPatch((x, y0), bw, bh, boxstyle="round,pad=0.02,rounding_size=0.08",
                                    fc=fc, ec=R.TEAL if i not in (3, 4) else R.NAVY, lw=1.6))
        ax.text(x + 0.12, y0 + bh - 0.32, t, fontsize=11.5, fontweight="bold", color=R.NAVY)
        ax.text(x + 0.12, y0 + bh - 0.62, body, fontsize=9.2, color="#222222", va="top", linespacing=1.45)
        if i < len(steps) - 1:
            ax.add_patch(FancyArrowPatch((x + bw + 0.01, y0 + bh / 2), (x + bw + gap - 0.01, y0 + bh / 2),
                                         arrowstyle="-|>", mutation_scale=14, color=R.NAVY, lw=1.4))
    # 되먹임: 판정이 알려준 '필요한 근거'를 팀이 찾아 다시 입력
    ax.add_patch(FancyArrowPatch((0.35 + 4 * (bw + gap) + bw / 2, y0 - 0.05), (0.35 + bw / 2, y0 - 0.05),
                                 connectionstyle="arc3,rad=-0.12", arrowstyle="-|>", mutation_scale=14,
                                 color=AMBER, lw=1.5, ls="--"))
    ax.text(6.65, 0.55, "판정이 '무엇이 확인되면 결론이 바뀌는지'를 알려줌 → 팀이 그 근거를 찾아 다시 입력",
            fontsize=9.5, color=AMBER, ha="center")
    if rec:
        res_txt = (f"현재 결과: v10 레버만 근거로 대표 {pct(ev['cases']['typical']['saving'])} (미달) → "
                   f"+{' + '.join(rec['add'])} 대표 {pct(rec['typical'])}·보수 {pct(rec['conservative'])} ({rec['verdict']})  |  "
                   f"종합: {ev['overall']['label']}")
        ax.text(0.35, 0.05, res_txt, fontsize=9.2, color=R.NAVY)
    fig.savefig(out, dpi=200, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return out


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "outputs" / "flow_diagram.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    print(build(out))
