"""
auto_mapper.py
AI 자동매핑: 자유서술 지출/활동 텍스트 -> Scope·카테고리 자동분류.

기법: 문자 n-gram TF-IDF + 코사인 유사도.
(한국어 형태소 분석기 없이도 짧은 텍스트 분류에 실무적으로 충분함)

설계 원칙:
- 기존 ghg_model.py / data_loader.py는 건드리지 않는다.
- 이 모듈은 "텍스트 -> (매핑유형, 카테고리, 신뢰도)"만 책임진다.
- 실제 배출량 계산은 app.py에서 ghg_model 함수를 그대로 재사용한다.
"""

import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# 카테고리별 키워드 코퍼스. (매핑유형, 카테고리명) -> 대표 표현들
# 매핑유형 "activity": 물량(kWh/L/m3)로 환산 필요 -> 단가로 지출액을 역산
# 매핑유형 "spend"   : 지출액을 그대로 EPA 계수에 적용
CATEGORY_KEYWORDS = {
    ("activity", "구매전력"): "전기요금 전력비 전기세 한전 전력사용료 전기 사용료 전력요금 산업용전기",
    ("activity", "도시가스"): "가스요금 도시가스 가스비 보일러가스 도시가스요금 가스사용료",
    ("activity", "경유"): "경유 디젤 유류비 주유비 경유구매 화물차 주유 경유대금 연료비",
    ("activity", "휘발유"): "휘발유 가솔린 주유비 승용차 유류대 휘발유구매 차량연료",

    ("spend", "화학제품(기초화학)"): "화학원료 화학제품 케미컬 원자재화학 화학소재 구매 화학약품 기초화학원료",
    ("spend", "석유정제품"): "석유제품 연료유 석유화학원료 정제유 구매 원유부산물",
    ("spend", "철강"): "철강재 강재 철판 철강원자재 금속자재 철강구매 강판",
    ("spend", "플라스틱 제품"): "플라스틱원료 합성수지 플라스틱제품 수지원료 플라스틱구매",
    ("spend", "건설·기계장비"): "기계구매 설비투자 건설장비 기계장치 설비도입 장비구입",
    ("spend", "소프트웨어"): "소프트웨어 라이선스 구독료 솔루션구매 소프트웨어구매 SW라이선스",
    ("spend", "IT·프로그래밍 서비스"): "IT아웃소싱 SI용역 소프트웨어개발 프로그래밍 전산용역 개발외주",
    ("spend", "화물 트럭운송"): "운송비 화물비 물류비 택배비 배송비 트럭운송 운반비",
    ("spend", "항공 여객운송"): "항공권 비행기 항공료 출장항공 여객기 항공출장비",
    ("spend", "음식점·급식"): "식대 구내식당 케이터링 회식비 식음료 급식비",
    ("spend", "사무·행정지원"): "사무용품 행정용역 오피스서비스 사무지원 사무비품",
}

# 물량 역산용 단가(원/단위) — 근사치, 조정 가능. 실제 청구 단가는 지역/계약에 따라 다름.
UNIT_PRICE = {"구매전력": 130.0, "도시가스": 1000.0, "경유": 1650.0, "휘발유": 1750.0}
UNIT_OF = {"구매전력": "kWh", "도시가스": "m3", "경유": "L", "휘발유": "L"}

_AMOUNT_RE = re.compile(r"([\d,]+)\s*원")


def _build_index():
    keys = list(CATEGORY_KEYWORDS.keys())
    texts = [CATEGORY_KEYWORDS[k] for k in keys]
    vec = TfidfVectorizer(analyzer="char", ngram_range=(2, 3))
    X = vec.fit_transform(texts)
    return keys, vec, X


_KEYS, _VEC, _X = _build_index()

# 신뢰도 임계치. 미만이면 "미매칭"으로 처리해 오분류를 자동 반영하지 않는다.
CONFIDENCE_THRESHOLD = 0.12


def match_text(text: str, top_k: int = 1):
    """텍스트 -> [(매핑유형, 카테고리, 신뢰도)] 상위 top_k개."""
    v = _VEC.transform([text])
    sims = cosine_similarity(v, _X)[0]
    order = sims.argsort()[::-1][:top_k]
    return [(_KEYS[i][0], _KEYS[i][1], float(sims[i])) for i in order]


def parse_ledger_line(line: str):
    """'전기요금 3,200,000원' -> (설명, 금액) ; 금액 없으면 None."""
    m = _AMOUNT_RE.search(line)
    amount = float(m.group(1).replace(",", "")) if m else None
    desc = _AMOUNT_RE.sub("", line).strip(" -:\t")
    return desc, amount


def classify_ledger(text_block: str, usd_krw: float = 1350.0):
    """
    여러 줄 원장 텍스트를 파싱해 각 줄을 분류하고 예상 배출량까지 계산.
    반환: [{원문, 금액, 매핑유형, 카테고리, 신뢰도, 물량/단위, 예상배출량_kg, 상태}]
    """
    from ghg_model import line_from_spend  # 지연 임포트로 순환참조 방지

    results = []
    for raw in text_block.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        desc, amount = parse_ledger_line(raw)
        if not desc:
            continue
        matches = match_text(desc, top_k=1)
        mtype, cat, score = matches[0]
        row = {"원문": raw, "설명": desc, "금액": amount, "매핑유형": mtype,
               "카테고리": cat, "신뢰도": score}

        if score < CONFIDENCE_THRESHOLD or amount is None:
            row["상태"] = "미매칭(수동확인 필요)"
            row["배출량_kg"] = 0.0
            row["물량표시"] = "-"
        elif mtype == "activity":
            price = UNIT_PRICE[cat]
            usage = amount / price
            from data_loader import load_activity_factors
            factor = load_activity_factors()[cat]["factor"]
            row["배출량_kg"] = usage * factor
            row["물량표시"] = f"{usage:,.1f} {UNIT_OF[cat]} (단가 {price:,.0f}원 역산)"
            row["상태"] = "자동매핑"
        else:  # spend
            from data_loader import load_spend_factors
            sf = load_spend_factors()[cat]
            line = line_from_spend(cat, amount, sf["factor"], sf["reference"], usd_krw)
            row["배출량_kg"] = line.co2e_kg
            row["물량표시"] = f"{amount:,.0f}원 (지출기반)"
            row["상태"] = "자동매핑"
        results.append(row)
    return results


if __name__ == "__main__":
    tests = [
        "전기요금 3,200,000원",
        "가스비 결제 850,000원",
        "경유 주유 1,200,000원",
        "화물 운송비 지급 12,000,000원",
        "IT 아웃소싱 결제 5,000,000원",
        "철강 원자재 구매 30,000,000원",
        "구내식당 식대 2,000,000원",
        "회의실 대여료 500,000원",   # 매칭 안 되어야 정상 (임계치 미만 기대)
    ]
    print(f"{'원문':32} | {'유형':8} | {'카테고리':14} | 신뢰도 | 상태")
    print("-" * 90)
    for t in tests:
        desc, amt = parse_ledger_line(t)
        mtype, cat, score = match_text(desc, top_k=1)[0]
        status = "매칭" if score >= CONFIDENCE_THRESHOLD else "미매칭(기대대로)"
        print(f"{t:32} | {mtype:8} | {cat:14} | {score:.3f} | {status}")

    print()
    print("=== classify_ledger 통합 테스트 ===")
    block = "\n".join(tests)
    rows = classify_ledger(block)
    total = sum(r["배출량_kg"] for r in rows)
    matched = sum(1 for r in rows if r["상태"] == "자동매핑")
    print(f"총 {len(rows)}줄 중 {matched}줄 자동매핑, 합계 {total/1000:,.2f} tCO2e")
    for r in rows:
        print(f"  [{r['상태']:18}] {r['설명']:20} -> {r['카테고리']:14} "
              f"({r['신뢰도']:.2f}) {r['배출량_kg']/1000:.3f} t")

    # 회의실 대여료는 미매칭이어야 정상 (오분류 방지 검증)
    room = next(r for r in rows if "회의실" in r["설명"])
    assert room["상태"] == "미매칭(수동확인 필요)", f"임계치 조정 필요: {room}"
    # 전기요금은 activity로 잘 잡혀야 함
    elec = next(r for r in rows if "전기" in r["설명"])
    assert elec["카테고리"] == "구매전력", elec
    print("\nauto_mapper.py self-test passed.")
