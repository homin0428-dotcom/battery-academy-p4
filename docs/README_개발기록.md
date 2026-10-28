# PFMEA 연계 공정 전환 검토 (Battery Process Change v10)

공정 개선 → PFMEA 관리조치 → 추가 시간·전력·공간 부담 → 목표 재판정 → 부족 성능 역산 → 조건부 설계 결론을
실제로 계산하는 소형 엔지니어링 의사결정 도구. Streamlit UI(3개 탭)와 독립 CLI가 같은 `core.py` 계산 엔진을 사용한다.

## 1. 목적과 적용 한계
- 기준 문서: `Battery_Process_Change_Proposal_v10.pdf` (v10을 구현 기준으로 사용).
- 가정 기반의 **조건부 계산 도구**이다. 대상 공장의 품질 충족, 수명, 불량률, 실제 절감 성능을 예측·보증하지 않는다.
- 화성 처리능력은 **화성 단독** 값이다. 건조·조립 등 병목 자료가 없어 전체 공장 생산능력 달성은 미확인이다.
- 요구 절감률·보완 사양은 "목표 도달에 필요한 값"이며 확보된 성능이 아니다.
- 구현하지 않은 것: ML/DL, 수명·불량 예측, RPN/AP/CEI 자동 계산, LLM/RAG, DB, 실시간 연계 등(범위 제외).
- 정규화 전력(기준 100)은 kWh·비용으로 환산하지 않는다.

## 2. v10 과제 조건
| 항목 | 값 |
|---|---|
| 목표 생산능력비 / 원단위 | 1.2 (10→12GWh) / 기존 대비 0.70 (30% 절감) |
| 기존 화성 / 에이징 | 20h / 14일 |
| 기준 전력 100 | 건조 35, 드라이룸 25, 화성·에이징 15(화성10·에이징5는 분석 가정), 기타 25 |
| 목표 총전력 (q=1.2) | 100×1.2×0.70 = 84 |
| 비교 조건 | 16h+0.25h(목표 사양), 16h+2h(비교 가정), 16h+2h·채널 1.08, P_add=0/2, 모든 f=0 |

## 3. 설치 (Windows PowerShell)
```powershell
py -3 -m venv .venv                      # 이미 유효한 .venv가 있으면 생략
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
Linux/macOS: `python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt` (이후 명령의 경로만 `.venv/bin/python`).
`requirements.lock.txt`는 이 작업에서 실제로 사용한 설치 버전 기록이다.

## 4. 실행
```powershell
# CLI (battery_v10 폴더에서)
.\.venv\Scripts\python.exe run.py --scenario representative --out outputs
.\.venv\Scripts\python.exe run.py --scenario custom --set channel_ratio=1.08 --set added_occupancy_source=\"input\" --set added_occupancy_h=2 --out outputs_custom
.\.venv\Scripts\python.exe run.py --scenario representative --out outputs --run-tests   # pytest 결과를 manifest에 기록

# UI
.\.venv\Scripts\python.exe -m streamlit run app.py

# 테스트
.\.venv\Scripts\python.exe -m pytest -q
```
`--set KEY=JSON` 의 키는 `configs/scenarios.json`의 `base_inputs` 항목이다. 프로젝트 상위 폴더에 `.venv`가 있으면 `..\.venv\Scripts\python.exe` 로 실행한다.

## 5. 시나리오
| 키 | 화면 표기 | 설명 |
|---|---|---|
| representative | v10 대표 | 16h+0.25h, 채널 1.00, 기본 f, r=[0.4,0.3,0.3,0,0], P_add=2 |
| all_proportional | 모든 부하 비례 | 대표와 같고 f 전부 0 |
| custom | 사용자 조건 | 대표에서 시작, UI 탭 2 또는 `--set`으로 변경 |

## 6. 건조 모드 A / B
- **모드 A**: v10 단순화 시나리오(기준 가열60/냉각25/팬15). b=0.52, COP_h=3.85(또는 3.0)는 분석 가정이며 R6의 COP 정의는 확인하지 않았다.
- **모드 B**: 정확히 3개 구간의 팬·가열·보조전력·히트펌프 가용 수요를 입력해 합산 후 히트펌프를 1회 계산(`Qh=min(Qset,수요,열원/(1-1/COP_h))`). 기본값은 **전부 미확인**이라 계산 보류이며 모드 A 값으로 채우지 않는다.
- 모드 B 경계: 기존 보조부하(`aux_base_kwe`)는 E_base·E_new 양쪽에, 구간별 추가 보조부하는 E_new에만 반영한다. 열원 한계 초과는 상한 처리 + 경고·제한 요인 표시, 단위는 `kWth/kWe` 고정.
- 공장 모델에는 `drying_r_source`(manual / mode_a / mode_b) **하나만** 반영된다. 둘 이상이면 입력 오류로 차단한다.

## 7. PFMEA 관리조치 반영
- `data/pfmea.csv`: 6개 위험 경로(F01, F02, D01, D02, R01, A01), 효과별 레코드(`action_id`).
- 각 효과는 `included_in_process` 또는 `additional` 중 하나에만 속하며 `(action_id, impact_parameter)` 중복은 오류.
- 추가 점유시간: `added_occupancy_source` = `pfmea`(PFMEA 효과 합계, 기본 F02 0.25h) 또는 `input`(직접 입력) 중 하나.
- 추가 전력: `p_add_mode` = `aggregate`(대표 가정 2pt) 또는 `itemized`(개별 효과 합계). 동시 입력은 차단. itemized에서 정량 미확인 항목이 있으면 합계를 확정하지 않고 계산 보류.
- 정량값이 없는 조치는 0이 아니라 "정량 부담 미확인"으로 남는다. 현재 계산에 직접 연결된 효과는 F02의 추가 점유 1건이며, 나머지는 미확인 또는 시나리오 입력 사용으로 표시된다.
- 품질 상태(미확인/검증 중/충족/미충족)는 수치 상태(충족/미달/계산 보류/입력 오류)와 독립이다. 상태 변경은 근거 메모가 필수이며 `미충족`은 적용 제외로 집계한다.

## 8. 입력 출처·품질 상태 정의
- `origin`: problem / literature / assumption / requirement / derived. 가정을 계산에 사용하면 결과에 가정 기반으로 표시한다.
- null=미확인(해당 계산만 보류), 0=확인된 0, 단위 불일치=계산 차단(예: P_add를 kWh로 입력).
- 비율은 내부 0~1, 화면 %는 표시용. 판정은 모두 반올림 이전 값. 요구 사양은 표시 시 올림(드라이룸 0.36231 → 36.3%).

## 9. 산출물 (`outputs/`)
| 파일 | 내용 |
|---|---|
| result_report.pdf | A4 4쪽 한국어 결과 보고서 |
| scenario_comparison.csv | 비교 조건 및 관리조치 전후 |
| requirements.csv | 계통별 역산 요구 절감률·보완 요구 |
| pfmea_summary.csv | PFMEA 전체 필드 + 계산 반영 상태 |
| evidence.csv | 근거 목록(`used_in_report`) |
| formation_boundary.png, energy_boundary.png | 300dpi 그래프 |
| run_manifest.json | 실행 일시·설정 해시·패키지 버전·입력 파일 해시·테스트 상태 |

CSV는 utf-8-sig. 한글 PDF는 `assets/fonts`의 NanumGothic Regular/Bold를 임베딩한다(라이선스: `assets/fonts/OFL.txt`, SIL OFL 1.1).
`requirements.csv`에는 계통 역산·보완 요구 외에 `건조 모드 B 경계/경고`(제한 요인·열원 한계·경고)와 `에이징 구역`(구역별 면적·전환 슬롯) 행이 조건부로 추가된다(`value`, `unit` 열).

## 10. 원문과 구현 명세의 충돌·정정 기록
1. **역산식 +1 항**: 이전 프롬프트의 역산식에는 `+1`이 빠져 있어 대표 검산값과 맞지 않았다. `r_j = 1 + (Σ_{i≠j}E_i + P_add − target)/B_j`를 사용하며 대표값(건조 0.4399014778, 드라이룸 0.3623076923, 기타 0.0589090909)이 회귀 테스트에서 확인된다.
2. **표기**: v10 본문의 "드라이룸 약 36.3%"는 0.36231의 올림 표시이다(반올림은 36.2%). 요구 사양은 올림 표시로 통일했다.
3. **PDF 원문 텍스트 추출**: v10 PDF는 텍스트 추출 시 한글이 깨져, 페이지를 이미지로 렌더링해 대조했다. 문헌 R1–R11의 제목·DOI는 v10 참고문헌 목록에서 옮겼으며 **논문 원문은 열람하지 않았다**.
4. 공식 대회 문제 4 출제서 파일은 작업공간에 없어 v10 PDF의 인용으로만 확인했다(미확인).
5. **R2**(Wood et al., 2019, *Formation Challenges of Lithium-Ion Battery Manufacturing*)는 v10 11쪽 참고문헌 목록에는 있으나 본문 어디에도 인용되지 않는다. 지시서 14.1("사용하지 않은 문헌은 장식용으로 넣지 않는다")에 따라 PDF 문헌 표에서는 의도적으로 제외한다. 다만 `evidence.csv`는 v10 목록 전체(R1~R11)를 추적하는 파일이므로 R2를 `used_in_report=N`으로 기록하고, PDF 4쪽에 제외 사실을 한 줄로 밝힌다.
6. 건조 모드 B의 "기준 보조 전기부하"(`aux_base_kwe`)는 기준 전력 비교를 위해 필수 입력으로 추가했다(원 명세에 명시되지 않은 구현 결정). 변경 전·후에 모두 남는 부하이므로 E_base와 E_new에 **같이** 더한다. 구간별 `aux_electric_kwe`는 변경안에서 추가되는 보조 부하로 E_new에만 더한다.
7. 모드 B 열원 한계(`Qsource/(1-1/COP_h)`)를 Qset 또는 Qdemand가 넘으면 지시서 식대로 Qh를 상한 처리하되, 결과의 `limit_by`·`source_limit_kwth`·`unmet_hp_kwth`·`warnings`로 제한 요인과 경고를 표시한다(UI 탭 2, `requirements.csv`, PDF 4쪽, manifest).
8. 모드 B 입력(`drying_b_global`, `drying_b_zones`)의 단위는 `kWth/kWe`이어야 하며 다르면 계산을 차단한다.
9. `drying_a_airflow_scope`(`system`/`zone`): 모드 A의 풍량 감소가 특정 구간 값(`zone`)인데 `drying_r_source=mode_a`로 건조 계통 전체에 적용되면 "구간 절감의 전체 중복 적용"으로 차단한다.
10. 에이징 구역별 계산(`aging_zones`, v10 10쪽 "구역별 슬롯과 공간 전환"): 구역 목록이 있으면 구역마다 슬롯비·freed_area·전환 슬롯을 계산하고, 없으면 기존 단일 구역 계산을 쓴다. 구역 간 상쇄는 하지 않으며(부족 구역은 "추가 공간 필요"), 14일은 구역과 무관하게 유지한다. 한 구역이라도 입력이 미확인이면 합계는 보류한다.

## 11. 미확인 입력과 현장 검증 사항
- 미확인: 실제 채널 수, 대기공간 입력(처리량·대기일·셀당 면적·슬롯 밀도·전환 비율), 건조 모드 B 전체 입력, 화성 회생 독립 수지, 전체 공장 병목(건조·조립).
- 가정: f·r·P_add, 화성10/에이징5 분할, b=0.52, COP_h, 채널비·가동률·수율 동일 유지.
- 현장 검증 필요: 16h 화성의 품질 동등성(프로토콜별 초기효율·용량·가스·저항·장기 수명), 새 프로토콜 구간의 진단 적합성, 건조 변경 시 잔류 NMP·접착·크랙, 드라이룸 이슬점 −40°C 유지, 랙·버퍼 전환의 최소 버퍼 시간·동선·방재·온도 균일성·추적성.
- 폰트: NanumGothic Regular/Bold(Copyright © 2011 NHN Corporation, Font designed by Sandoll Communications Inc.)를 **SIL Open Font License 1.1** 조건으로 사용·재배포한다. 전문은 `assets/fonts/OFL.txt`에 보존했고 PDF 4쪽과 manifest(`font_note`)에도 명시한다. 단, 폰트 파일 자체의 메타데이터(name table)에는 저작권 문구만 있고 라이선스 문구는 없다. OFL 적용은 이 프로젝트 요청자의 지정에 따른 것이므로 폰트를 내려받은 배포처의 라이선스 고지와 일치하는지 한 번 확인할 것.

## 12. 구조
```
app.py(UI) run.py(CLI) core.py(계산) reporting.py(PDF/CSV/그래프/manifest)
evidence_engine.py(근거 기반 자동 판정) evidence_report.py(근거 판정 보고서) kb_schema.py(데이터셋 정의) kb_import.py(엑셀 가져오기)
configs/scenarios.json  data/pfmea.csv  data/evidence.csv  data/kb/(근거 FMEA 데이터셋)  assets/fonts  tests/  outputs/  tools/
```

## 13. 근거 FMEA 데이터셋과 자동 판정 (2026-10-23 추가)

v10 경로(위 1~11절)는 사람이 정한 절감률 r로 계산한다. 근거 경로는 **r을 쓰지 않고**, 논문·자료의 수치를 모은
데이터셋(`data/kb/`)만으로 계통별 절감률 범위를 추론해 같은 공장 모델(core.plant_energy)로 목표를 판정한다.
두 결과를 나란히 보여 주어 v10 가정이 근거로 뒷받침되는지 검증한다.

### 데이터셋 (data/kb/*.csv, 정의는 kb_schema.py)
| 파일 | 내용 |
|---|---|
| sources.csv | 근거 자료 (서지·DOI·확인범위: 원문/초록/2차) |
| levers.csv | 공정 변경 레버 (적용 계통, 중복방지그룹, 패키지 포함 레버, v10 채택, 적용시기 3년내/장기) |
| effects.csv | 정량효과 - 레버 × 지표 × 근거 1건 = 1행. 값·단위·**측정범위**·적용 조건·근거 위치·등급·확인상태 |
| fmea.csv | 근거 FMEA - 고장모드·메커니즘·관리조치·검출 방법·관리 부담(시간·전력·채널)·품질 관문 |

### 판정 규칙
1. **측정범위 환산**: 계통전체 → 그대로 / 공장전체 → 계통 비중으로 나눔(원문 비중 → KB 비중 근거 → 과제 비중 순, 100% 초과 시 제외) /
   계통일부 → 부분 비중을 곱함(없으면 참고 전용) / 복합계통·장비단위 → 참고 전용.
2. **적용 조건**: 대상 NCM·파우치·양산. 양극계 불일치·확인상태 '미확인'은 제외, 규모·셀형태 차이는 '조건부'.
3. **결합**: 같은 중복방지그룹은 곱하지 않고 가장 큰 단일 레버 값, 다른 그룹은 독립 가정으로 1-Π(1-s). 패키지 레버는 포함 레버를 대체.
4. **3개 경우**: 보수(근거 하한+부담 상한) / 대표(중앙값) / 낙관(근거 상한+부담 하한) → 근거상 충족 / 조건부 충족 / 근거 상한에서만 충족 / 근거상 미달.
5. **보조 기능**: 단독 보완 요구값 vs 근거 상한, 근거 있는 3년 내 레버 1~2개 추가 조합의 결정적 열거(최적화·확률 아님), v10 가정 검증, 파라미터(COP 등) 점검.
6. 점수·확률(RPN/AP/CEI)은 만들지 않는다. 근거 등급(A~E)·확인상태·적용 조건은 범주로만 보고한다.

### 팀원 자료 추가 절차
```
python tools/make_kb_template.py 근거FMEA_입력템플릿.xlsx      # 최신 템플릿 (이미 폴더에 있음)
python kb_import.py 채운파일.xlsx                              # 검증만 - 오류는 kb_import_report.csv
python kb_import.py 채운파일.xlsx --merge                      # 통과 행을 data/kb에 병합 (같은 ID는 교체)
python run.py --out outputs                                    # 판정·보고서 재생성
```
CLI에서 레버를 바꾸려면 `--scenario custom --set kb_selected_levers='["FOR-FAST","DRM-LOCAL","DRY-RAD"]'`.

### 의사결정 보조 (2026-10-23 외부 평가 반영)
평가 지적: "최종 답은 프로그램이 아니라 C사의 개선 조합과 적용 순서여야 한다." → 근거 판정 보고서 1~2쪽이 답을 먼저 제시한다.
- **추천 조합**: v10 채택 레버 + 근거 있는 3년 내 레버 1~2개 추가 조합 중 최선 (결정적 열거).
- **증산 +20% 성립**: 화성 처리능력 + 에이징 보관능력(14일 유지 시 슬롯 증가율, 슬롯 고정 시 허용 평균 점유일). 에너지 판정과 별개.
- **에너지 종류**: 목표는 전력 원단위. 근거의 `energy_carrier`(전력/열/합산/1차에너지)를 보고, 열·합산은
  `kb_electric_heating`(계통 가열 전기식 여부, 기본 전기식 - v10 가정)일 때만 조건부 인정, 1차에너지는 참고 전용.
- **추천이 바뀌는 조건**: 근거 없는 레버가 넘어야 할 기준값, 추천 조합 유지 하한·여유, 미정량 관리 부담 허용치,
  가열 방식 가정이 바뀔 때의 판정, 화성 추가 점유 허용치.
- **개선안 비교표**: 원단위(보수/대표/낙관), 연 절감 전력량·금액(KB 전력 원단위 × `baseline_capacity_gwh` × `electricity_price_krw_per_kwh`),
  허용 투자비(`payback_years` 단순 회수 역산 - 견적 아님), 증산 판정, FMEA 품질 위험 수, 최대 변경 유형, 근거 보유 레버 수.
- **3년 적용 순서**: 레버 `change_type`(운영변경→1년차, 설비개조→2년차, 설비교체→3년차, 공정전환·장기→중장기), 레버별 근거FMEA 품질 관문을
  다음 단계 진입 조건으로 사용. 1년차에 근거 없는 레버의 파일럿 계측과 미정량 관리 부담 정량화를 배치.
- 단가 기본값 100원/kWh는 v10 예시값이다. 실제 산업용(을) 계약 단가로 바꾸면 금액·허용 투자비가 비례해 바뀐다.

### 산출물 추가
`evidence_report.pdf`(근거 판정 보고서), `evidence_systems.png`, `evidence_cases.png`, `kb_cases.csv`, `kb_lever_judgement.csv`,
`kb_effect_trace.csv`(수치→근거 추적), `kb_combos.csv`, `kb_options.csv`(비교표), `kb_thresholds.csv`(전환 조건), `kb_roadmap.csv`(3년 순서). manifest의 `evidence_dataset`에 데이터셋 파일 해시와 판정 요약을 기록.

### 2026-10-23 초기 데이터셋의 한계 (팀 확인 요청)
- R6(Guo 2026)·R7(Chen 2024)·R8(Lechner 2025)·R17(Zeferino 2025) 원문 미확보 - R8 값은 v10 인용 '2차 인용'.
- R1(Degen 2023) Table 1은 텍스트 추출 기반이라 값-열 대응을 원문 PDF로 재확인 필요.
- v10 채택 레버 중 DRY-ZONE·DRY-AIR·DRY-HP·DRM-LEAK·FOR-REGEN·FOR-DATA·AGE-RACK은 계산 가능한 근거 없음.
- 에이징 보관 공간 확보(`slot_gain_ratio`) 근거 없음 → 모든 안이 '증산 미완결'. 대상 공장 공간 검토 결과 필요.
- 계통 가열 방식(전기/가스) 미확인 - 드라이룸이 가스 재생이면 추천 조합이 미달로 바뀜.
- 관리 부담 FM-005(진단 점유)·FM-011(히트펌프 보조열)·FM-013(미니환경 경계 관리)은 미정량.


## 14. A/B/C 후보 비교 (2026-10-26, candidates.py)
- 같은 기준선(12 GWh 무개선 ΣB)·같은 근거·같은 단가·같은 열원으로 A(운영·기존 설비), B1/B2(고형분 상향 + 선택 개조), C(공간 제약 대안)를 계산.
- 판정은 5축 × 4상태(검증 완료 / 가정하 수치 충족 / 미확인 / 미달). **미확인은 통과가 아니다.**
- 현장 확인값 입력(configs/scenarios.json 또는 앱 탭 2 "A/B/C 후보 비교 조건"):
  `solids_old`, `kb_candidates[].solids`, `drying_solvent_load_share`(φ), `drying_max_speed_ratio_verified`, `aging_slot_gain_approved`, `kb_extra_occupancy_h`.
- 출력: evidence_report.pdf 1~3쪽(후보 비교·실패 경계·검증 우선순위), kb_candidates.csv, kb_boundaries.csv, kb_verification_priority.csv,
  evidence_candidates.png. `python run.py --run-tests`는 test_log.txt와 종료코드를 run_manifest.json에 함께 남긴다.

## 15. v12 분석 모듈 (2026-10-27)
| 파일 | 내용 |
|---|---|
| baseline.py | 워터폴(희석 vs 개조), 기준선 민감도(토네이도), 금액 범위, 기준선 카드 |
| necessity.py | 레버 하나씩 제거 비교, B2 요구 성능 역산, 건조 구조 가정 M1/M2/M3 |
| joint.py | 문헌 효과 α × 관리 전력 P 성립 영역, 스트레스 시나리오 5개 |
| capacity.py | 공장 처리능력 = min(건조·화성·에이징), 필요 최소값, 수율 시나리오, 연차별 q_t |
| upside.py | 판정 미반영 추가 여유(섀도 모드 에이징, what-if) |
| results_export.py | outputs/results.json(보고서·PPT 숫자의 유일한 원본) + 숫자 일치 검사 |

- 현장 검증 기록은 `kb_verifications`에 후보별로 입력: `{"candidate_id": "B1", "metric": "drying_speed_ratio", "value": 1.25, "conditions": {"solids": 0.65, "heat_dry": "전기", "drying_profile": "기준"}}`.
- `python run.py --run-tests` → 테스트·결과·results.json·숫자 일치 검사를 한 번에. 둘 중 하나라도 실패하면 종료코드 1.
