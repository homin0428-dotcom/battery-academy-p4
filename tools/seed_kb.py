"""초기 근거 데이터셋(seed) 작성 스크립트 - 2026-10-23 문헌 조사 결과.

모든 수치는 아래 출처를 직접 열어 확인한 값이다. 원문 접근이 막힌 문헌은 '2차 인용' 또는 '미확인'으로 둔다.
실행: python tools/seed_kb.py  → data/kb/sources.csv, effects.csv, fmea.csv 생성
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import kb_schema as S  # noqa: E402

BY = "Claude(2026-10-23 조사)"

SOURCES = [
    dict(source_id="R1", citation="Degen, F., Winter, M., Bendig, D., Tübke, J. (2023). Nature Energy 8, 1284-1295.",
         title="Energy consumption of current and future production of lithium-ion and post lithium-ion battery cells",
         doi="10.1038/s41560-023-01355-z", year=2023, source_type="논문", access="원문",
         url="https://publikationen.bibliothek.kit.edu/1000169022/152378381",
         note="KIT 공개 원문. Table 1 절감률은 '전극 면적당 전체 생산 에너지' 기준(Methods Eq.11-12). 표 텍스트 추출이 깨져 값-열 대응 재확인 권장"),
    dict(source_id="R2", citation="Wood, D. L., Li, J., An, S. J. (2019). Joule 3, 2884-2888.",
         title="Formation Challenges of Lithium-Ion Battery Manufacturing", doi="10.1016/j.joule.2019.11.002", year=2019,
         source_type="리뷰", access="초록", url="https://www.ornl.gov/publication/formation-challenges-lithium-ion-battery-manufacturing",
         note="ORNL 요약 페이지만 확인"),
    dict(source_id="R3", citation="Weng, A. et al. (2021). Joule 5, 2971-2992. (arXiv:2203.14158)",
         title="Predicting the impact of formation protocols on battery lifetime immediately after manufacturing",
         doi="10.1016/j.joule.2021.09.015", year=2021, source_type="논문", access="원문",
         url="https://arxiv.org/abs/2203.14158", note="arXiv 판으로 확인 - 학술지 판과 쪽 번호 다름"),
    dict(source_id="R4", citation="Bryntesen, S. N. et al. (2021). Energies 14, 1406.",
         title="Opportunities for the State-of-the-Art Production of LIB Electrodes - A Review", doi="10.3390/en14051406",
         year=2021, source_type="리뷰", access="원문", url="https://www.mdpi.com/1996-1073/14/5/1406", note="리뷰 - 수치는 인용 문헌 값(2차)"),
    dict(source_id="R5", citation="Rhyu, J. et al. (2025). Joule 9, 101884. (arXiv:2410.07458)",
         title="Systematic feature design for cycle life prediction of lithium-ion batteries during formation",
         doi="10.1016/j.joule.2025.101884", year=2025, source_type="논문", access="초록", url="https://arxiv.org/abs/2410.07458", note=""),
    dict(source_id="R6", citation="Guo, Y. et al. (2026). Energy 360, 141917.",
         title="Machine learning optimized integration of a transcritical CO2 heat pump for sustainable and simultaneous heating-cooling in lithium-ion battery electrode drying",
         doi="10.1016/j.energy.2026.141917", year=2026, source_type="논문", access="2차", url="",
         note="원문 접근 불가 - v10 인용만. 팀에 원문 요청"),
    dict(source_id="R7", citation="Chen, Y. et al. (2024). Energy Technology 12, 2401146.",
         title="Modeling and Optimizing the Drying Process of Electrode Manufacturing for Lithium-Ion Batteries",
         doi="10.1002/ente.202401146", year=2024, source_type="논문", access="2차", url="", note="원문 접근 불가 - 팀에 원문 요청"),
    dict(source_id="R8", citation="Lechner, M. et al. (2025). Energy Technology 13, 2402311.",
         title="Cost Model for the Footprint Planning of Production Environments in Lithium-Ion Battery Production",
         doi="10.1002/ente.202402311", year=2025, source_type="논문", access="2차", url="",
         note="원문 접근 불가 - v10 p.6 표 값을 2차 인용. 팀에 원문 요청"),
    dict(source_id="R9", citation="Schomburg, F. et al. (2024). Energy & Environmental Science 17, 2686-2733.",
         title="Lithium-ion battery cell formation: status and future directions towards a knowledge-based process design",
         doi="10.1039/D3EE03559J", year=2024, source_type="리뷰", access="원문",
         url="https://pubs.rsc.org/en/content/articlehtml/2024/ee/d3ee03559j", note="공개 리뷰 - 수치는 인용 문헌 값(2차)"),
    dict(source_id="R10", citation="U.S. Department of Energy, AMCA (2003). Improving Fan System Performance: A Sourcebook for Industry.",
         title="Improving Fan System Performance: A Sourcebook for Industry", doi="", year=2003, source_type="보고서", access="2차",
         url="", note="팬 상사법칙 근거(계산식). 수치 효과 근거 아님"),
    dict(source_id="R11", citation="Orozco, L., Liao, W. (2015). Analog Devices Technical Article.",
         title="Power Efficient Battery Formation/Testing System with Energy Recycling", doi="", year=2015, source_type="기술자료",
         access="원문", url="https://www.analog.com/en/resources/technical-articles/power-efficient-battery-testing-system-with-energy-recycling.html",
         note="장비 회사 기술자료. 90%는 장비 효율·계산 가정, 40%는 셀 2개 계산 예시"),
    dict(source_id="R12", citation="Davidsson Kurland, S. (2020). Environmental Research Communications 2, 012001.",
         title="Energy use for GWh-scale lithium-ion battery production", doi="10.1088/2515-7620/ab5e1e", year=2020,
         source_type="논문", access="원문", url="https://research.chalmers.se/publication/524468",
         note="Northvolt Ett 환경영향평가 기술보고서 기반 추정"),
    dict(source_id="R13", citation="Guddingsmo, H. et al. (2021). Proc. SIMS EUROSIM 2021, 211-218.",
         title="Energy Reduction in Lithium-Ion Battery Manufacturing using Heat Pumps and Heat Exchanger Networks",
         doi="10.3384/ecp21185211", year=2021, source_type="논문", access="원문",
         url="https://ecp.ep.liu.se/index.php/sims/article/view/347", note="NMC111, 530 MWh/년 모델 공장"),
    dict(source_id="R14", citation="Gu, Y., Tao, R., Yuan, C., Zhang, H. C., Hauschild, M. CIRP Annals (연도 미확인, 2025 추정).",
         title="A cradle-to-grave life-cycle-assessment of dry-processed Li-ion batteries for electric vehicles", doi="", year=2025,
         source_type="논문", access="원문", url="https://par.nsf.gov/servlets/purl/10585190",
         note="NSF 공개 원고. 배터리 팩 제조 에너지 기준 비중(셀 공장과 경계 다름)"),
    dict(source_id="R15", citation="Munters (2021). Charged EVs sponsored article, 2021-11-03.",
         title="How to choose the right dry room dehumidification solution for lithium-ion battery production", doi="", year=2021,
         source_type="기술자료", access="원문",
         url="https://chargedevs.com/sponsored/how-to-choose-the-right-dry-room-dehumidification-solution-for-lithium-ion-battery-production/",
         note="제습기 제조사 홍보 기사 - 제조사 주장값"),
    dict(source_id="R16", citation="Laserline/IDEEL 프로젝트 (2023). Wiley Industry News, 2023-02-02.",
         title="Reducing energy consumption in electrode production", doi="", year=2023, source_type="기술자료", access="원문",
         url="https://www.wileyindustrynews.com/en/news/reducing-energy-consumption-electrode-production",
         note="연구 프로젝트 초기 결과 보도"),
    dict(source_id="R17", citation="Zeferino, E., Yang, S., Thiede, S. (2025). Procedia CIRP 134, 1053-1058.",
         title="Assessing the impact of mini environments in lithium-ion battery production under uncertainties",
         doi="10.1016/j.procir.2025.02.233", year=2025, source_type="논문", access="초록",
         url="https://research.utwente.nl/en/publications/assessing-the-impact-of-mini-environments-in-lithium-ion-battery-",
         note="초록에 수치 없음 - 원문 PDF 확인 필요(팀 요청)"),
    dict(source_id="S0", citation="2026 배터리 아카데미 문제 4 출제서", title="공식 대회 문제 4 출제서", doi="", year=2026,
         source_type="과제", access="2차", url="", note="v10 PDF 인용으로만 확인"),
    dict(source_id="TEAM", citation="팀 판단", title="팀 가정·전문가 판단 (출처 수치 없음)", doi="", year=2026,
         source_type="기타", access="2차", url="", note="근거등급 E 전용"),
]

# 정량효과: 레버 × 지표 × 근거 1건 = 1행
E = []


def eff(**k):
    base = dict(value_low="", value_typ="", value_high="", value_before="", value_after="", boundary_share="",
                machine_elec_change="", machine_heat_change="",
                conditions_note="", entered_by=BY, note="")
    base.update(k)
    base["effect_id"] = f"EF-{len(E) + 1:03d}"
    E.append(base)


# ---- 드라이룸 (R1 Degen Table 1: 공장 전체 기준)
eff(lever_id="DRM-LOCAL", metric="system_saving_ratio", value_typ=16.1, unit="%",
    basis="전극 면적당 전체 셀 생산 에너지 대비 (2040, 기술 100% 대체 가정)", boundary="공장전체",
    chemistry="NCM", cell_format="무관", scale="모델", source_id="R1", locator="p.1290 Table 1 (Smart dry rooms: micro-environments, LIB)",
    excerpt="드라이룸 미니환경(micro-environments) 적용 시 LIB 전체 생산 에너지 −16.1%", evidence_grade="C",
    verification="원문 확인", note="표 텍스트 추출 기반 - 값-열 대응 재확인 권장")
eff(lever_id="DRM-LOCAL", metric="system_saving_ratio", value_typ=7.4, unit="%",
    basis="전극 면적당 전체 셀 생산 에너지 대비 (2040, 기술 100% 대체 가정)", boundary="공장전체",
    chemistry="NCM", cell_format="무관", scale="모델", source_id="R1", locator="p.1290 Table 1 (Smart dry rooms: macro-environments, LIB)",
    excerpt="드라이룸 매크로환경(macro-environments) 적용 시 LIB 전체 생산 에너지 −7.4%", evidence_grade="C",
    verification="원문 확인", note="표 텍스트 추출 기반 - 값-열 대응 재확인 권장")
# ---- 드라이룸 (R8 Lechner, v10 p.6 2차 인용: 드라이룸 계통 전체 기준)
eff(lever_id="DRM-LOCAL", metric="energy_before_after", value_before=46.74, value_after=37.28, unit="kWh/kWh_cell",
    basis="드라이룸 총에너지(가스+전력), 셀 kWh당 - 기준 드라이룸 vs 일부 공정 국소화", boundary="계통전체",
    chemistry="무관", cell_format="무관", scale="모델", conditions_note="이슬점 -60°C 사례 (대상 공장 -40°C와 다름), 가스+전력 합산",
    source_id="R8", locator="v10 p.6 표 (원문 미확인)", excerpt="일부 공정 국소화 46.74 → 37.28 kWh/kWh셀 (−20.2%), 총비용 +1.9%",
    evidence_grade="C", verification="2차 인용")
eff(lever_id="DRM-LOCAL", metric="energy_before_after", value_before=46.74, value_after=32.14, unit="kWh/kWh_cell",
    basis="드라이룸 총에너지(가스+전력), 셀 kWh당 - 기준 드라이룸 vs 확대 국소화", boundary="계통전체",
    chemistry="무관", cell_format="무관", scale="모델", conditions_note="이슬점 -60°C 사례, 가스+전력 합산. 총비용 +8.6%",
    source_id="R8", locator="v10 p.6 표 (원문 미확인)", excerpt="확대 국소화 46.74 → 32.14 kWh/kWh셀 (−31.2%), 총비용 +8.6%",
    evidence_grade="C", verification="2차 인용")
# ---- 드라이룸 제습 재생 (R15 제조사)
eff(lever_id="DRM-HR", metric="system_saving_ratio", value_low=30, unit="%",
    basis="제습 시스템 총에너지 - 업계 표준 퍼지 방식 대비 (공급 공기 16,320 m3/h 예시)", boundary="계통일부",
    chemistry="무관", cell_format="무관", scale="무관", source_id="R15", locator="본문 (Green PowerPurge 사례)",
    excerpt="제조사 주장: 총에너지 30% 이상 절감, 재생(reactivation) 에너지 최대 45% 절감", evidence_grade="D",
    verification="원문 확인", note="제조사 홍보값. 드라이룸 계통 중 제습기 비중 미확인 → 참고 전용")
# ---- 건조 (R1 Degen Table 1: 공장 전체 기준)
eff(lever_id="DRY-RAD", metric="system_saving_ratio", value_typ=12.3, unit="%",
    basis="전극 면적당 전체 셀 생산 에너지 대비 (2040, 기술 100% 대체 가정)", boundary="공장전체",
    chemistry="NCM", cell_format="무관", scale="모델", source_id="R1", locator="p.1290 Table 1 (NIR drying, LIB)",
    excerpt="NIR 건조 적용 시 LIB 전체 생산 에너지 −12.3%", evidence_grade="C", verification="원문 확인",
    note="표 텍스트 추출 기반 - 값-열 대응 재확인 권장")
eff(lever_id="DRY-RAD", metric="system_saving_ratio", value_typ=12.3, unit="%",
    basis="전극 면적당 전체 셀 생산 에너지 대비 (2040, 기술 100% 대체 가정)", boundary="공장전체",
    chemistry="NCM", cell_format="무관", scale="모델", source_id="R1", locator="p.1290 Table 1 (Laser drying, LIB)",
    excerpt="레이저 건조 적용 시 LIB 전체 생산 에너지 −12.3%", evidence_grade="C", verification="원문 확인",
    note="표 텍스트 추출 기반 - 값-열 대응 재확인 권장")
eff(lever_id="DRY-HSC", metric="system_saving_ratio", value_typ=7.2, unit="%",
    basis="전극 면적당 전체 셀 생산 에너지 대비 (2040, 기술 100% 대체 가정)", boundary="공장전체",
    chemistry="NCM", cell_format="무관", scale="모델", source_id="R1", locator="p.1290 Table 1 (High-solid slurry, LIB)",
    excerpt="고형분 슬러리 적용 시 LIB 전체 생산 에너지 −7.2%", evidence_grade="C", verification="원문 확인",
    note="표 텍스트 추출 기반 - 값-열 대응 재확인 권장")
eff(lever_id="DRY-DRYCOAT", metric="system_saving_ratio", value_typ=18.2, unit="%",
    basis="전극 면적당 전체 셀 생산 에너지 대비 (2040, 기술 100% 대체 가정)", boundary="공장전체",
    chemistry="NCM", cell_format="무관", scale="모델", source_id="R1", locator="p.1290 Table 1 (Dry coating, LIB)",
    excerpt="건식 코팅 적용 시 LIB 전체 생산 에너지 −18.2%", evidence_grade="C", verification="원문 확인",
    note="표 텍스트 추출 기반 - 값-열 대응 재확인 권장")
eff(lever_id="DRY-DRYCOAT", metric="system_saving_ratio", value_typ=41, unit="%",
    basis="배터리 팩 제조 1차 에너지 대비 (NMP 공정 152.9 → 건식 90.2 MJ/kg)", boundary="공장전체",
    chemistry="NCM", cell_format="무관", scale="모델", source_id="R14", locator="Sec. 3.2, Fig. 3",
    excerpt="용매·건조 제거로 팩 제조 에너지 41% 감소 (152.9 → 90.2 MJ/kg)", evidence_grade="C", verification="원문 확인",
    boundary_share=0.41, note="경계비중 0.41 = 같은 문헌의 건조 비중(Sec. 3.2). 팩 제조 경계")
eff(lever_id="DRY-HP", metric="system_saving_ratio", value_low=11, value_high=20, unit="%",
    basis="2040년 전 세계 LIB·PLIB 셀 생산 에너지 변화 (공장 60% 히트펌프 보급 가정)", boundary="복합계통",
    chemistry="무관", cell_format="무관", scale="모델", source_id="R1", locator="p.1289 본문, Fig. 5; Methods p.1293",
    excerpt="히트펌프 사용으로 11~20% 절감 (100°C 이상 COP 1.5~2.5, 공장 60% 보급 가정)", evidence_grade="C",
    verification="원문 확인", note="전 세계 생산 에너지 기준 - 계통 경계로 환산 불가, 참고 전용")
eff(lever_id="DRY-HP", metric="energy_before_after", value_before=10.2, value_after=4.1, unit="kWh/kg",
    basis="NMP 1 kg당 증발 에너지 - 기존 vs 초임계 CO2 히트펌프", boundary="계통일부",
    chemistry="무관", cell_format="무관", scale="모델", source_id="R4", locator="Sec. 3.3 (문헌 [52] 및 예비 계산)",
    excerpt="초임계 CO2 히트펌프로 NMP 증발 에너지 10.2 → 4.1 kWh/kg (약 −60%)", evidence_grade="D", verification="2차 인용",
    note="건조 계통 중 NMP 증발 에너지 비중 미확인 → 참고 전용. 공급온도 한계(최대 약 90°C) 주의")
eff(lever_id="DRY-HP", metric="cop_h", value_low=1.5, value_high=2.5, unit="-",
    basis="100°C 이상 공급 시 히트펌프 COP (분석 가정)", boundary="장비단위",
    chemistry="무관", cell_format="무관", scale="모델", source_id="R1", locator="Methods p.1293",
    excerpt="100°C 이상 온도에서 COP 1.5~2.5 가정", evidence_grade="C", verification="원문 확인",
    note="v10 모드 A의 COP_h 3.85는 이 범위보다 높음 - 공급온도 조건 확인 필요")
eff(lever_id="DRY-PKG", metric="energy_before_after", value_before=4090, value_after=1403.4, unit="kW",
    basis="건조·NMP 회수·드라이룸 열부하 합산 최대 동력 - 기준 vs 열교환망(MER-1)", boundary="복합계통",
    chemistry="NCM", cell_format="무관", scale="모델", conditions_note="NMC111, 530 MWh/년, 공급 140°C",
    source_id="R13", locator="Sec. 3.4-3.5, p.215-216", excerpt="열교환망 MER-1 적용 시 4090 → 1403.4 kW (약 −66%)",
    evidence_grade="C", verification="원문 확인", note="여러 계통 합산 → 참고 전용(계통 분리 불가)")
eff(lever_id="DRY-NMP", metric="energy_before_after", value_before=3624, value_after=2121, unit="kW",
    basis="NMP 회수 가열+냉각 부하 - 재생기(regenerator) 없음 vs 500 kW 재생기", boundary="계통일부",
    chemistry="NCM", cell_format="무관", scale="모델", conditions_note="NMC111, 530 MWh/년, 140°C 대류 건조",
    source_id="R13", locator="Sec. 3.2, p.214, Table 2", excerpt="재생기 도입 시 NMP 회수 열부하 3624 → 2121 kW (약 −41%)",
    evidence_grade="C", verification="원문 확인", note="건조 계통 중 NMP 회수 부하 비중 미확인 → 참고 전용")
eff(lever_id="DRY-RAD", metric="system_saving_ratio", value_high=85, unit="%",
    basis="전극 생산(건조) 에너지 - 순수 레이저 건조 초기 결과", boundary="계통일부",
    chemistry="무관", cell_format="무관", scale="실험실", conditions_note="시험 속도 1.3 m/min (양산 속도 아님)",
    source_id="R16", locator="본문 (2023-02-02 보도)", excerpt="순수 레이저 건조로 전극 생산 에너지 최대 85% 감소(초기 결과)",
    evidence_grade="D", verification="원문 확인", note="보도 자료·초기 결과 - 측정 경계 불명확, 참고 전용")
# ---- 화성 (R1 Degen Table 1: 공장 전체 기준)
eff(lever_id="FOR-FAST", metric="system_saving_ratio", value_typ=5.8, unit="%",
    basis="전극 면적당 전체 셀 생산 에너지 대비 (2040, 기술 100% 대체 가정)", boundary="공장전체",
    chemistry="NCM", cell_format="무관", scale="모델", source_id="R1", locator="p.1290 Table 1 (High C-rate formation, LIB)",
    excerpt="고율 화성 적용 시 LIB 전체 생산 에너지 −5.8%", evidence_grade="C", verification="원문 확인",
    note="표 텍스트 추출 기반 - 값-열 대응 재확인 권장")
eff(lever_id="FOR-FAST", metric="system_saving_ratio", value_typ=11.5, unit="%",
    basis="전극 면적당 전체 셀 생산 에너지 대비 (2040, 기술 100% 대체 가정)", boundary="공장전체",
    chemistry="NCM", cell_format="무관", scale="모델", source_id="R1", locator="p.1290 Table 1 (Adaptive formation with partial cycles, LIB)",
    excerpt="부분 사이클 적응형 화성 적용 시 LIB 전체 생산 에너지 −11.5%", evidence_grade="C", verification="원문 확인",
    note="표 텍스트 추출 기반 - 값-열 대응 재확인 권장")
# ---- 화성 시간
eff(lever_id="FOR-FAST", metric="time_before_after", value_before=56, value_after=14, unit="h",
    basis="화성 프로토콜 총 소요시간 - 기준 vs 고속 화성", boundary="계통전체",
    chemistry="NCM", cell_format="파우치", scale="파일럿", conditions_note="NMC/흑연 파우치 2.36 Ah, 셀 40개(군당 10)",
    source_id="R3", locator="Sec. 2.1", excerpt="고속 화성 14 h, 기준 화성 56 h. 고속 화성 셀의 수명이 100사이클 이상 길었음(70% 도달 기준)",
    evidence_grade="B", verification="원문 확인", note="기준 프로토콜이 길어(56h) 비율을 20h 기준 공장에 그대로 옮기면 과대")
eff(lever_id="FOR-FAST", metric="time_before_after", value_before=80, value_after=21, unit="h",
    basis="다중 사이클 화성 총 소요시간 (0.2C 부분 사이클 3.9-4.2 V)", boundary="계통전체",
    chemistry="무관", cell_format="무관", scale="실험실", source_id="R9", locator="Sec. 'Multi-cycle formation strategies' (An et al. 인용)",
    excerpt="0.2C 부분 사이클 4회로 화성 80 h → 21 h", evidence_grade="D", verification="2차 인용",
    note="리뷰가 인용한 An et al. 값 - 양극계 미기재")
# ---- 회생 (R11)
eff(lever_id="FOR-REGEN", metric="regen_efficiency", value_typ=90, unit="%",
    basis="충방전기 채널 효율 (4 V 셀, 20 A)", boundary="장비단위",
    chemistry="무관", cell_format="무관", scale="무관", source_id="R11", locator="본문 (efficiency 문단)",
    excerpt="4 V·20 A 구성에서 효율 90% 이상", evidence_grade="D", verification="원문 확인",
    note="장비 효율 - 공장 화성 절감률 아님")
eff(lever_id="FOR-REGEN", metric="system_saving_ratio", value_typ=40, unit="%",
    basis="셀 2개(3.2 V, 15 Ah) 충전 에너지 - 회생 없음 107 Wh vs 회생 63.4 Wh 계산 예시", boundary="장비단위",
    chemistry="LFP", cell_format="무관", scale="무관", source_id="R11", locator="본문 (worked example)",
    excerpt="회생 효율 90% 가정 시 셀 2개 충전 에너지 40% 이상 절감 (계산 예시)", evidence_grade="D", verification="원문 확인",
    note="이상적 짝지음 계산 예시 - 공장 값 아님. 3.2 V 셀 → LFP로 판단")
# ---- 계통 에너지 비중 (공장전체 기준 환산용)
eff(lever_id="BASE-FOR", metric="energy_share", value_high=20, unit="%",
    basis="공장 총 전력 중 화성 전력 (Northvolt Ett 예상치)", boundary="공장전체",
    chemistry="NCM", cell_format="무관", scale="양산", conditions_note="8 GWh 1호 라인, 약 15 kWh/kWh_c",
    source_id="R12", locator="Northvolt Ett 절 (Northvolt 2017b 인용)", excerpt="Northvolt은 총 전력의 최대 20%를 화성에 사용할 것으로 예상",
    evidence_grade="C", verification="원문 확인", note="'최대' 값 - 상한")
eff(lever_id="BASE-DRY", metric="energy_share", value_typ=39, unit="%",
    basis="LIB 생산 에너지 중 건조 공정 비중", boundary="공장전체",
    chemistry="무관", cell_format="무관", scale="무관", source_id="R4", locator="Abstract",
    excerpt="LIB 생산 에너지의 약 39%가 건조 공정 (그중 약 절반이 전극 건조)", evidence_grade="D", verification="원문 확인",
    note="리뷰 초록 값 - 원 출처 미기재")
eff(lever_id="BASE-DRY", metric="energy_share", value_typ=41, unit="%",
    basis="배터리 팩 제조 에너지 중 건조 비중 (NMP 공정)", boundary="공장전체",
    chemistry="NCM", cell_format="무관", scale="모델", source_id="R14", locator="Sec. 3.2",
    excerpt="NMP 공정 팩 제조에서 건조가 에너지의 41.0%", evidence_grade="C", verification="원문 확인", note="팩 제조 경계")
eff(lever_id="BASE-DRM", metric="energy_share", value_typ=44, unit="%",
    basis="배터리 팩 제조 에너지 중 드라이룸 비중 (NMP 공정)", boundary="공장전체",
    chemistry="NCM", cell_format="무관", scale="모델", source_id="R14", locator="Sec. 3.2",
    excerpt="NMP 공정 팩 제조에서 드라이룸이 최대 기여(44.0%)", evidence_grade="C", verification="원문 확인", note="팩 제조 경계")
F = []


def fm(**k):
    base = dict(burden_low="", burden_typ="", burden_high="", unit="", locator="", excerpt="", entered_by=BY, note="")
    base.update(k)
    base["fmea_id"] = f"FM-{len(F) + 1:03d}"
    F.append(base)


fm(lever_id="FOR-FAST", failure_mode="음극 리튬 석출(plating)", mechanism="고전류 충전에서 흑연 음극 전위가 0 V vs Li 아래로 내려감",
   affected="품질;안전", control_action="C-rate·CV 구간 상한 설정, 3전극 셀로 음극 전위 확인",
   detection_method="3전극 음극 전위, 방전 용량, 임피던스, 사이클 유지율", burden_metric="none",
   quality_gate="양산 셀 형태에서 석출 없음 확인 (Drees: 1.5C CC-CV에서 석출, Münster: 2C에서만 석출)",
   source_id="R9", locator="Sec. 'Single-cycle formation strategies' (Drees, Mao, Münster 인용)",
   excerpt="1.5C CC-CV 후 석출과 용량 저하(Drees), 0.5C에서도 석출(Mao)", evidence_grade="D", verification="2차 인용")
fm(lever_id="FOR-FAST", failure_mode="가스 발생·불균일 SEI", mechanism="두꺼운 전극·대형 셀에서 가스 배출 지연, 국부 석출 유발",
   affected="품질", control_action="적정 예비 충전, 조기 탈기, 외부 가압",
   detection_method="가스 성분·양 분석, 탈기 전후 비교, 외관", burden_metric="none",
   quality_gate="대상 파우치 형상에서 탈기 조건 확정", source_id="R9", locator="Sec. 'Degassing' (Ellis 등 인용)",
   excerpt="대형·후막 셀에서 가스가 고속 화성의 제약. 파우치 불규칙 석출은 예비충전·조기 탈기·가압으로 방지", evidence_grade="D",
   verification="2차 인용")
fm(lever_id="FOR-FAST", failure_mode="화성 효율 저하·리튬 손실 증가", mechanism="고속 화성이 더 많은 리튬을 SEI 형성에 소모",
   affected="품질", control_action="초기 용량·화성 쿨롱효율 허용 범위 설정",
   detection_method="화성 쿨롱효율, 초기 방전 용량, SEI 리튬 손실량", burden_metric="none",
   quality_gate="화성 효율 저하(문헌 −0.8%p)와 용량 저하(−0.3%)가 제품 규격 안인지",
   source_id="R3", locator="Sec. 2.3.1, Table 1",
   excerpt="화성 쿨롱효율 87.3 → 86.5%, SEI 리튬 손실 +6.6%, 방전 용량 −0.3% (대신 수명은 증가)", evidence_grade="B",
   verification="원문 확인")
fm(lever_id="FOR-FAST", failure_mode="고온 수명 말기 셀 팽창", mechanism="고속 화성 SEI의 고온 안정성 차이",
   affected="품질;안전", control_action="45°C 사이클·고온 보관 시험 포함",
   detection_method="고온 사이클 중 두께·팽창 측정", burden_metric="none",
   quality_gate="45°C 장기 시험에서 팽창 허용 기준 통과", source_id="R9", locator="Sec. 'Ageing and capacity' (Weng 인용)",
   excerpt="고속 화성은 상온·45°C 수명을 개선했으나 45°C 수명 말기에 팽창 발생", evidence_grade="D", verification="2차 인용")
fm(lever_id="FOR-DATA", failure_mode="저 SOC 저항 기반 수명 판정 오류", mechanism="R_LS(5% SOC 10초 저항)와 수명 상관이 셀·공정에 따라 달라짐",
   affected="품질;시간", control_action="대상 셀로 상관 재검증 후에만 판정 대체 후보로 사용",
   detection_method="R_LS 측정(HPPC 1회 진단 사이클), 예측 오차 추적", burden_metric="added_occupancy_h", unit="h",
   quality_gate="대상 셀에서 상관(문헌 ρ=−0.84)과 예측 오차(문헌 6.9~8.0%) 재현",
   source_id="R3", locator="Sec. 2.3.2, 2.4", excerpt="R_LS가 수명과 ρ=−0.84로 유일하게 의미 있는 상관. 진단 사이클 1회 필요",
   evidence_grade="B", verification="원문 확인",
   note="10초 펄스 ≠ 검사 10초: SOC 5% 조정·온도 안정화·취급 시간이 별도로 필요하며 원문에서 미확인 → 부담 미정량. "
        "미세단락 검출·에이징 대체 근거로 확대하지 않음")
fm(lever_id="FOR-DATA", failure_mode="화성 Q(V) 특징 기반 수명 예측 오류", mechanism="화성 온도·입자 저항 불균일에 따라 특징 구간이 달라짐",
   affected="품질", control_action="대상 공정 데이터로 특징 재설계·오차 검증",
   detection_method="예측 오차 추적, 불합격 셀 미검출·정상 셀 과잉 배제 비율", burden_metric="none",
   quality_gate="대상 셀에서 예측 오차(문헌 중앙값 9.20%) 재현", source_id="R5", locator="Abstract",
   excerpt="추가 진단 사이클 없이 화성 Q(V) 특징 2개로 수명 예측, 중앙 오차 9.20%", evidence_grade="B", verification="초록 확인")
fm(lever_id="FOR-REGEN", failure_mode="회생 전력 미사용(충방전 시점 불일치)", mechanism="방전 에너지를 같은 시각 충전 중인 채널이 받아야 재사용 가능",
   affected="전력", control_action="채널 스케줄링, 버스 전압·동시 사용 비율 실측",
   detection_method="회생 전력량·동시 사용 비율 계측", burden_metric="none",
   quality_gate="동시 사용 가능 비율 실측 후 화성 절감률 산정 (장비 효율 90%를 공장 절감률로 쓰지 않음)",
   source_id="R11", locator="본문", excerpt="방전 에너지를 다른 셀 충전에 재사용하는 구조. 효율 90%는 장비 값", evidence_grade="D",
   verification="원문 확인")
fm(lever_id="DRY-ZONE", failure_mode="바인더 이동(접착력·저항 악화)", mechanism="고온·고속 건조에서 바인더가 표면으로 이동",
   affected="품질", control_action="구간별 온도·건조속도 상한, 후막 전극 조건 별도 관리",
   detection_method="박리 강도, 전극 저항, 단면 바인더 분포", burden_metric="none",
   quality_gate="건조 온도 80°C 초과·두께 150 µm 초과 조건에서 접착·저항 확인", source_id="R4", locator="Sec. 3.2",
   excerpt="80°C 초과·두께 150 µm 초과 시 바인더 이동 문제가 뚜렷. 산업 건조속도 >1.5 g/m2·s", evidence_grade="D",
   verification="2차 인용")
fm(lever_id="DRY-AIR", failure_mode="배기 NMP 농도 상승(폭발 하한 접근)", mechanism="풍량 저감으로 용매 증기 희석 부족",
   affected="안전;품질", control_action="배기 농도 감시·인터록, 우회 운전 기준",
   detection_method="배기 NMP 농도 연속 측정", burden_metric="none",
   quality_gate="배기 용매 증기 LFL의 25% 이하 유지 (문헌: NMP 약 1.1%)", source_id="R4", locator="Sec. 3.3 (문헌 [52])",
   excerpt="용매 증기는 폭발 하한(LFL)의 25% 미만으로 유지해야 함", evidence_grade="D", verification="2차 인용")
fm(lever_id="DRY-ZONE", failure_mode="잔류 수분·용매 과다", mechanism="구간 온도·체류시간 축소로 건조 불충분",
   affected="품질", control_action="후건조 조건 유지, 잔류량 검사",
   detection_method="잔류 수분(ppm)·잔류 NMP 측정", burden_metric="none",
   quality_gate="잔류 수분 약 50 ppm 수준 유지 (약 500 ppm에서 빠른 열화 보고)", source_id="R4", locator="Sec. 3.1 (문헌 [112], [163])",
   excerpt="약 50 ppm 건조 셀은 NMP 공정 셀과 동등, 약 500 ppm에서 빠른 열화", evidence_grade="D", verification="2차 인용")
fm(lever_id="DRY-HP", failure_mode="히트펌프 공급온도 부족", mechanism="일반 히트펌프 70~75°C, 초임계 CO2 최대 약 90°C인데 산업 건조는 120°C 이상 필요",
   affected="전력", control_action="히트펌프는 예열·저온 구간에만 적용, 고온 구간 보조열 유지",
   detection_method="구간별 요구 온도·공급 온도 비교", burden_metric="added_power_ratio", unit="ratio",
   quality_gate="구간별 요구 온도 ≤ 히트펌프 공급 온도인 구간만 히트펌프 열 인정",
   source_id="R4", locator="Sec. 3.3", excerpt="산업 전극 건조는 120°C 이상 필요. 히트펌프 70~75°C, CO2 초임계 최대 90°C",
   evidence_grade="D", verification="2차 인용", note="보조열 전력 부담은 미정량")
fm(lever_id="DRY-HSC", failure_mode="크랙·도포 불균일", mechanism="고형분·고로딩에서 건조 응력 증가",
   affected="품질", control_action="로딩·고형분 상한, 건조 속도 조정",
   detection_method="크랙 검사, 두께 균일도", burden_metric="none",
   quality_gate="대상 로딩에서 임계 두께 확인 (수계 NMC111 20~23 mg/cm2까지 크랙 증가 보고)", source_id="R4", locator="Sec. 3.2 (문헌 [79])",
   excerpt="로딩 20~23 mg/cm2까지 크랙 악화(수계 NMC111)", evidence_grade="D", verification="2차 인용")
fm(lever_id="DRM-LOCAL", failure_mode="미니환경 경계 수분 유입", mechanism="이송·출입 시 국소 환경 경계에서 습기 침투",
   affected="품질", control_action="에어록·차압·이슬점 지도, 최악 출입 복구 점검",
   detection_method="구역별 이슬점 연속 측정, 출입 후 복구 시간", burden_metric="added_power_ratio", unit="ratio",
   quality_gate="전극 노출 구역 이슬점 -40°C 이하 유지 (과제 조건)", source_id="S0", locator="v10 p.2",
   excerpt="조립동 이슬점 -40°C 이하, 24시간 운전 (과제 조건)", evidence_grade="E", verification="2차 인용",
   note="경계 관리 전력 부담 미정량 - R17 원문(미니환경 불확실성 평가) 확인 시 보완")
fm(lever_id="AGE-RACK", failure_mode="온도 불균일·추적성·방재 문제", mechanism="랙·버퍼 전환 공간의 온도 분포와 동선 차이",
   affected="품질;안전;공간", control_action="구역별 온도 균일성·추적성·방재 검토 후 승인 슬롯만 계산",
   detection_method="구역 온도 지도, 추적 시스템 점검", burden_metric="none",
   quality_gate="승인된 유효 슬롯만 전환 가능 공간으로 인정", source_id="R8", locator="v10 p.4",
   excerpt="온도 균일성·방재·동선·추적 조건을 만족하는 공간만 유효 슬롯", evidence_grade="E", verification="2차 인용")


# ---- 공장 전력 원단위 (연간 절감 전력량·금액 환산용, 반드시 전력 기준)
eff(lever_id="BASE-PLANT", metric="plant_electricity_intensity", value_low=50, value_high=65, unit="kWh/kWh_cell",
    basis="GWh급 공장의 셀 kWh당 전력 사용량 (채굴·소재 제외)", boundary="공장전체",
    chemistry="NCM", cell_format="무관", scale="양산", conditions_note="Northvolt Ett(EIA 추정)·Tesla Gigafactory 1(역산) 두 공장",
    source_id="R12", locator="Abstract, Fig. 1", excerpt="두 공장은 배터리 용량 kWh당 약 50~65 kWh(180~230 MJ)의 전력을 사용",
    evidence_grade="C", verification="원문 확인", note="양산 공장 추정치 - 대상 공장 실측으로 교체 필요")
eff(lever_id="BASE-PLANT", metric="plant_electricity_intensity", value_low=20, value_high=29, unit="kWh/kWh_cell",
    basis="Ni계 LIB 셀 생산 에너지 (전력+열, kWh_prod/kWh_cell)", boundary="공장전체",
    chemistry="NCM", cell_format="무관", scale="모델", source_id="R1", locator="p.1287 Fig. 3",
    excerpt="Ni계 LIB 셀 생산 에너지 20~29 kWh_prod/kWh_cell", evidence_grade="C", verification="원문 확인",
    note="전력+열 합산 → 전력 원단위로 쓰지 않음(참고)")

# =============================================================== 2026-10-24 출제 참고논문 6편 원문 재확인
BY2 = "Claude(2026-10-24 출제 논문 원문 확인)"
SOURCES += [
    dict(source_id="R18", citation="Liu, Y., Zhang, R., Wang, J., Wang, Y. (2021). iScience 24, 102332.",
         title="Current and future lithium-ion battery manufacturing", doi="10.1016/j.isci.2021.102332", year=2021,
         source_type="리뷰", access="원문", url="", note="출제 제공 참고논문. Table 1 에너지 비중은 Yuan et al.(2017) LMO 파일럿 실측 인용"),
    dict(source_id="R19", citation="Örüm Aydin, A., Zajonz, F., Günther, T., Dermenci, K. B., Berecibar, M., Urrutia, L. (2023). Batteries 9, 555.",
         title="Lithium-Ion Battery Manufacturing: Industrial View on Processing Challenges, Possible Solutions and Recent Advances",
         doi="10.3390/batteries9110555", year=2023, source_type="리뷰", access="원문", url="",
         note="출제 제공 참고논문. SVOLT 유럽 산업 관점 리뷰"),
]
_SRC_PATCH = {
    "R1": dict(note="출제 제공 참고논문. Table 1(p.1289)을 원본 이미지로 확인(2026-10-24): 값-열 대응 일치. "
                    "절감률은 '전극 면적당 전체 생산 에너지(전력+열)' 기준. 같은 표의 설비 전기·열 변화율 열로 계통 비중 역산 가능"),
    "R2": dict(access="원문", note="출제 제공 참고논문(원문 PDF 확인). 출제서 'ORNL 3~7일·최대 2주·면적 25%' 문장의 출처"),
    "R3": dict(note="출제 제공 참고논문(arXiv판 원문 확인) - 학술지 판과 쪽 번호 다름. 고속 화성은 R2(ORNL) 프로토콜을 사용"),
    "R4": dict(note="출제 제공 참고논문. 출제서 '건조 관련 39%, 그 절반이 전극건조' 문장의 출처. 리뷰라 세부 수치는 인용 문헌 값"),
    "S0": dict(access="원문", note="출제서 PDF 원문 확인(2026-10-24). C사 조건·전력 배분(건조35/드라이룸25/화성·에이징15/기타25)"),
}
for _s in SOURCES:
    _s.update(_SRC_PATCH.get(_s["source_id"], {}))

# R1 Table 1 재확인: 같은 표의 '설비 전기·열 변화율' 열로 Degen 기준 공정의 계통 비중을 역산 → 동일 문헌 비중 환산
#  건조 : 고형분(전기+50%,열-33%)=-7.2, NIR·레이저(전기+566%,열-100%)=-12.3, 건식(전기+310%,열-100%)=-18.2
#         → 열 25.35 + 전기 2.31 = 27.6% (네 행 모두 0.1%p 이내로 재현)
#  드라이룸: 미니 16.1/0.65 = 매크로 7.4/0.30 = 스마트 3.7/0.15 = 24.7%
#  화성 : 고율 5.8/0.25 = 23.2%, 적응형 11.5/0.50 = 23.0% → 23.1%
DEGEN_SHARE = {"건조": 0.276, "드라이룸": 0.247, "화성": 0.231}
_SYS = {"DRY": "건조", "DRM": "드라이룸", "FOR": "화성"}
_MACHINE = {"High-solid": "설비 전기 +50%, 열 -33%", "NIR": "설비 전기 +566%, 열 -100%",
            "Laser": "설비 전기 +566%, 열 -100%", "Dry coating": "설비 전기 +310%, 열 -100%",
            "micro": "설비 전기·열 -65%", "macro": "설비 전기·열 -30%",
            "High C-rate": "설비 전기 -25%", "Adaptive": "설비 전기 -50%"}
# Table 1 'Assumed electric / thermal energy consumption of machine' 열 (비율). 열이 n/a인 화성은 빈칸
_MACHINE_NUM = {"High-solid": (0.50, -0.33), "NIR": (5.66, -1.0), "Laser": (5.66, -1.0), "Dry coating": (3.10, -1.0),
                "micro": (-0.65, -0.65), "macro": (-0.30, -0.30), "High C-rate": (-0.25, ""), "Adaptive": (-0.50, "")}
for _r in E:
    if _r["source_id"] == "R1" and "Table 1" in _r["locator"]:
        _r["locator"] = _r["locator"].replace("p.1290", "p.1289")
        _sys = _SYS[_r["lever_id"].split("-")[0]]
        _r["boundary_share"] = DEGEN_SHARE[_sys]
        _mc = next((v for k, v in _MACHINE.items() if k in _r["locator"]), "")
        _r["note"] = (f"원본 표 이미지로 값 확인(2026-10-24). {_mc}. 경계비중 {DEGEN_SHARE[_sys]:.3f}는 같은 표의 설비 변화율로 역산한 "
                      f"Degen 기준공정의 {_sys} 비중(동일 문헌 환산)")
        _mx = next((v for k, v in _MACHINE_NUM.items() if k in _r["locator"]), None)
        if _mx:
            _r["machine_elec_change"], _r["machine_heat_change"] = _mx
        if _sys == "건조" and ("NIR" in _r["locator"] or "Laser" in _r["locator"]):
            _r["note"] += ". 주의: 열을 전기로 대체 - 건조 가열이 전기식이 아니면 공장 전력은 오히려 증가"

eff(lever_id="DRM-DEW", metric="system_saving_ratio", value_typ=3.7, unit="%", boundary_share=DEGEN_SHARE["드라이룸"],
    machine_elec_change=-0.15, machine_heat_change=-0.15,
    basis="전극 면적당 전체 셀 생산 에너지 대비 (2040, 기술 100% 대체 가정)", boundary="공장전체",
    chemistry="NCM", cell_format="무관", scale="모델", source_id="R1", locator="p.1289 Table 1 (Smart dry rooms, LIB)",
    excerpt="필요할 때만 제습(air is dehumidified only when required) 시 LIB 전체 생산 에너지 −3.7% (설비 전기·열 −15%)",
    evidence_grade="C", verification="원문 확인", entered_by=BY2,
    note="수요 기반 제습 운전을 '이슬점 설정·운전 최적화' 레버에 대응. 경계비중 0.247은 같은 표에서 역산한 드라이룸 비중")
for _sys, _v, _x in (("BASE-DRY", 27.6, "건조 27.6% (고형분·NIR·레이저·건식 4개 행의 설비 전기·열 변화율로 역산)"),
                     ("BASE-DRM", 24.7, "드라이룸 24.7% (미니·매크로·스마트 3개 행으로 역산, 출제서 C사 25%와 거의 같음)"),
                     ("BASE-FOR", 23.1, "화성 23.1% (고율·적응형 2개 행으로 역산)")):
    eff(lever_id=_sys, metric="energy_share", value_typ=_v, unit="%", basis="Degen 기준 LIB 공정의 단계별 에너지 비중(전력+열) - 표에서 역산",
        boundary="공장전체", chemistry="NCM", cell_format="무관", scale="모델", source_id="R1", locator="p.1289 Table 1 (역산)",
        excerpt=_x, evidence_grade="C", verification="원문 확인", entered_by=BY2, note="원문에 직접 적힌 비중이 아니라 표 값으로 계산한 값")
eff(lever_id="DRY-RAD", metric="system_saving_ratio", value_typ=50, unit="%",
    basis="전극 건조 에너지 (450 W·1,070 nm 파이버 레이저 적용)", boundary="계통전체",
    chemistry="무관", cell_format="무관", scale="실험실", source_id="R18", locator="p.7 'Coating and drying' (Pfleging 2018 인용)",
    excerpt="450 W/1,070 nm 파이버 레이저로 건조 에너지 소비를 절반으로 줄일 수 있음", evidence_grade="D",
    verification="2차 인용", entered_by=BY2, note="실험실 규모 인용값 - 양산 건조로 적용성 미확인")
eff(lever_id="DRY-ZONE", metric="drying_time_ratio", value_typ=0.60, unit="ratio",
    basis="전극 건조시간 - 3단 건조(초기·말기 고속, 중간 저속) vs 기존", boundary="계통전체",
    chemistry="무관", cell_format="무관", scale="실험실", source_id="R18", locator="p.7 'Coating and drying' (Jaiser 2017 인용)",
    excerpt="3단 건조 전략으로 건조시간 40% 단축, 중간 저속 구간이 바인더 이동을 막음", evidence_grade="D",
    verification="2차 인용", entered_by=BY2,
    note="에너지 절감률이 아니라 시간 근거 - 코팅속도 1.2배(건조시간비 0.83 필요) 대응 가능성의 참고")
eff(lever_id="DRY-HSC", metric="drying_time_ratio", value_typ=0.56, unit="ratio",
    basis="고형분 55→75% 슬러리의 건조 속도 (시간비 = 1/1.8)", boundary="계통전체",
    chemistry="무관", cell_format="무관", scale="실험실", source_id="R18", locator="p.6 'Coating and drying' (Haarmann 2019 인용)",
    excerpt="고형분을 55%에서 75%로 높이면 건조 속도가 최대 80% 증가 (압출 도포 필요)", evidence_grade="D",
    verification="2차 인용", entered_by=BY2, note="고점도 슬러리는 기존 슬롯다이로 도포 불가 - 압출 방식 필요(설비 조건)")
eff(lever_id="FOR-FAST", metric="formation_time_ratio", value_typ=0.50, unit="ratio",
    basis="화성시간 - 상한 전압 4.2→3.7 V", boundary="계통전체",
    chemistry="기타", cell_format="무관", scale="실험실", conditions_note="LCO/흑연 셀", source_id="R18",
    locator="p.10 'Formation and aging' (Lee 2004 인용)", excerpt="상한 전압을 4.2에서 3.7 V로 낮추면 LCO/흑연 셀의 화성시간이 절반",
    evidence_grade="D", verification="2차 인용", entered_by=BY2, note="LCO 화학 - NCM 대상 공장에는 적용 제외(참고)")
eff(lever_id="FOR-FAST", metric="formation_time_ratio", value_typ=round(1 / 8.5, 4), unit="ratio",
    basis="화성시간 - ORNL 초고속 화성(14 h) vs 0.05C 3사이클 기준", boundary="계통전체",
    chemistry="NCM", cell_format="파우치", scale="파일럿", conditions_note="NMC532/흑연 1.5 Ah 파우치", source_id="R2",
    locator="p.2885-2886, Fig. 1", excerpt="초고속 화성 14 h - 0.05C/0.05C 3사이클 기준보다 8.5배 빠름",
    evidence_grade="B", verification="원문 확인", entered_by=BY2,
    note="기준(0.05C 3사이클 ≈ 120 h)이 매우 느려 비율을 20 h 공장에 그대로 옮기면 과대. R3(Weng)과 같은 프로토콜 계열 - 독립 근거 아님")
for _lid, _v, _x in (("BASE-DRY", 46.84, "건조·용매회수 46.84%"), ("BASE-DRM", 29.37, "드라이룸 29.37%"),
                     ("BASE-FOR", 0.53, "화성·에이징 0.53%")):
    eff(lever_id=_lid, metric="energy_share", value_typ=_v, unit="%", basis="32 Ah LMO/흑연 셀 파일럿 생산 실측 에너지 비중",
        boundary="공장전체", chemistry="LMO", cell_format="무관", scale="파일럿", conditions_note="Johnson Controls 파일럿(Yuan 2017)",
        source_id="R18", locator="p.3 Table 1", excerpt=_x, evidence_grade="C", verification="2차 인용", entered_by=BY2,
        note="LMO 파일럿 - 대상(NCM) 화학과 달라 적용 제외. 화성 비중이 문헌마다 0.5~23%로 크게 다름")
eff(lever_id="DRY-DRYCOAT", metric="system_saving_ratio", value_high=47, unit="%",
    basis="건조 단계 제거 시 에너지 절감 (기준 경계 원문 미기재)", boundary="복합계통",
    chemistry="무관", cell_format="무관", scale="무관", source_id="R19", locator="p.14 Sec. 3.1 Dry-Coating Technology (문헌 [37] 인용)",
    excerpt="건조 단계가 없어 최대 47% 에너지 절감, 제조원가 19% 절감", evidence_grade="D", verification="2차 인용",
    entered_by=BY2, note="절감 기준 경계 불명 → 참고 전용")

fm(lever_id="FOR-FAST", failure_mode="초기 정격용량 저하(등급 판정 왜곡)", mechanism="빠른 첫 방전으로 화성 방전용량이 낮게 측정됨",
   affected="품질", control_action="정격용량 판정 C-rate 통일, 고속 화성 셀의 첫 방전 조건 별도 관리",
   detection_method="동일 C-rate 용량 재측정, 기준 프로토콜 셀과 비교", burden_metric="none",
   quality_gate="정격용량 차이 7% 이내 확인 후 등급 기준 재설정", source_id="R2", locator="p.2886-2887, Fig. 2",
   excerpt="14 h 화성 146 mAh/g vs 기준 168 mAh/g(−13%), 첫 충방전을 0.2C/0.33C로 늦추면 차이 −7%",
   evidence_grade="B", verification="원문 확인", entered_by=BY2)
fm(lever_id="AGE-EARLY", failure_mode="자가방전·미세단락 검출력 저하", mechanism="에이징 OCV 감시 기간이 줄어 누설전류가 충분히 감쇠·분리되기 전에 판정",
   affected="품질;안전", control_action="단축 판정 셀 일부를 14일 대조군으로 병행 보관, 정밀 누설전류 측정 장비 도입",
   detection_method="OCV 감소율, 정밀 누설전류, 단축·기존 판정 불일치율", burden_metric="none",
   quality_gate="단축 판정과 14일 판정의 불량 판정 일치(누락 0건) 확인 전 단축 적용 금지",
   source_id="R19", locator="p.5 Sec. 2 (aging·final grading)",
   excerpt="에이징 중 OCV로 자가방전율을 계산하며 높은 값은 내부 단락을 뜻함. 화성 후 누설전류를 판정하면 에이징을 크게 줄일 수 있음(R2 p.2887)",
   evidence_grade="D", verification="원문 확인", entered_by=BY2)

# 에너지 종류 (과제 목표는 전력 원단위) - 원문 기준
CARRIER_BY_SOURCE = {"R1": "합산", "R8": "합산", "R15": "합산", "R16": "합산", "R14": "1차에너지", "R13": "열",
                     "R11": "전력", "R12": "전력", "R3": "무관", "R9": "무관"}
CARRIER_BY_ID = {}   # 행별 예외 (아래에서 채움)


def _carrier(r):
    if r["metric"] in ("cop_h", "time_before_after", "formation_time_ratio", "drying_time_ratio"):
        return "무관"
    if r["source_id"] == "R4":
        return "열" if r["metric"] == "energy_before_after" else "합산"
    if r["source_id"] == "R1" and r["metric"] == "plant_electricity_intensity":
        return "합산"
    return CARRIER_BY_SOURCE.get(r["source_id"], "")


# ---- 2026-10-25 에이징 단축 근거 (팀 제공 PDF 원문 확인)
SOURCES.append(dict(source_id="R20", citation="Roth, T., Streck, L., Mujanovic, N., Winter, M., Niehoff, P., Jossen, A. (2023). J. Electrochem. Soc. 170, 080524.",
                    title="Transient Self-Discharge after Formation in Lithium-Ion Cells: Impact of State-of-Charge and Anode Overhang",
                    doi="10.1149/1945-7111/acf164", year=2023, source_type="논문", access="원문", url="",
                    note="NMC622/흑연 단층 파우치(실험실) + 5 Ah 파일럿 셀 89개 사례. 화성 직후 자가방전 과도 거동과 SOC 영향"))
eff(lever_id="AGE-EARLY", metric="aging_days_before_after", value_before=14, value_after=round(50 / 24, 2), unit="day",
    basis="자가방전 전류 측정 기간 - 기존 에이징 14일(C사) vs SOC 10%에서 안정 측정(50 h)", boundary="계통일부",
    chemistry="NCM", cell_format="파우치", scale="실험실", conditions_note="NMC622/흑연 단층 파우치, SOC 10%, 전압 감쇠법(1 μV 분해능)",
    source_id="R20", locator="p.7 Fig. 4d 및 본문 'In summary'",
    excerpt="SOC10에서는 약 50 h 안에 1 μA 수준의 신뢰할 만한 자가방전 전류를 구할 수 있었음. 낮은 SOC 측정이 소프트 쇼트·결함에 더 민감해 이상 셀을 더 빨리 검출할 수 있을 것(제안)",
    evidence_grade="C", verification="원문 확인", entered_by="Claude(2026-10-25 팀 제공 PDF)",
    note="측정 단계의 시간 근거일 뿐 불량 검출력은 검증되지 않음(결함 셀 시험 없음). SOC10 전류도 20주 동안 계속 감소 → 참고 전용(계통일부)")
fm(lever_id="AGE-EARLY", failure_mode="화성 직후 과도 자가방전이 불량 신호를 가림",
   mechanism="SEI 성장·음극 오버행 평형으로 화성 후 수 주간 자가방전 전류가 정상 셀에서도 크게 변함(5 Ah 파일럿 셀 첫 주 약 130 μA → 4주 60 μA)",
   affected="품질", control_action="자가방전 측정을 낮은 SOC(약 10%)에서 수행해 과도 성분을 줄임, 오버행 설계값 확인",
   detection_method="전압 감쇠법 또는 정전위법 자가방전 전류, SOC별 비교", burden_metric="none",
   quality_gate="대상 다층 파우치 셀에서 저 SOC 단축 측정의 불량 판정이 14일 판정과 일치함을 대조군으로 확인",
   source_id="R20", locator="p.2-3 서론·Fig. 1c, p.7 'In summary', p.10 결론 1",
   excerpt="에이징에서 가장 오래 걸리는 단계는 자가방전 측정으로 2~4주 소요 - 자가방전률의 과도 거동 때문. 낮은 SOC에서 과도 거동이 작아 결함에 더 민감",
   evidence_grade="C", verification="원문 확인", entered_by="Claude(2026-10-25 팀 제공 PDF)")

SOURCES.append(dict(source_id="R21", citation="Liao, H., Huang, B., Cui, Y., Qin, H., Liu, X., Xu, H. (2022). Journal of Energy Storage 55, 105431.",
                    title="Research on a fast detection method of self-discharge of lithium battery", doi="10.1016/j.est.2022.105431",
                    year=2022, source_type="논문", access="원문", url="",
                    note="LFP 재사용(echelon) 팩 33.8 Ah, 2병렬 12직렬 셀 12개. 100% SOC에서 12~24 h OCV 차로 자가방전 큰 셀 선별 → 30일 결과와 비교"))
eff(lever_id="AGE-EARLY", metric="aging_days_before_after", value_before=30, value_after=1, unit="day",
    basis="자가방전 큰 셀 선별에 필요한 휴지 기간 - 30일 OCV 감시 vs 12~24 h OCV 차 + 셀별 임계값", boundary="계통전체",
    chemistry="LFP", cell_format="기타", scale="실험실", conditions_note="노화된 LFP 재사용 팩(2P12S, 33.8 Ah), 셀 12개, 100% SOC, 결함 셀을 일부러 넣은 시험 아님",
    source_id="R21", locator="p.1 초록, p.3 Sec. 2.2.1, p.6-7 Fig. 8-9",
    excerpt="24 h 안의 OCV 분석으로 고른 자가방전 큰 셀(4·5번)이 30일 휴지 결과와 같았고, 4·5번은 2일 만에 임계값을 넘음",
    evidence_grade="D", verification="원문 확인", entered_by="Claude(2026-10-25 팀 제공 PDF)",
    note="LFP·재사용 팩이라 NCM 신품 셀 에이징에는 적용 제외. 표본 12개, 통계적 검출률 없음 → 방향성 참고만")

# ---- 2026-10-25 팀 3차 검토 반영: Lechner(R8) EF-003·004는 '공장 전체·전기+가스 합산' 모델값
for _r in E:
    if _r["source_id"] == "R8" and _r["metric"] == "energy_before_after":
        _r["boundary"] = "공장전체"
        _r["basis"] = _r["basis"].replace("드라이룸 총에너지(가스+전력)", "공장 전체 에너지(전기+가스)")
        _r["conditions_note"] = "15 GWh 모델 공장, NMC811 4680 원통형, 이슬점 -60°C 시나리오, 전기+가스 합산 (대상 -40°C·파우치와 다름)"
        _r["boundary_share"] = 0.71
        _r["chemistry"], _r["cell_format"] = "NCM", "원통형"
        _r["verification"] = "원문 확인"
        _r["locator"] = "p.8 §4.3 본문, p.9 Fig. 6(b) (Sc2 → Sc4/Sc5)"
        _r["conditions_note"] += ". 드라이룸 범위가 양극 생산까지 포함"
        _r["note"] = ("팀 원문 확인(2026-10-25): 공장 전체(전기+가스) 값. Sc2(-60°C)에서 드라이룸이 공장 에너지의 71% → 경계비중 0.71(같은 문헌). "
                      "§4.4는 드라이룸을 가스 85%/전기 15%, 미니환경을 100% 전기로 봄 → 가스 가열 시나리오는 전력 절대 증감 행으로 따로 반영")

# ---- 가스·스팀 가열 시나리오 전용: 전력 절대 증감 (팀 원문 확인 2026-10-25)
for _lab, _d, _x in (("NIR", 2.204 - 0.92, "열풍 기준선 전기 0.92 → NIR 2.204 kWh/kWh_cell"),
                     ("레이저", 5.51 - 0.92, "열풍 기준선 전기 0.92 → 레이저 5.51 kWh/kWh_cell")):
    eff(lever_id="DRY-RAD", metric="electricity_delta_abs", value_typ=round(_d, 3), unit="kWh/kWh_cell",
        basis=f"가스 가열 열풍 건조(천연가스 10.09 + 전기 0.92 kWh/kWh_cell)를 {_lab} 건조로 바꿀 때 건조 전력 증가", boundary="계통전체",
        chemistry="무관", cell_format="무관", scale="모델",
        conditions_note=f"Schütte 2024 Table 3 기준선은 Ref.[8] 인용 모델값. 기준 건조 전기 0.92 대비 {_d / 0.92 * 100:+.1f}%",
        source_id="CL-R01", locator="§3.3, Table 3", excerpt=_x, evidence_grade="D", verification="원문 확인",
        entered_by="Claude(팀 원문 확인값 2026-10-25)", note="가스·스팀 가열 시나리오에서만 계산에 사용. 공장 전력 원단위(R12 50~65)로 나눠 환산")
eff(lever_id="DRM-LOCAL", metric="electricity_delta_abs", value_typ=2.9, unit="kWh/kWh_cell",
    basis="드라이룸 가스 85%/전기 15% 기준에서 미니환경(100% 전기)으로 국소화(Sc4) 시 환경 설비 전력 6.4 → 9.3 kWh/kWh_cell", boundary="계통전체",
    chemistry="NCM", cell_format="원통형", scale="모델",
    conditions_note=f"Lechner 15 GWh 4680 모델, 이슬점 -60°C. 기준 환경 설비 전기 6.4 대비 {2.9 / 6.4 * 100:+.1f}%",
    source_id="R8", locator="p.9 §4.4 (팀원 계산)", excerpt="드라이룸 가스 85%·전기 15%, 미니환경 100% 전기 가정 → Sc4 환경 설비 전기 약 6.4 → 9.3",
    evidence_grade="C", verification="원문 확인", entered_by="Claude(팀원 계산값 2026-10-25)",
    note="가스·스팀 가열 시나리오에서만 사용. 팀원이 원문 비율로 계산한 값 - 표에 직접 있는 수치 아님")

# R18 레이저 건조 '에너지 절반'·R19 건식 '에너지 47%'는 전력·열 구분이 없는 총에너지 → 합산
for _r in E:
    if _r["source_id"] in ("R18", "R19") and _r["metric"] == "system_saving_ratio":
        CARRIER_BY_ID[_r["effect_id"]] = "합산"
for _r in E:
    _r["energy_carrier"] = CARRIER_BY_ID.get(_r["effect_id"], _carrier(_r))


# ---- v12 기준선 출처 조사 (2026-10-27, Claude 원문 확인)
SOURCES += [
    dict(source_id="R22", citation="Reynolds, C. D., Hare, S. D., Slater, P. R., Simmons, M. J. H., Kendrick, E. (2022). Energy Technology 10, 2200545.",
         title="Rheology and Structure of Lithium-Ion Battery Electrode Slurries", doi="10.1002/ente.202200545", year=2022,
         source_type="논문", access="원문", url="",
         note="양극 NMC 96/PVDF 2/CB 2, NMP 고형분 60 wt%(Sec. 2.1 p.3, Table 1 p.4). 산업 슬러리는 50~60%(p.3), 결론에서 양극 60 wt%를 산업 기준으로 제시(p.12). "
              "겔화 시 코터 불안정(p.10), 탄성은 코팅 결함 유발(p.1)"),
    dict(source_id="R23", citation="Vogt, M., Koch, K., Turetskyy, A., Cerdas, F., Thiede, S., Herrmann, C. (2021). Procedia CIRP 98, 157-162.",
         title="Model-based energy analysis of a dry room HVAC system in battery cell production", doi="10.1016/j.procir.2021.01.023", year=2021,
         source_type="논문", access="원문", url="",
         note="'드라이룸 HVAC 운전은 생산 처리량과 무관(production throughput-independent)'(Sec. 1, p.158). 1개월 실측 60,497 kWh 중 재생 히터 25,880 kWh(Table 1, p.160). 연구 라인 규모"),
    dict(source_id="R24", citation="Jinasena, A., Burheim, O. S., Strømman, A. H. (2021). Batteries 7(1), 14.",
         title="A Flexible Model for Benchmarking the Energy Usage of Automotive Lithium-Ion Battery Cell Manufacturing", doi="10.3390/batteries7010014",
         year=2021, source_type="논문", access="원문", url="",
         note="드라이룸 에너지는 공정 시간·공장 설계 용량 기준 풍량에 비례(Sec. 2.1.5, 3.2), '2 GWh 이상에서는 용량 증가에 따른 원단위 변화가 매우 작음'(Sec. 3.3) - "
              "설계 단계에서 공장을 크게 지을 때의 비교라 같은 공장 증산(고정부하)과는 조건이 다름"),
    dict(source_id="R25", citation="Keyser, M., Long, D., Pesaran, A., Darcy, E., Shoesmith, M., McCarthy, B. (2015). NREL/PR-5400-66958 (228th ECS Meeting).",
         title="NREL/NASA Internal Short-Circuit Instigator in Lithium Ion Cells", doi="", year=2015, source_type="보고서", access="원문",
         url="https://www.nrel.gov/docs/fy17osti/66958.pdf",
         note="내부단락 사고 확률 1~10 ppm 추정(p.3). 인위 내부단락 유발 장치(ISC instigator)로 결함 셀을 만들어 시험 - 섀도 모드 결함 양성 표본 확보 방법"),
]

# ---- v12 (2026-10-27) 누락 고장모드 3건 - 팀 판단(등급 E), 출처 원문 확인 전이라 '미확인'
for _k, _kw in (("V12-01", dict(
        lever_id="DRY-HSC", failure_mode="고형분 상향 슬러리 겔화·점도 급상승·가용시간 단축",
        mechanism="고형분 증가로 입자 간 거리 감소, PVDF·도전재 망상 구조 형성 → 점도·항복응력 급상승, 보관 중 겔화",
        affected="품질", control_action="배합 2수준 점도·항복응력·가용시간(pot life) 측정, 분산 공정(혼련) 조건 고정",
        detection_method="회전 점도계·유변 측정, 코팅 두께 편차·핀홀·가장자리 크랙 검사",
        quality_gate="목표 고형분에서 점도·가용시간이 코팅 설비 허용 범위 안이고 코팅 결함률이 기준 배합과 동등",
        source_id="R22", locator="p.10 (gel-like rheology), p.1, p.12",
        excerpt="탄소 비중이 커져 유변이 겔처럼 되면 코터 불안정 / 탄성이 코팅 결함 유발 / 조성 한계 근처에서 유변이 급변")),
                  ("V12-02", dict(
        lever_id="DRY-RAD", failure_mode="NMP 증기 구역 표면 과열·점화원",
        mechanism="복사(NIR·레이저) 국부 고온으로 전극 표면·이물이 과열, NMP 증기 농도가 높은 구역에서 점화원이 됨",
        affected="안전;품질", control_action="NMP 농도 LFL 25% 인터록과 복사 출력 연동 차단, 표면 온도 상한 제어",
        detection_method="구역별 NMP 농도계, 적외선 표면 온도 감시, 인터록 작동 시험",
        quality_gate="최악 조건(최대 출력·최대 증발 구간)에서 표면 온도 상한 유지 + 인터록 차단 시험 통과",
        source_id="R18", locator="원문 위치 확인 필요", excerpt="(팀 판단 - 복사 건조 안전 관리)")),
                  ("V12-03", dict(
        lever_id="DRM-LOCAL", failure_mode="드라이룸 국소화 개조 전환기 이슬점 이탈",
        mechanism="기존 대공간 제습에서 미니환경으로 전환하는 공사·시운전 기간에 경계(인클로저·반송 포트) 기밀 미완성",
        affected="품질;안전", control_action="구역별 단계 전환, 전환 구역 생산 격리, 이슬점 연속 기록",
        detection_method="노출 구역 이슬점 연속 측정, 전환 전후 셀 수분·초기 용량 비교",
        quality_gate="전환 기간 전 구간에서 전극 노출 구역 이슬점 -40°C 이하 유지 기록 + 전환 로트 품질 동등",
        source_id="R8", locator="원문 위치 확인 필요", excerpt="(팀 판단 - 국소화 전환 관리)"))):
    fm(burden_metric="none", evidence_grade="E", verification="미확인", note="v12 추가 - 출처 원문 확인 필요(등급 E 팀 판단)", **_kw)
    F[-1]["fmea_id"] = f"FM-{_k}"
    if _k == "V12-01":     # Reynolds 2022 원문에서 겔화·코팅 불안정 문장 확인 (실험실 규모 → 등급 D)
        F[-1].update(evidence_grade="D", verification="원문 확인",
                     note="v12 추가. Reynolds 2022(R22) 원문 문장 확인 - 실험실 배합 연구라 고형분 65% 직접 시험값은 아님")


# ---- v12.1 조원 자료조사 반영 (2026-10-27, 조원 원문 대조 → Claude 정리). 효과값(EF)·등급은 바꾸지 않는다 → 결론 숫자 불변
BY3 = "조원 자료조사(2026-10-27)"
_SRC_PATCH_V121 = {
    "R8": dict(access="원문",
               note="조원 원문 확인(Fraunhofer 공개 PDF). Table 2 p.7: 드라이룸(DP -40°C) 상시 동력 전기 0.17 + 가스 0.95 kW/m², "
                    "DP -60°C 전기 0.39 + 가스 2.19 kW/m², 클린룸(ISO 8) 전기 0.112 + 가스 0.112 kW/m², 365일·3교대 상시. "
                    "드라이룸 투자 5,828.69 $/m², 미니환경 하우징 28,592.73 $/m³, 진공락(직경 600 mm) 43,922.14 $/대. "
                    "Sc1 2.43 · Sc2 4.18 · Sc4 6.16(셀 원가 +1.9%) · Sc5 13.29 $/kWh_cell(+8.6%, 70%가 미니환경 투자). "
                    "15 GWh 원통형 신설·독일 단가 기준 → C사 금액으로 쓰지 않고 '부분 국소화 우선'의 근거로만 사용. "
                    "면적 비례 상시 부하 = 고정부하 f 분류 근거(숫자 f는 팀 계수)"),
    "R6": dict(access="초록",
               note="조원 초록 확인: CO2 히트펌프 동적 회수기간 2.28년, COP 정의 미확인 → 경제성 '문헌 사례'로만, C사 계산에 쓰지 않음"),
}


def apply_v121_notes():
    """팀 레이어 병합 뒤에 실행 - 팀 비고는 지우지 않고 v12.1 조원 확인 내용을 덧붙인다."""
    for _r in SOURCES:
        pt = _SRC_PATCH_V121.get(_r["source_id"])
        if pt and "[v12.1 조원 자료]" not in (_r.get("note") or ""):
            _r["access"] = pt["access"] if _r.get("access") != "원문" else "원문"
            _r["note"] = ((_r.get("note") or "") + " [v12.1 조원 자료] " + pt["note"]).strip()
SOURCES += [
    dict(source_id="R26", citation="Sun, X., Luo, X., Zhang, Z., Meng, F., Yang, J. (2020). Journal of Cleaner Production 273, 123006. (Jinasena 2021 Table 4 재인용)",
         title="Life cycle assessment of lithium nickel cobalt manganese oxide (NCM) batteries for electric passenger vehicles",
         doi="10.1016/j.jclepro.2020.123006", year=2020, source_type="논문", access="2차", url="",
         note="30 GWh NCM622 파우치(204 Wh/셀) 양산 공장: 총 제조 에너지 28.4 Wh/Wh_cell 중 화성 3.0 → 10.56%(Jinasena 2021 Table 4, p.11). "
              "열 포함 총에너지 비중이라 C사 '전력 비중 15%'와 기준이 다름 → '화성 단독 10% 안팎 사례가 있어 10/5 분할과 모순되지 않는다'까지만 씀"),
    dict(source_id="R27", citation="Bryntesen, S. N., Kahrom, A., Lamb, J. J., Tolstorebrov, I., Burheim, O. S. (2023). Batteries 9(2), 96.",
         title="Experimental Analysis of Drying Kinetics and Quality Aspects of Convection-Dried Cathodes at Laboratory Scale",
         doi="10.3390/batteries9020096", year=2023, source_type="논문", access="원문", url="https://doi.org/10.3390/batteries9020096",
         note="p.2 Sec.1: 'solvent-to-powder content usually varies from 30 to 60% depending on the mixing method' → 고형분 대략 40~70% 범위(환산 방식에 따라 다름). "
              "기존 고형분 60%는 범위 안 대표값(C사 값 미공개). 출제 참고논문 R4(2021 리뷰)와 별개 논문"),
    dict(source_id="R28", citation="Lu, X., Lian, G. J., Ge, R., Parker, J., Sadan, M. K., Smith, R., Cumming, D. (2023). Energy Technology 11(10), 2300446.",
         title="Microstructure of Conductive Binder Domain for Electrical Conduction in Next-Generation Lithium-Ion Batteries",
         doi="10.1002/ente.202300446", year=2023, source_type="논문", access="원문", url="",
         note="p.2 Sec.2.1: 코팅용 슬러리 고형분 64~66% 권장(Ouyang 2020, RSC Adv. 10, 19360 인용 - 2차), 약한 가교 응집 구조로 항복응력 없이 분산 안정·건조 중 이동 억제. "
              "고형분↑ → 점도·저장/손실 탄성률 상승, p.6 Sec.2.4 '코팅 전 강한 겔 방지'. NMC622/CB/PVDF/NMP 계 → 목표 65%·경계 64.29%가 권장 범위 안"),
    dict(source_id="R29", citation="Zheng, H., Yang, S., Xue, W., Xiao, S., Shen, D., Dong, W., Zhang, X. (2026). Engineering Applications of Artificial Intelligence, 114180.",
         title="(화성 데이터 기반 조기 판정 관련 - 서지만 확인)", doi="10.1016/j.engappai.2026.114180", year=2026,
         source_type="논문", access="2차", url="",
         note="조원이 ORCID 등록부로 서지만 확인. 원문 미확보 → 수치 사용 안 함. 중장기 트랙(화성 데이터 조기 판정) 정성 근거 후보"),
]
# FM-V12-01(고형분 상향)을 조원 확인 원문으로 보강 - 행을 늘리지 않아 관문 수(41건) 유지
for _r in F:
    if _r.get("fmea_id") == "FM-V12-01":
        _r.update(
            failure_mode="고형분 상향 슬러리 겔화·점도 급상승·가용시간 단축, 슬롯다이 토출 한계·응집체 막힘",
            mechanism="고형분 증가로 입자 간 거리 감소, PVDF·도전재 망상 구조 형성 → 점도·항복응력 급상승·강한 겔. "
                      "점도가 높으면 기존 슬롯다이로 도포 불가(압출 필요), 다이 표면 불균일 젖음으로 응집체 퇴적 → 토출 막힘·줄무늬",
            control_action="배합 2수준 점도·항복응력·가용시간 측정, 분산 조건 고정, 목표 고형분은 권장 64~66% 안(65%)에서만, "
                           "슬롯다이 토출 압력·필터 차압 감시와 다이 세정 주기 설정",
            detection_method="회전 점도계·유변 측정, 슬롯다이 토출 압력·필터 차압 추이, 코팅 두께 편차·줄무늬·핀홀·가장자리 크랙 검사",
            quality_gate="목표 고형분에서 점도·가용시간이 슬롯다이 허용 범위 안, 토출 압력 안정·응집 결함 없음, 코팅 결함률이 기준 배합과 동등",
            excerpt="R22: 겔 유변 → 코터 불안정 / R28: 코팅 권장 64~66%, 강한 겔 방지 / R18 p.6: 고농도 슬러리는 기존 슬롯다이로 도포 불가 / "
                    "R19 p.6: 슬롯다이 응집체가 토출을 막아 코팅 결함",
            locator="R22 p.10·p.1·p.12 / R28 p.2 Sec.2.1·p.6 Sec.2.4 / R18 p.6 / R19 p.6 Sec.2.2",
            note="v12 추가 · v12.1 조원 자료(R28 Lu 2023, R18 Liu 2021 p.6, R19 Örüm Aydin 2023 p.6)로 보강. 등급 D 유지(65% 직접 시험값 아님)")


def write(name, rows, sheet):
    cols = S.columns(sheet)
    with open(ROOT / "data" / "kb" / f"{name}.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="raise")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def merge_team_layer():
    """data/kb_team/*.csv(팀원 입력, tools/import_team.py로 생성)를 합친다. 같은 ID는 팀 값으로 교체."""
    tdir = ROOT / "data" / "kb_team"
    for name, rows, idc in (("sources", SOURCES, "source_id"), ("effects", E, "effect_id"), ("fmea", F, "fmea_id")):
        f = tdir / f"{name}.csv"
        if not f.exists():
            continue
        team = list(csv.DictReader(open(f, encoding="utf-8-sig")))
        idx = {r[idc]: i for i, r in enumerate(rows)}
        for t in team:
            if t[idc] in idx:
                rows[idx[t[idc]]] = t
            else:
                rows.append(t)


if __name__ == "__main__":
    merge_team_layer()
    apply_v121_notes()
    write("sources", SOURCES, "sources")
    write("effects", E, "effects")
    write("fmea", F, "fmea")
    print(f"sources {len(SOURCES)} · effects {len(E)} · fmea {len(F)}")
