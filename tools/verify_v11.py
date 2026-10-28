"""v11·v12 독립 검산 - 엔진 공식을 쓰지 않고 손계산으로 다시 계산해 엔진 출력과 비교한다.

사용: python tools/verify_v11.py   (battery_v10 폴더에서)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import candidates as C  # noqa: E402
import core  # noqa: E402

v, _ = core.resolve_inputs(core.load_config())
run = C.run_candidates(v)
cand = {c["id"]: c for c in run["candidates"]}
q, s0, s1 = 1.2, 0.60, 0.65
w, f = v["w"], v["f"]
rows = []


def chk(name, hand, eng, tol=1e-6):
    ok = abs(hand - eng) <= tol * max(1, abs(hand))
    rows.append(ok)
    print(f"{'OK ' if ok else 'NG '} {name:<34} 손계산 {hand:.6f}  엔진 {eng:.6f}")


# 1. 질량수지
chk("용매량 유지 최소 고형분", q * s0 / (1 + (q - 1) * s0), cand["B1"]["mass_balance"]["s1_min_keep_solvent"])
chk("고형분 65% 총 용매량(기존=1)", q * (0.35 / 0.65) / (0.40 / 0.60), cand["B1"]["mass_balance"]["solvent_vs_base"])
chk("같은 생산량 용매 감소율", 1 - (0.35 / 0.65) / (0.40 / 0.60), cand["B1"]["mass_balance"]["solvent_cut_same_output"])
# 2. 건조 체류
dry = next(a for a in cand["B1"]["axes"] if a["axis"].startswith("건조"))
chk("가능 체류시간비(60 m 고정)", 1 / q, dry["available_time_ratio"])
chk("B1 필요 건조시간비", (0.35 / 0.65) / (0.40 / 0.60), dry["need_time_ratio"])
# 3. 건조 잔여 부하 (φ 대표 0.5, f_건조)
fd, R = f[0], q * (0.35 / 0.65) / (0.40 / 0.60)
chk("건조 잔여 부하비(φ=0.5)", (fd + (1 - fd) * (0.5 * R + 0.5 * q)) / (fd + (1 - fd) * q), cand["B1"]["drying_residual"]["typical"])
# 4. 기준선·전력 (B1 대표 r로 손계산)
B = [wi * (fi + (1 - fi) * q) for wi, fi in zip(w, f)]
chk("12 GWh 무개선 기준선 ΣB", sum(B), cand["B1"]["E0"])
t = cand["B1"]["cases"]["typical"]
E = sum(b * (1 - r) for b, r in zip(B, t["r"])) + t["p_add"]
chk("B1 대표 E_new (pt)", E, t["E_total"])
chk("B1 대표 원단위 절감", 1 - E / (100 * q), t["saving"])
chk("B1 목표 여유 (84 - E)", 84 - E, cand["B1"]["margin_pt"])
# 5. 화성·에이징
fa = next(a for a in cand["B1"]["axes"] if a["axis"].startswith("화성"))
chk("화성 허용 추가 점유 (h)", 20 / 1.2 - 16, fa["allowed_added_h"])
ag = next(a for a in cand["B1"]["axes"] if a["axis"].startswith("에이징"))
chk("14일 추가 슬롯", 1.2 * 0.9 / 0.95 - 1, ag["required_slot_gain"])
chk("슬롯 무증설 허용 일수", 14 * 0.95 / (1.2 * 0.9), ag["allowed_days_without_slots"])
agc = next(a for a in cand["C"]["axes"] if a["axis"].startswith("에이징"))
chk("13일 추가 슬롯", 1.2 * 0.9 / 0.95 * 13 / 14 - 1, agc["required_slot_gain"])
# 6. 비용 (500~650 GWh, 181.9원)
pt = sum(B) - E
chk("B1 연 절감 하한 (억원)", pt / 100 * 500 * 1e6 * 181.9 / 1e8, cand["B1"]["money_typ"]["krw_eok"][0], 1e-3)
chk("B1 연 절감 상한 (억원)", pt / 100 * 650 * 1e6 * 181.9 / 1e8, cand["B1"]["money_typ"]["krw_eok"][1], 1e-3)
# 7. 검출력
chk("n=300 미검출 상한", 1 - 0.05 ** (1 / 300), C.miss_rate_upper(300))

# 8. 단일 계통 역산 세 모델 · 단계별 누적 · 안전 관문 수 (v11.1)
ev = C.evaluate(v)
rvm = {r["system"]: r for r in ev["reverse_models"]["rows"]}
chk("① 전부 비례 건조 단독", (120 - 84) / (35 * q), rvm["건조"]["linear"])
chk("② 엔진 무개선 건조 단독", (sum(B) - 84) / B[0], rvm["건조"]["engine"])
chk("③ 후보 A 후 건조 단독", rvm["건조"]["after_A"], next(r["required"] for r in cand["A"]["shortfall"]["per_system"] if r["system"] == "건조"))
chk("단계 누적 마지막 = B1 대표", ev["stages"]["stages"][-1]["saving"][1], cand["B1"]["saving"][1])
fm = {f["fmea_id"]: f for f in run["clean"]["fmea"]}
for cid in ("A", "B1", "B2", "C"):
    n = sum("안전" in (fm[r["fmea_id"]].get("affected_list") or []) for r in cand[cid]["quality"]["rows"])
    chk(f"{cid} 안전 관문 수", n, cand[cid]["n_safety_gates"])

# 9. v12: 워터폴 · 처리능력 · 동시 불확실성 · 연차 q_t · 섀도 모드
bl = ev["baseline_model"]["waterfall"]
chk("희석 pt = 120 - ΣB", 100 * q - sum(B), bl["steps"][0]["pt"])
chk("개조 %p = ΣB_j·r_j / 120", sum(b * r for b, r in zip(B, t["r"])) / (100 * q) * 100, bl["tech_pp"])
cpk = ev["capacity"]["plant"]["caps"]
chk("건조 처리능력 = 1/면적당 용매비", 1 / ((0.35 / 0.65) / (0.40 / 0.60)), cpk["건조"])
chk("화성 처리능력 = 20/16", 20 / 16, cpk["화성"])
chk("에이징 처리능력(무증설) = 0.95/0.90", 0.95 / 0.90, cpk["에이징"])
rg = ev["joint"]["region"]
chk("α* = (a - 84)/b", (rg["a"] - 84) / rg["b"], rg["alpha_star"])
chk("P_max(0.9) = 84 - a + 0.9b", 84 - rg["a"] + 0.9 * rg["b"], rg["p_max"][0.9])
st1 = ev["capacity"]["stages"]["stages"][0]
chk("1년차 q_t = 에이징 무증설 능력", 0.95 / 0.90, st1["q_t"])
sh = {x["days"]: x for x in ev["upside"]["shadow"]["rows"]}
chk("섀도 13일 슬롯", 1.2 * 0.9 / 0.95 * 13 / 14 - 1, sh[13]["slot_need"])
chk("섀도 10일 리드타임 h", 16 + 10 * 24, sh[10]["lead_time_h"])

print(f"\n{sum(rows)}/{len(rows)} 일치 · 추천 {run['selected']} · {run['status']}")
sys.exit(0 if all(rows) else 1)
