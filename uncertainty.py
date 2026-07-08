"""
uncertainty.py
Monte Carlo 시뮬레이션 기반 배출량 불확실성 정량화.

배경:
- GHG Protocol/IPCC는 배출량을 점추정치만이 아니라 신뢰구간과 함께 보고할 것을 권장한다
  (IPCC 2006 GL Vol.1 Ch.3의 오차전파/Monte Carlo 접근 방식).
- 각 라인의 데이터 품질 등급(1차 실측 / 2차 계수기반 / 3차 프록시·지출기반)에 따라
  상대 불확실성(변동계수, CV)을 부여하고, 라인별 정규분포 표본을 합산해 총배출량의
  분포를 근사한다.

중요 — 정직성 고지:
  아래 CV(변동계수) 값은 "등급이 낮을수록 불확실성이 크다"는 일반 원칙에 따른
  예시값이며, 이 프로젝트의 개별 배출계수에 대한 실측·문헌 검증치가 아니다.
  실제 감사·보고 목적이라면 IPCC 국가 인벤토리 가이드라인의 항목별 불확실성 표나
  자체 실측 데이터로 교체해야 한다. UI에서도 이 사실을 그대로 노출한다.
"""

import numpy as np

# 데이터 품질 등급(문자열에 포함된 키워드) -> 변동계수(CV, 상대 표준편차)
# 예시값 — 실제 감사 시 IPCC 국가 인벤토리 가이드라인 수치로 교체 권장.
CV_BY_QUALITY = [
    ("1차", 0.05),
    ("지출기반", 0.45),   # 3차·지출기반이 먼저 매칭되도록 순서 배치
    ("프록시", 0.40),
    ("2차", 0.15),
    ("3차", 0.35),
]
DEFAULT_CV = 0.30


def get_cv(data_quality: str) -> float:
    """데이터 품질 라벨 문자열에서 변동계수를 추정한다. AI역산 표기는 추가 가중."""
    base = DEFAULT_CV
    for keyword, cv in CV_BY_QUALITY:
        if keyword in data_quality:
            base = cv
            break
    if "AI" in data_quality:
        base = min(base + 0.15, 0.8)  # AI 자동매핑/역산분은 불확실성 가중
    return base


def simulate(lines, n_sims: int = 5000, seed: int = 42):
    """
    Inventory.lines(EmissionLine 리스트)를 받아 Monte Carlo 시뮬레이션 수행.

    각 라인의 co2e_kg를 평균으로, get_cv(data_quality)*co2e_kg를 표준편차로 하는
    정규분포에서 표본을 뽑아 합산한다 (0 미만은 0으로 클리핑).

    Returns
    -------
    dict: {
        'total_samples': np.ndarray (n_sims,),
        'scope_samples': {1: array, 2: array, 3: array},
        'mean', 'median', 'p5', 'p95', 'std': float (총배출량 기준, kg),
        'scope_ci': {scope: {'mean','p5','p95'}},
        'n_lines': int, 'n_sims': int,
    }
    """
    rng = np.random.default_rng(seed)
    if not lines:
        zeros = np.zeros(n_sims)
        return {
            "total_samples": zeros, "scope_samples": {1: zeros, 2: zeros, 3: zeros},
            "mean": 0.0, "median": 0.0, "p5": 0.0, "p95": 0.0, "std": 0.0,
            "scope_ci": {s: {"mean": 0.0, "p5": 0.0, "p95": 0.0} for s in (1, 2, 3)},
            "n_lines": 0, "n_sims": n_sims,
        }

    n_lines = len(lines)
    means = np.array([l.co2e_kg for l in lines])
    cvs = np.array([get_cv(l.data_quality) for l in lines])
    sds = means * cvs

    # (n_sims, n_lines) 표본 행렬 — 라인별 독립 정규분포, 음수는 0으로 클리핑
    samples = rng.normal(loc=means, scale=np.maximum(sds, 1e-9), size=(n_sims, n_lines))
    samples = np.clip(samples, 0, None)

    total_samples = samples.sum(axis=1)

    scope_samples = {}
    for s in (1, 2, 3):
        idx = [i for i, l in enumerate(lines) if l.scope == s]
        scope_samples[s] = samples[:, idx].sum(axis=1) if idx else np.zeros(n_sims)

    def ci(arr):
        return {
            "mean": float(np.mean(arr)),
            "p5": float(np.percentile(arr, 5)),
            "p95": float(np.percentile(arr, 95)),
        }

    return {
        "total_samples": total_samples,
        "scope_samples": scope_samples,
        "mean": float(np.mean(total_samples)),
        "median": float(np.median(total_samples)),
        "p5": float(np.percentile(total_samples, 5)),
        "p95": float(np.percentile(total_samples, 95)),
        "std": float(np.std(total_samples)),
        "scope_ci": {s: ci(scope_samples[s]) for s in (1, 2, 3)},
        "n_lines": n_lines, "n_sims": n_sims,
    }


if __name__ == "__main__":
    from ghg_model import EmissionLine

    test_lines = [
        EmissionLine(1, "직접", "도시가스", 60000, "m3", 2.176, 130560.0, "2차(계수기반)", "환경부"),
        EmissionLine(2, "간접", "구매전력", 1500000, "kWh", 0.4594, 689100.0, "2차(계수기반)", "GIR"),
        EmissionLine(3, "구매품(Cat1)", "철강", 30000000, "원", 0.787, 17489000 / 1000, "3차(지출기반)", "EPA"),
    ]
    r = simulate(test_lines, n_sims=5000)
    print(f"라인 수: {r['n_lines']}, 시뮬레이션: {r['n_sims']}회")
    print(f"평균: {r['mean']/1000:.2f} t, 중앙값: {r['median']/1000:.2f} t")
    print(f"90% 신뢰구간: [{r['p5']/1000:.2f}, {r['p95']/1000:.2f}] t")
    for s in (1, 2, 3):
        c = r["scope_ci"][s]
        print(f"  Scope {s}: 평균 {c['mean']/1000:.2f} t, "
              f"90%CI [{c['p5']/1000:.2f}, {c['p95']/1000:.2f}] t")

    point_total = sum(l.co2e_kg for l in test_lines)
    assert abs(r["mean"] - point_total) / point_total < 0.05, "시뮬레이션 평균이 점추정과 크게 어긋남"
    assert r["p5"] < r["mean"] < r["p95"], "신뢰구간 순서 이상"
    print("uncertainty.py self-test passed.")
