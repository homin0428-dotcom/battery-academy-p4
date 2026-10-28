# battery_v10 감사 보고서 (수정 없음)

`pytest`를 직접 실행해 46 passed / 0 failed를 확인했습니다. 모드 B 시험 스크립트는 scratchpad(`C:\Users\skygu\AppData\Local\Temp\claude\C--cursor-work\ede49cb5-de54-49fd-a38a-96e84fad711a\scratchpad\modeb_audit.py`)에만 두었고 프로젝트 파일은 건드리지 않았습니다.

## 1. 모드 B(8.2): 임의 3구간 입력으로 실제 계산

**입력**

| 구간 | 기존 팬 kWe | 변경 팬 | 기존 가열 kWth | 변경 가열 kWth | 보조 kWe | HP 사용 가능 kWth | 공급온도 적합 |
|---|---|---|---|---|---|---|---|
| 예열 | 12 | 풍량비 0.9, 상사법칙 적용 | 80 | 70 | 1.5 | 50 | 예 |
| 주건조 | 20 | 풍량비 0.8, 상사법칙 적용 | 150 | 130 | 2.0 | 90 | 예 |
| 후건조 | 8 | 직접 입력 7 | 60 | 55 | 0.5 | 40 | **아니오** |

공통 입력은 Qset 200, Qsource 100, COP_h 3.5, COP_c 3.0, 히터효율 1.0, 적합 냉각 30, 전체 냉각 45, 기존 보조부하 0입니다.

**결과.** 코드 출력과 제가 손으로 계산한 값이 모두 일치했습니다.

| 항목 | 값 | 비고 |
|---|---|---|
| HP 사용 가능 수요 | 140 | 후건조는 공급온도 부적합이라 40이 제외됨 |
| Qh | 140.0 | 열원 한계 100/(1−1/3.5)=140.0 (제한 요인: 열원) |
| W | 40.0 | |
| Qc | 100.0 | |
| Qcool_used | 30.0 | 적합 냉각수요로 제한됨 |
| 잔여 가열 / 잔여 냉각 | 115.0 / 15.0 | |
| 새 팬 합계 | 25.988 | 8.748 + 10.24 + 7 |
| E_new | 189.988 | |
| E_base | 345.0 | |
| 절감률 | **44.931%** | |

**공장 모델 연결.** 건조 절감률 출처를 `mode_b`로 두면 `r_effective[0]=0.4493`이 됩니다. 그 결과 E_total=83.618, 원단위 절감 30.318%, 격차 −0.382pt로 목표를 충족합니다. 이때 모드 A 값 42.20%는 적용되지 않았습니다.

**검증 동작**

| 시험 | 결과 |
|---|---|
| 2구간만 입력 | InputError: 정확히 3개 필요 |
| 필수 입력 1개 누락 | 계산 보류, 누락 항목 명시 |
| 기본 빈 3행 | 계산 보류, 누락 29건. 모드 A 값으로 채우지 않음 |
| 냉각수요 미확인(None) | 계산 보류 |
| 냉각수요 확인된 0 | 정상 계산, `Qcool_used`=0 |
| 열원 미확인 | 계산 보류. 열원을 무한대로 가정하지 않음 |
| COP_h=1.0 | InputError |
| 음수 열량 | InputError |
| 적합 냉각 60 > 전체 냉각 45 | InputError |
| `mode_b` 선택 + 입력 미확인 | 공장 전력 계산 보류. 화성 계산은 계속 수행되고 모드 A로 대체되지 않음 |

**시험 중 발견한 결함 3건**

1. **기준·변경 경계가 비대칭입니다.** `aux_base_kwe`는 E_base에만 더해지고 E_new에는 들어가지 않습니다(`core.py:331`, 330). 기존 보조부하를 0에서 5로 바꾸면 절감률이 44.93%에서 45.72%로 올라갔습니다. 반대로 구간별 `aux_electric_kwe`는 E_new에만 들어갑니다. 지시서 493행의 "같은 운전 경계 비교"와 어긋납니다.
2. **단위 혼용이 모드 B에서는 차단되지 않습니다.** `check_units`는 `EXPECTED_UNITS`의 키만 검사합니다(`core.py:32-40, 462-466`). `drying_b_global`의 단위를 "MW"로 바꿔도 계산이 진행됐습니다.
3. **열원 초과는 오류가 아니라 조용히 상한 처리됩니다.** Qset 200이 열원 한계 140을 넘어도 140으로 잘리고 경고가 없습니다(`core.py:323-324`). 지시서 공식(min)과는 일치하지만, 지시서 486행의 "열원 초과 금지"를 검증 규칙으로 보면 PARTIAL입니다.

## 2. Completion Gate(20)

| 항목 | 판정 | 근거 파일:줄 | 테스트 |
|---|---|---|---|
| 화성 계산 검산 | PASS | `core.py:125-172` | `test_formation_reference_values` (`test_core.py:37`) |
| 에이징 슬롯 검산 | PASS | `core.py:176-224` | `test_aging_slots_reference` (68) |
| 건조 A 검산 | PASS | `core.py:237-258` | `test_drying_mode_a_reference` (91) |
| 건조 B 제약 계산 검산 | PARTIAL | `core.py:268-339` | `test_mode_b_calculation` (124), `_source_limit` (151), `_supply_temperature` (157), `_errors` (162). 위 결함 3건이 있고, 시험 입력은 모두 가상 값 |
| 공장 전력 검산 | PASS | `core.py:368-398` | `test_plant_reference_values` (176) |
| 역산 검산 | PASS | `core.py:401-429` (+1 항 405) | `test_reverse_requirements_reference` (194), `_roundtrip_hits_target` (201) |
| 반올림 전 판정 | PASS | `core.py:85` (`_ge`), 판정 157, 394 | `test_formation_status_and_required_channel` (47). 표시용 반올림은 `fmt_*`에만 있음 |
| 미확인과 0의 구분 | PASS | `core.py:131-132`, 272-283, 370 | `test_null_vs_zero` (246), `test_mode_b_zero_cooling_is_confirmed_zero` (146) |
| PFMEA 6개 위험 경로 | PASS | `data/pfmea.csv` (F01, F02, D01, D02, R01, A01) | `test_pfmea_six_risks_and_accounting` (302) |
| 관리조치 영향 연결 | PASS | `core.py:484-551, 570-591, 743-768` | `test_comparison_and_before_after` (375), `test_pfmea_effect_not_counted_twice` (360) |
| action_id 중복 방지 | PASS | `core.py:489-492` | `test_duplicate_action_id_rejected` (331) |
| 관리 전력 집계 모드 분리 | PASS | `core.py:508-518` | `test_aggregate_and_itemized_not_mixed` (338), `test_itemized_mode` (349) |
| 품질 상태 분리 | PASS | `core.py:499-506, 554-567` | `test_quality_unknown_vs_numeric` (312), `test_quality_override_requires_note_and_unmet_excludes` (318) |
| 미확인 관리 부담 표시 | PASS | `core.py:526-527` (미확인 8건) | `test_pfmea_six_risks_and_accounting` (308) |
| Streamlit 3개 탭 | PASS (AppTest 기준) | `app.py:33` | `test_app_runs_with_exactly_three_tabs` |
| 독립 CLI | PASS | `run.py:39-70` | `test_cli_core_csv_pdf_consistent` (405), `test_cli_custom_set_and_bad_set` (442) |
| 동일 계산 엔진 | PASS | `app.py:30` (`core.run_scenario`), `run.py:52` | `test_app_has_no_formula_of_its_own`, `test_app_uses_core_result_values` |
| 2개 PNG | PASS | `reporting.py:73, 94` | 위 통합 테스트(405). 300dpi를 확인했고 제가 읽어 본 PNG 메타데이터도 299.9994였음 |
| CSV | PASS | `reporting.py:371` | 같은 통합 테스트. 4종 모두 utf-8-sig, 행 수 10/11/9/11 |
| manifest | PARTIAL | `reporting.py:371` | 같은 통합 테스트. 아래 3-1 참조 |
| README | PARTIAL | `README.md` (12개 절) | 테스트 없음. 폰트 라이선스 전문이 없음 |
| requirements lock | PASS | `requirements.lock.txt` | 설치된 `pip freeze`와 차이 없음을 확인 |
| A4 4쪽 | PASS | `reporting.py:162` | 통합 테스트. 제가 읽은 PDF도 4쪽, 595×842pt |
| 한국어 폰트 | PARTIAL | `reporting.py:156-170` | NanumGothic Regular/Bold 임베딩을 확인했음. 라이선스 파일이 없음 |
| KPI | PASS | `core.py:771-795` | `test_app_uses_core_result_values` |
| 시나리오 비교 | PASS | `core.py:595-617` | `test_comparison_and_before_after` (375) |
| PFMEA 요약 | PASS | `core.py:895-914` | `test_cli_core_csv_pdf_consistent` |
| 근거 및 미확인 사항 | PASS | `data/evidence.csv`, `reporting.py` | 통합 테스트(`evidence.csv` 생성 확인). 내용의 정확성은 아래 3-2 참조 |
| 표 넘침 검사 | PARTIAL | `reporting.py:198` (`repeatRows=1, splitByRow=1`) | 자동 테스트는 4쪽 여부만 확인. 넘침은 PROGRESS의 육안 확인 기록뿐 |
| 그래프·계산 일치 | PARTIAL | `core.py:829-860` | `test_boundary_data_and_grid_limit` (383)은 그래프 데이터 점만 검증. PNG 픽셀과의 일치는 검증하지 않음 |

## 3. 15.7 오류 처리

| 항목 | 판정 | 테스트 |
|---|---|---|
| B_j=0 | PASS | `test_reverse_over_one_not_clipped_and_zero_B` (210) |
| 요구 절감률 >1 (클리핑 안 함) | PASS | 같은 테스트 |
| 음수 점유시간 | PASS | `test_input_errors` (222) |
| 전력 비중합 오류 | PASS | `test_input_errors` |
| COP_h<=1 | PASS | `test_drying_mode_a_validation` (101), `test_mode_b_errors` (162) |
| 음수 열량 | PASS | `test_mode_b_errors` |
| 단위 불일치 | PARTIAL | `test_unit_mismatch_blocks_calculation` (239). 모드 B 입력은 검사 대상이 아님(결함 2) |
| 열원 초과 | PARTIAL | `test_mode_b_source_limit_never_exceeded` (151). 오류가 아니라 상한 처리를 검증함 |
| 적합 냉각수요 초과 | PASS | `test_mode_b_errors` |
| null과 0의 차이 | PASS | `test_null_vs_zero` (246) |
| 품질 미확인 / 미충족 | PASS | `test_quality_unknown_vs_numeric` (312), `test_quality_override_requires_note_and_unmet_excludes` (318) |
| 중복 action_id | PASS | `test_duplicate_action_id_rejected` (331) |
| aggregate와 itemized 중복 | PASS | `test_aggregate_and_itemized_not_mixed` (338) |
| 구간별 절감의 전체 중복 적용 | PARTIAL | `test_mode_a_b_not_double_applied` (267). 검사 인자 `zone_savings_applied_globally`는 `run_scenario`가 한 번도 True로 넘기지 않아(`core.py:662`), 실제 실행 경로에서는 발동하지 않는 가드임 |
| 모드 A/B 중복 | PASS (구조적) | 같은 테스트. 출처가 enum 하나라 동시 선택이 불가능하고, 검증 함수는 단위 테스트로만 확인됨 |
| 화성 회생 중복 | PASS | `test_regen_not_double_counted` (280), `test_regen_independent_in_run` (293) |

## 4. 지시서 대비 단순화·생략·불일치

1. **모드 B 경계 비대칭**: 기존 보조부하(`aux_base_kwe`)가 E_new에 반영되지 않습니다. 위 결함 1입니다.
2. **모드 B 단위 검사 누락**: 위 결함 2입니다.
3. **열원 초과**는 오류나 경고 없이 상한 처리됩니다. 위 결함 3입니다.
4. **구간별 절감 중복 가드**가 실행 경로에 연결되어 있지 않습니다(15.7 표 참조).
5. **폰트 라이선스 정보 미보존**: 지시서 14.2는 라이선스 정보 보존을 요구합니다. `assets/fonts/`에는 TTF 두 개뿐이고 라이선스 파일이 없습니다. README 96행과 `reporting.py:358`에 "확인 필요"라는 메모만 있습니다.
6. **에이징 구역별 계산 없음**: 지시서 7.2의 "구역별 데이터가 있으면 각각 계산"은 구현되지 않았습니다. 단일 구역 계산뿐입니다. 최소 버퍼·동선·방재 등 검증 항목은 안내 문구로만 존재합니다(`core.py:222-223`).
7. **모드 B 정상 계산의 근거가 가상 입력뿐입니다.** 앱 기본 데이터는 전부 미확인이고, `pytest`와 이번 감사 모두 가상 값으로만 확인했습니다. 지시서의 "임의 수치 금지"에는 부합하지만, 실데이터 검증은 0건입니다.
8. **PDF에 `Helvetica` Type1 참조가 하나 남아 있습니다.** 한글 폰트는 모두 임베딩됐으므로 영향은 미미합니다.
9. **UI와 PDF·CSV의 수치 일치 테스트가 약합니다.** 15.8은 UI도 같은 Core Result를 쓰라고 합니다. UI 쪽 테스트는 표시 문자열(28.65%, 1.231배 등) 포함 여부만 봅니다.
10. **`app.py`가 `quality_overrides`를 받는 방식**은 세션 상태 기반입니다. 기능상 문제는 없지만, 브라우저에서 직접 조작한 검증은 PROGRESS에도 "미수행"으로 적혀 있습니다.

### 3-1. manifest 불일치

PROGRESS.md는 Phase 7에서 "manifest에 test_status=passed 기록"이라고 적었습니다. 그러나 현재 `outputs/run_manifest.json`은 `test_status: {"status": "not_run"}`이고 생성 시각은 01:06:47입니다. 후속 수정 이후 `--run-tests` 없이 다시 생성된 것으로 보입니다. 정직하게 기록되어 있어 규칙 위반은 아니지만, PROGRESS의 완료 서술과는 맞지 않습니다.

### 3-2. 제가 확인하지 못한 것

- PDF를 이미지로 렌더링해 보지 않았습니다. 육안 검수는 PROGRESS의 기록만 있고, 제가 한 확인은 쪽수·폰트·텍스트 수준입니다.
- `evidence.csv`의 R번호·DOI·제목이 v10 PDF 원문과 일치하는지는 대조하지 않았습니다. 통합 테스트는 DOI 하나(`10.1038/s41560-023-01355-z`)가 PDF 텍스트에 있는지만 봅니다.
- 실제 Streamlit 서버 기동과 브라우저 조작은 확인하지 않았습니다(AppTest만 통과 확인).

## 5. 종합

- 계산 코어, 대표 검산값, PFMEA 회계, 산출물 생성은 지시서와 일치합니다.
- 모드 B는 구조와 보류 규칙은 맞습니다. 다만 경계 비대칭, 단위 검사 누락, 열원 초과 무경고 상한 처리 때문에 PARTIAL로 판정합니다.
- 폰트 라이선스 정보 보존과 에이징 구역별 계산은 지시서 대비 미충족입니다.
---

# 감사 후속 수정 및 재검증 (2026-10-21)

위 감사 보고서(수정 없음)는 원문 그대로 보존했습니다. 아래는 이후 수정 내용과 재검증 결과입니다. 기존 대표값(28.65%, 1.231배 등)과 기존 테스트 기대값은 바꾸지 않았습니다.

## A. 수정 내용

| # | 항목 | 수정 내용 | 주요 위치 | 테스트 |
|---|---|---|---|---|
| 1 | 모드 B 경계 대칭 | `aux_base_kwe`를 E_base와 E_new에 동일하게 반영. 구간별 `aux_electric_kwe`는 변경안에서 추가되는 부하라 E_new에만 반영 | `core.py` 모드 B 계산부 | `test_mode_b_aux_base_in_both_base_and_new` |
| 2 | 모드 B 단위 검사 | `drying_b_global`·`drying_b_zones`가 `kWth/kWe`가 아니면 InputError, `run_scenario`는 계산 차단 | `core.py` `EXPECTED_UNITS` | `test_mode_b_unit_mismatch_raises` |
| 3 | 열원 한계 경고 | 상한 처리는 유지. 결과에 `limit_by`, `source_limit_kwth`, `unmet_hp_kwth`, `exceeded`, `warnings` 추가. UI·CSV·PDF 4쪽·manifest에 표시 | `core.py`, `app.py`, `reporting.py` | `test_mode_b_source_limit_warning_and_limit_factor`, `test_mode_b_source_limit_reaches_run_csv_pdf_manifest` |
| 4 | 중복 가드 연결 | 입력 `drying_a_airflow_scope`(`system`/`zone`) 추가. `zone`인데 모드 A를 건조 전체에 쓰면 `run_scenario`가 차단 | `core.py` `run_scenario`, `configs/scenarios.json` | `test_zone_savings_guard_wired_in_run` |
| 5 | 에이징 구역별 계산 | `aging_zones`가 있으면 구역별 슬롯비·freed_area·전환 슬롯 계산, 없으면 기존 단일 구역 계산. 구역 간 상쇄 없음, 한 구역이라도 미확인이면 합계 보류 | `core.py` `_aging_zones`, `app.py`, CSV, PDF | `test_aging_single_zone_unchanged_without_zone_data`, `test_aging_zones_computed_per_zone_without_netting`, `test_aging_zones_missing_input_holds_only_totals`, `test_aging_zones_validation`, `test_aging_zones_reach_run_csv_pdf` |
| 6 | 폰트 라이선스 | `assets/fonts/OFL.txt`(OFL 1.1 전문) 추가. README·PDF 4쪽·manifest에 명시 | `OFL.txt`, `reporting.py`, `README.md` | `test_font_license_preserved` |
| 7 | R2 | v10 11쪽 참고문헌 목록에만 있고 본문 미인용. PDF 문헌 표 제외는 의도된 결과(지시서 14.1)였으나 `evidence.csv` 누락은 의도하지 않은 것이어서 `used_in_report=N`으로 추가, PDF에 제외 사실 한 줄 표기 | `data/evidence.csv`, README 10-5 | `test_r2_recorded_but_not_listed_as_used` |
| 추가 | PDF 4쪽 유지 | 새 내용으로 5쪽이 되어 4쪽 구성을 압축. 최악 조건(모드 B 경고 + 구역 8개)도 테스트 | `reporting.py` | `test_pdf_stays_four_pages_in_worst_case` |

## B. 감사 지적 항목별 처리 상태

| 감사 지적 | 상태 |
|---|---|
| 결함 1 (경계 비대칭) | 수정 |
| 결함 2 (단위 검사 누락) | 수정 |
| 결함 3 (열원 초과 무경고) | 경고·제한 요인 표시 추가, 상한 처리는 유지 |
| 4-4 (구간 절감 가드 미연결) | 수정 |
| 4-5 (폰트 라이선스) | OFL.txt 추가. 아래 주의 참조 |
| 4-6 (에이징 구역별 계산) | 수정 |
| 3-1 (manifest `not_run`) | `--run-tests`로 재생성해 `passed` 기록 |
| 4-7, 4-8, 4-9, 4-10, 3-2 | 수정하지 않음 |

## C. 테스트 결과

| 검사 | 결과 |
|---|---|
| pytest 전체 | 59 passed / 0 failed (기존 46 + 신규 13, `tests/test_audit_fixes.py`) |
| 기존 테스트 기대값 | 변경 없음 |
| `run.py --scenario representative --out outputs --run-tests` | 종료 코드 0, 통과 59 / 실패 0 |
| `outputs/run_manifest.json` | `test_status = passed` (59/0), 생성 2026-10-21T01:20:52, 경고 0건 |
| 대표 KPI | 화성 1.231배, 원단위 절감 28.65%, 격차 +1.62pt, E=85.62 (변경 없음) |
| PDF | A4 4쪽(pypdf). 1~4쪽 모두 수정 후 렌더링해 육안 확인(넘침·글자 깨짐 없음). 2·3쪽은 이후 추가 확인(그림 1·2, PFMEA 표 6행, 요약 수치 기존과 동일) |
| CSV 행 수 | scenario_comparison 10, requirements 12, pfmea_summary 9, evidence 12 |
| `requirements.lock.txt` | `pip freeze`와 일치 |

## D. 남은 한계와 주의

- 브라우저에서 Streamlit UI를 직접 조작하지 않았습니다. 구역 입력 표·경고 표시는 AppTest 통과까지만 확인했습니다.
- OFL 표기는 요청에 따른 것입니다. 폰트 파일 메타데이터에는 "Copyright © 2011 NHN Corporation. All rights reserved"만 있고 OFL 문구가 없으므로, 내려받은 배포처의 고지와 일치하는지 확인이 필요합니다.
- 논문 DOI·제목을 원문과 대조하지 않았습니다. R2 항목은 v10 11쪽 이미지에서 옮겼습니다.
- 에이징 구역 합계 `freed_area_m2`는 부호를 상쇄한 단순 합입니다. 부족 구역은 합계 상태("일부 구역 추가 공간 필요")로 드러냅니다.
- `aux_base_kwe` 해석(기존 부하는 양쪽, 구간 보조부하는 변경안에만)은 설계 판단이며 README에 기록했습니다.
- `drying_a_airflow_scope`는 사용자가 선언하는 입력이라 `zone` + 모드 A 조합에서만 가드가 발동합니다.
- 모드 B 정상 계산은 여전히 가상 입력으로만 검증했습니다(실데이터 0건).
- UI와 PDF·CSV 수치 일치 테스트 보강은 이번 범위에 없었습니다.

# 외부 검토 반영(10/21)

외부 검토에서 재현된 결함을 `core.py`·`app.py` 교체본에 반영하고, 회귀 테스트 `tests/test_review_fixes.py`(26개)를 추가했습니다. 이어서 `reporting.py` 표시 누락을 보완했고, 이 부분은 `tests/test_review_reporting.py`(4개)로 고정했습니다.

## E. 기존 테스트 영향 판단

교체본으로 `pytest` 전체를 실행한 결과 기존 테스트는 실패하지 않았습니다. 이 때문에 기존 테스트의 기대값은 하나도 바꾸지 않았고, `core.py`도 추가로 고치지 않았습니다.

## F. 결함별 기록

"수정 전 결과"는 교체 전 코드(`battery_v10_backup/core.py`)에 `test_review_fixes.py`를 그대로 실행해 확인했습니다(26개 중 25개 실패, 1개 통과). 통과한 1개는 대표값 불변 테스트로, 수정 전에도 통과해야 하는 것이 맞습니다.

| # | 결함 | 재현 테스트 (`tests/test_review_fixes.py`) | 수정 위치 | 결과 |
|---|---|---|---|---|
| 1 | 품질 집계: 같은 위험의 조치 중 하나만 미충족/미확인이어도 위험 전체가 "충족"으로 집계됨 | `test_quality_unmet_in_second_action_makes_overall_unmet`, `test_quality_mixed_met_and_unknown_is_not_met` | `core.py` `_combine_quality`(756), `risk_quality`(770), `quality_overall`(778) | 수정 전 실패 → 수정 후 통과. 미충족 1건이면 위험·전체 모두 "미충족", 충족+미확인 혼합은 "검증 중" |
| 2 | 미충족 위험인데 결론이 "검증 후보 또는 조건부"로 나옴 | `test_unmet_quality_concludes_excluded_not_candidate` | `core.py` `build_conclusion`(1065), `build_kpi`(1031) | 수정 전 실패 → 수정 후 통과. 결론 첫 문장과 KPI에 "현재 조건에서 적용 제외" |
| 3 | 추가 점유 시간이 미확인인 조치가 있는데 알려진 합계만으로 "충족" 판정 | `test_unknown_time_burden_is_lower_bound_and_holds_ok_verdict`, `test_unknown_time_burden_fail_stays_fail` | `core.py` `apply_occupancy_lower_bound`(792) | 수정 전 실패 → 수정 후 통과. 알려진 합계는 하한, 처리능력은 상한(≤)으로 두고 충족은 "계산 보류". 하한만으로 미달이면 "미달" 확정 |
| 4 | PFMEA 단위: `15 min`을 15 h로 계산, 허용되지 않은 단위·숫자 아닌 값을 통과시킴 | `test_pfmea_minutes_converted_to_hours`, `test_pfmea_disallowed_unit_blocked`(kWh·sec·빈 값·pt), `test_pfmea_non_numeric_value_is_input_error` | `core.py` `PFMEA_UNITS`(78), `_normalize_pfmea_unit`(727) | 수정 전 실패 → 수정 후 통과. 15 min = 0.25 h로 변환, 허용 외 단위·비숫자는 `InputError` |
| 5 | Boolean 변환: 모드 B `supply_temp_ok="False"`가 참(True)으로 처리됨 | `test_mode_b_string_false_disallows_heat_supply`, `test_to_bool_explicit`, `test_mode_b_uninterpretable_bool_is_error` | `core.py` `to_bool`(124), `drying_mode_b`(404 호출부) | 수정 전 실패 → 수정 후 통과. 문자열 "False"·"아니오"·0은 거짓, 해석 불가(maybe, 2, 0.5)는 `InputError` |
| 6 | 회생 전력이 화성 계통 전력을 넘거나 음수여도 계산됨 | `test_regen_over_formation_energy_rejected`, `test_regen_negative_rejected` | `core.py` `plant_energy`(514, 회생 상한·음수 검사) | 수정 전 실패 → 수정 후 통과. 상한 초과·음수는 `InputError` |
| 7 | r<0(전력 증가)이 입력 오류로 차단됨. 모드 B 보조부하 증가는 유효한 Trade-off | `test_energy_increase_is_valid_tradeoff_not_input_error` | `core.py` `plant_energy`(514, r>1만 차단), `increase_systems` 반환 | 수정 전 실패 → 수정 후 통과. 계산은 진행하고 "목표 미달"과 증가 계통을 결론에 표시 |
| 8 | 결론에 PFMEA 자동 반영 범위가 없어 수동 반영 대상 항목이 계산된 것처럼 읽힘 | `test_pfmea_link_types_and_conclusion_mentions_manual_items` | `core.py` `analyze_pfmea`(642, `link_type`), `build_conclusion`(1065) | 수정 전 실패 → 수정 후 통과. 자동 반영 1건(F02-A1)과 수동 반영 대상 7건을 결론에 명시 |
| - | 대표값 불변(참조) | `test_representative_values_unchanged` | - | 수정 전후 모두 통과. 처리능력 1.2308배, 절감 28.65%, 격차 +1.62pt, 대표 검산 전부 일치 |

## G. reporting.py 보완 (`tests/test_review_reporting.py`)

| 항목 | 재현 테스트 | 수정 위치 | 결과 |
|---|---|---|---|
| KPI "≤x배" 상한 표시 | `test_lower_bound_hold_still_shows_numbers_with_markers` | KPI는 `core.build_kpi`가 만들고 PDF 1쪽이 그대로 사용 | `≤1.231배` 표시 확인(렌더링) |
| 결론 첫 문장 "적용 제외" | `test_unmet_pdf_first_sentence_excluded_and_4_pages` | `build_conclusion`(core)이 만들고 PDF 1쪽이 그대로 사용 | 첫 문장이 "…현재 조건에서 적용 제외로 판정한다" |
| PFMEA 표 "(자동 반영)/(수동 반영 대상)" | `test_pfmea_table_shows_link_tags` | `core.pfmea_table`이 만들고 PDF 3쪽이 사용. `reporting.py` 3쪽에 표기 범례 한 줄 추가 | 표 칸에 태그 표시, 범례 추가 |
| 계산 보류 + `occupancy_lower_bound=True`에서도 수치 표시 | `test_lower_bound_hold_still_shows_numbers_with_markers` | `reporting.py` 2쪽 해석 문단(하한·상한·허용 점유 0.667 h 표시), 3쪽 요약(`≥0.25 h`) | 보류 상태에서도 수치 표시, 상한·하한 사실을 같이 적음 |
| plant `increase_systems` 표시 | `test_increase_systems_in_pdf_and_manifest` | `reporting.py` 2쪽 해석 문단, `write_manifest`의 `derived.increase_systems` | PDF와 manifest에 증가 계통("건조") 기록 |
| manifest 추가 필드 | 위 테스트들 | `reporting.py` `write_manifest` | `formation_status`, `occupancy_lower_bound`, `capacity_is_upper_bound`, `increase_systems`, `unmet_risks`, `manual_pending` |

3쪽 요약에서 문장을 한 줄 늘렸을 때 "계산 보류 + 하한" 조건에서만 5쪽으로 넘쳤습니다. 범례와 요약 문장을 줄여 4쪽으로 맞췄습니다.

## H. 재생성·검증 결과

| 검사 | 결과 |
|---|---|
| pytest 전체 | 90 passed / 0 failed (기존 59 + `test_review_fixes` 27 + `test_review_reporting` 4) |
| `run.py --scenario representative --out outputs --run-tests` | 종료 코드 0, `run_manifest.json`의 `test_status` = passed (90/0) |
| 대표 PDF | A4 4쪽. 1·3쪽 렌더링으로 육안 확인(넘침·글자 깨짐 없음, `≤`·`≥` 글리프 정상) |
| 긴 결론 조건 4종(적용 제외, 하한 보류, 적용 제외+하한 보류, 전력 증가) | 모두 4쪽. 적용 제외+하한 보류 조건의 1·3쪽을 렌더링해 확인 |
| 대표 KPI | 화성 1.231배, 절감 28.65%, 격차 +1.62pt (변경 없음) |

## I. 남은 한계

- (해소) 자동 연결 대상이지만 `impact_value`가 미확인인 행은 `link_type`을 "자동 반영 대상(값 미확인)"(`core.LINK_AUTO_PENDING`)으로 표시합니다. `auto_linked`·`manual_pending`에는 들어가지 않으며 테스트 `test_auto_target_with_unknown_value_is_labeled_pending`로 고정했습니다. 이 테스트 추가로 전체는 90개입니다.
- 3쪽은 여유가 거의 없습니다. PFMEA 행이나 요약 문장을 더 늘리면 5쪽이 되어 `build_pdf`가 `RuntimeError`로 중단합니다.
- Streamlit UI는 브라우저에서 직접 조작하지 않았습니다(`app.py`는 기존 AppTest 통과까지만 확인).
