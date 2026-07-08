# 🏭 조직 온실가스(GHG) 인벤토리 대시보드 + AI 자동매핑

GHG Protocol(Scope 1·2·3) 기준으로 조직의 온실가스 배출량을 산정하는 Streamlit 대시보드입니다.
실제 공개 배출계수 데이터를 통합했고, 회계원장 텍스트를 자동으로 Scope에 매핑하는 AI 기능과
Monte Carlo 기반 불확실성(신뢰구간) 분석을 포함합니다.

## 왜 만들었나

그린화학공학 전공 지식과 AI(NLP)를 결합해, ESG 실무에서 실제로 쓰이는 GHG Protocol 산정
체계를 코드로 구현한 포트폴리오 프로젝트입니다. 화학공정에서의 직접배출(Scope 1) 이해와
공개 데이터 기반 Scope 3 산정을 함께 다룹니다.

## 핵심 기능

| 탭 | 내용 |
|---|---|
| 📊 대시보드 | 총배출량, Scope 1/2/3 구성, 원단위 지표(직원당·매출당) |
| 🔍 상세·감축 | Scope 3 카테고리별 배출, 감축 시나리오, 데이터 품질 구성 |
| 📄 보고서·출처 | GHG Protocol 배출량 명세표, 계수 출처 투명 공개 |
| 🤖 AI 자동매핑 | 회계원장 텍스트 → Scope/카테고리 자동분류 → **인벤토리에 실제 반영** |
| 📐 불확실성 | Monte Carlo 시뮬레이션 기반 총배출량 90% 신뢰구간 |

## 데이터 출처

- **GHG Protocol** — Corporate / Scope 3 Standard (국제표준 프레임워크)
- **US EPA Supply Chain GHG Emission Factors v1.3** — 1,016개 산업(NAICS)별 실측
  지출기반 계수. Scope 3 구매품(Cat1) 11개 카테고리에 통합.
- **GIR·IPCC·DEFRA** — 전력·연료 활동계수(Scope 1·2)

계수 값과 출처는 `보고서·출처` 탭과 `data/` 폴더의 CSV에 전부 명시되어 있습니다.

## AI 자동매핑 — 어떻게 동작하나

전표·법인카드 내역(예: `전기요금 3,200,000원`)을 붙여넣으면:

1. 정규식으로 금액을 추출하고 설명 텍스트를 분리
2. 문자 2~3-gram TF-IDF로 15개 카테고리 코퍼스와 코사인 유사도 계산
3. 신뢰도 0.12 미만은 **"미매칭"으로 분류하지 않고 사람 확인을 요청** (오분류 방지)
4. "반영" 클릭 시 계산된 배출량이 메인 인벤토리(대시보드·상세·보고서 탭)에 실제로 합산

형태소 분석기(KoNLPy/Mecab) 없이 가벼운 방식으로 짧은 한국어 텍스트를 분류합니다.

## 불확실성 정량화 — 방법론

각 배출 라인을 정규분포 `N(배출량, (CV×배출량)²)`로 모델링하고 5,000회 이상 표본을
합산해 총배출량의 분포와 90% 신뢰구간을 계산합니다(GHG Protocol/IPCC가 권장하는
Monte Carlo 접근의 단순화 구현).

> **중요**: 변동계수(CV)는 "데이터 품질 등급이 낮을수록 불확실성이 크다"는 일반 원칙에
> 따른 예시값(1차 ±5%, 2차 ±15%, 3차 ±35~45%)이며, 개별 계수의 실측·문헌 검증치가
> 아닙니다. 감사·공식 보고 목적이라면 IPCC 국가 인벤토리 가이드라인의 항목별 수치로
> 교체해야 합니다.

## 실행 방법

```bash
git clone https://github.com/mungn0603-code/ghg-inventory-dashboard.git
cd ghg-inventory-dashboard
pip install -r requirements.txt
streamlit run app.py
```

## 프로젝트 구조

```
ghg-inventory-dashboard/
├── app.py                          # Streamlit UI (5개 탭)
├── ghg_model.py                     # 계산 엔진 (Inventory, EmissionLine)
├── data_loader.py                    # 계수 로드 + 출처 관리
├── auto_mapper.py                     # AI 자동매핑 (TF-IDF 기반)
├── uncertainty.py                      # Monte Carlo 불확실성 분석
├── data/
│   ├── factors_activity.csv            # Scope 1/2/3(거리기반) 활동계수
│   └── factors_scope3_spend.csv         # Scope 3 지출기반 계수 (실제 EPA 데이터)
├── .streamlit/config.toml               # Binance 다크 테마
└── requirements.txt
```

`app.py`(UI)와 `ghg_model.py`(계산), `data_loader.py`(데이터), `auto_mapper.py`(AI),
`uncertainty.py`(통계)가 완전히 분리되어 있어 각 모듈을 독립적으로 테스트·확장할 수
있습니다. 각 모듈은 `python <module>.py`로 실행하면 자체 검증(self-test)이 돌아갑니다.

## 알려진 한계

- Scope 3 지출기반 계수(EPA)는 미국 산업구조 기준이라 한국 조직엔 근사치입니다.
- AI 자동매핑은 의미 이해가 아닌 문자열 유사도 기반이며, 신뢰도 낮은 항목은 반드시
  사람이 확인해야 합니다.
- 불확실성 분석의 CV 값은 예시 가정이며(위 방법론 참고), 실제 감사 목적으로는
  검증된 수치로 교체가 필요합니다.

## 로드맵

- [x] Scope 1/2/3 조직 인벤토리 + 실제 EPA 데이터 통합
- [x] AI 자동매핑 (TF-IDF) + 메인 인벤토리 실연동
- [x] Monte Carlo 불확실성 정량화
- [ ] NAICS → KSIC(한국표준산업분류) 매핑
- [ ] 청구서 이미지 OCR 연동
- [ ] pytest + CI, DB 연동(다년도·다사업장)

## 라이선스

포트폴리오/교육 목적으로 자유롭게 참고하세요.
