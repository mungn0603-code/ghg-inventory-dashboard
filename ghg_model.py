"""
ghg_model.py
조직 온실가스 인벤토리 계산 엔진 (GHG Protocol Scope 1/2/3).

설계:
- 순수 함수 중심. UI/파일 IO는 data_loader/app이 담당한다.
- 배출량 = 활동량 × 배출계수 (활동기반) 또는 지출액 × 계수 (지출기반).
- Scope 1/2/3, Scope 3 카테고리별 집계, 원단위 KPI, 데이터 품질 요약 제공.
"""

from dataclasses import dataclass, field
from typing import Optional


# 지출기반 Scope 3 계수는 USD 기준 -> 원화 환산 가정(조정 가능)
DEFAULT_USD_KRW = 1350.0


@dataclass
class EmissionLine:
    scope: int
    category: str          # 직접 / 간접 / 출장(Cat6) / 통근(Cat7) / 구매품(Cat1)
    activity: str
    usage: float
    unit: str
    factor: float
    co2e_kg: float
    data_quality: str
    reference: str


@dataclass
class Inventory:
    lines: list = field(default_factory=list)

    def add(self, line: EmissionLine):
        if line.usage and line.usage > 0:
            self.lines.append(line)

    # --- 집계 ---
    def total_kg(self) -> float:
        return sum(l.co2e_kg for l in self.lines)

    def by_scope(self) -> dict:
        out = {1: 0.0, 2: 0.0, 3: 0.0}
        for l in self.lines:
            out[l.scope] = out.get(l.scope, 0.0) + l.co2e_kg
        return out

    def by_s3_category(self) -> dict:
        out = {}
        for l in self.lines:
            if l.scope == 3:
                out[l.category] = out.get(l.category, 0.0) + l.co2e_kg
        return out

    def data_quality_mix(self) -> dict:
        """데이터 품질 등급별 배출 비중."""
        out = {}
        for l in self.lines:
            key = l.data_quality
            out[key] = out.get(key, 0.0) + l.co2e_kg
        return out


def line_from_activity(scope, category, activity, usage, unit, factor,
                       data_quality, reference) -> EmissionLine:
    return EmissionLine(scope, category, activity, usage, unit, factor,
                        usage * factor, data_quality, reference)


def line_from_spend(category, spend_krw, factor_usd, reference,
                    usd_krw=DEFAULT_USD_KRW) -> EmissionLine:
    """지출기반(Scope 3 Cat1): 원화 지출 -> USD 환산 -> 계수 적용."""
    spend_usd = spend_krw / usd_krw
    co2e = spend_usd * factor_usd
    return EmissionLine(3, "구매품(Cat1)", category, spend_krw, "원",
                        factor_usd, co2e, "3차(지출기반)",
                        reference)


# --- 원단위(intensity) KPI ---
def intensity_per_employee(total_kg: float, employees: int) -> float:
    if not employees:
        return 0.0
    return (total_kg / 1000.0) / employees  # tCO2e/인

def intensity_per_revenue(total_kg: float, revenue_krw_100m: float) -> float:
    """tCO2e / 매출 억원."""
    if not revenue_krw_100m:
        return 0.0
    return (total_kg / 1000.0) / revenue_krw_100m


# --- 감축 시나리오 ---
def apply_reduction(co2e_kg: float, pct: float) -> float:
    return co2e_kg * (1 - pct / 100.0)


# --- 직관적 환산 ---
TREE_KG_PER_YEAR = 6.6

def tree_equivalent(co2e_kg_year: float) -> float:
    return co2e_kg_year / TREE_KG_PER_YEAR if TREE_KG_PER_YEAR else 0.0
