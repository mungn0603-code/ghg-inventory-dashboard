"""
data_loader.py
조직 GHG 인벤토리용 계수/출처 로드.

- load_activity_factors(): Scope 1/2/3(거리기반) 활동계수 {activity: dict}
- load_spend_factors(): Scope 3 Cat1 지출기반 계수 {category: dict} (실제 EPA 데이터)
- get_sources(): 화면 표시용 출처 표
"""

import csv
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
ACTIVITY_CSV = os.path.join(DATA_DIR, "factors_activity.csv")
SPEND_CSV = os.path.join(DATA_DIR, "factors_scope3_spend.csv")


def load_activity_factors() -> dict:
    """{activity: {scope, category, factor, unit, method, data_quality, reference, ...}}"""
    out = {}
    with open(ACTIVITY_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[r["activity"]] = {
                "scope": int(r["scope"]),
                "category": r["s3_category"],
                "factor": float(r["factor"]),
                "unit": r["unit"],
                "method": r["method"],
                "data_quality": r["data_quality"],
                "reference": f'{r["reference"]} ({r["year"]})',
                "note": r["note"],
            }
    return out


def load_spend_factors() -> dict:
    """{category: {naics, factor, unit, reference}} — 실제 EPA Supply Chain 계수."""
    out = {}
    with open(SPEND_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[r["category"]] = {
                "naics": r["naics"],
                "factor": float(r["factor"]),
                "unit": r["unit"],
                "reference": f'{r["reference"]} ({r["year"]})',
            }
    return out


def get_sources() -> list:
    rows = []
    seen = set()
    for act, d in load_activity_factors().items():
        rows.append({"구분": f"Scope {d['scope']}", "항목": act,
                     "값": f"{d['factor']} {d['unit']}",
                     "출처": d["reference"], "품질": d["data_quality"]})
        seen.add(d["reference"])
    # 지출기반은 출처가 동일(EPA)하므로 대표 1행 + 카테고리 수 표기
    sp = load_spend_factors()
    any_ref = next(iter(sp.values()))["reference"] if sp else ""
    rows.append({"구분": "Scope 3", "항목": f"구매품 {len(sp)}개 카테고리(지출기반)",
                 "값": "0.08~1.01 kgCO2e/USD",
                 "출처": any_ref, "품질": "3차(지출기반)"})
    rows.append({"구분": "프레임워크", "항목": "Scope 1/2/3 산정 체계",
                 "값": "-", "출처": "GHG Protocol Corporate / Scope 3 Standard",
                 "품질": "국제표준"})
    return rows


if __name__ == "__main__":
    a = load_activity_factors()
    s = load_spend_factors()
    print("활동계수:", len(a), "개 |", list(a.keys()))
    print("지출계수:", len(s), "개 |", list(s.keys())[:3], "...")
    print("출처행:", len(get_sources()))
    print("data_loader.py self-test passed.")
