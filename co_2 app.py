"""
app.py — 조직 온실가스 인벤토리 대시보드 (GHG Protocol Scope 1/2/3)
디자인: Binance 다크 테마 (DESIGN-binance.md)
데이터: GIR·IPCC·DEFRA(활동계수) + US EPA Supply Chain v1.3(지출기반 Scope 3)
실행: streamlit run app.py
"""

import streamlit as st
import plotly.graph_objects as go

from ghg_model import (
    Inventory, EmissionLine, line_from_activity, line_from_spend,
    intensity_per_employee, intensity_per_revenue,
    apply_reduction, tree_equivalent, DEFAULT_USD_KRW,
)
from data_loader import load_activity_factors, load_spend_factors, get_sources
from auto_mapper import classify_ledger, CONFIDENCE_THRESHOLD
from uncertainty import simulate, get_cv, CV_BY_QUALITY, DEFAULT_CV

# ---------- Binance 토큰 ----------
C = {"primary": "#FCD535", "primary_active": "#F0B90B", "canvas": "#0B0E11",
     "surface": "#1E2329", "surface_elevated": "#2B3139", "hairline": "#2B3139",
     "body": "#EAECEF", "muted": "#707A8A", "muted_strong": "#929AA5",
     "on_primary": "#181A20", "up": "#0ECB81", "down": "#F6465D",
     "turquoise": "#2DBDB6", "info": "#3B82F6", "violet": "#8B5CF6"}
SCOPE_COLOR = {1: C["down"], 2: C["info"], 3: C["turquoise"]}

st.set_page_config(page_title="조직 GHG 인벤토리", page_icon="🏭", layout="wide")


def css():
    st.markdown(f"""<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap');
    .stApp {{ background-color:{C['canvas']}; }}
    html,body,[class*="css"] {{ font-family:'Inter',-apple-system,sans-serif; color:{C['body']}; }}
    h1,h2,h3 {{ font-family:'Inter'!important; font-weight:700!important; letter-spacing:-0.5px; }}
    .block-container {{ padding-top:1.6rem; max-width:1320px; }}
    section[data-testid="stSidebar"] {{ background-color:{C['surface']}; border-right:1px solid {C['hairline']}; }}
    .hero-title {{ font-size:38px; font-weight:700; letter-spacing:-1px; margin:0; }}
    .hero-title .accent {{ color:{C['primary']}; }}
    .hero-sub {{ color:{C['muted']}; font-size:14px; margin-top:6px; font-weight:500; }}
    .section-title {{ font-size:12px; font-weight:600; text-transform:uppercase; letter-spacing:1px;
        color:{C['muted_strong']}; margin:22px 0 10px 0; }}
    .total-card {{ background:{C['surface']}; border:1px solid {C['hairline']}; border-radius:12px; padding:22px 26px; }}
    .total-card .cap {{ color:{C['muted']}; font-size:12px; font-weight:500; text-transform:uppercase; letter-spacing:0.5px; }}
    .total-card .val {{ font-family:'IBM Plex Mono'; font-size:42px; font-weight:700; color:{C['primary']};
        letter-spacing:-1px; line-height:1.1; margin-top:4px; }}
    .total-card .val small {{ font-size:18px; color:{C['muted_strong']}; font-weight:500; }}
    [data-testid="stMetric"] {{ background:{C['surface']}; border:1px solid {C['hairline']}; border-radius:12px; padding:16px 20px; }}
    [data-testid="stMetricLabel"] p {{ font-size:11px!important; font-weight:500!important; text-transform:uppercase;
        letter-spacing:0.5px; color:{C['muted']}!important; }}
    [data-testid="stMetricValue"] {{ font-family:'IBM Plex Mono'!important; font-weight:700!important; color:{C['body']}!important; }}
    .callout {{ background:{C['surface']}; border:1px solid {C['hairline']}; border-radius:12px; padding:18px 22px; }}
    .callout .big {{ font-family:'IBM Plex Mono'; font-size:26px; font-weight:700; color:{C['up']}; }}
    .callout .lbl {{ color:{C['muted']}; font-size:13px; }}
    .stTabs [data-baseweb="tab-list"] {{ gap:4px; border-bottom:1px solid {C['hairline']}; }}
    .stTabs [data-baseweb="tab"] {{ color:{C['muted']}; font-weight:600; }}
    .stTabs [aria-selected="true"] {{ color:{C['primary']}!important; }}
    table.rt {{ width:100%; border-collapse:collapse; font-size:13px; }}
    table.rt th {{ text-align:left; color:{C['muted_strong']}; font-weight:600; font-size:11px; text-transform:uppercase;
        letter-spacing:0.5px; padding:9px 12px; border-bottom:1px solid {C['hairline']}; }}
    table.rt td {{ color:{C['body']}; padding:10px 12px; border-bottom:1px solid {C['hairline']}; vertical-align:top; }}
    table.rt td.v {{ font-family:'IBM Plex Mono'; color:{C['primary']}; white-space:nowrap; }}
    table.rt td.n {{ color:{C['muted']}; font-size:12px; }}
    .badge {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:600; }}
    #MainMenu, footer {{ visibility:hidden; }}
    </style>""", unsafe_allow_html=True)


def style_fig(fig, h=300, legend=False):
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Mono", color=C["body"], size=12),
        margin=dict(t=10, b=10, l=10, r=10), height=h, showlegend=legend,
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=C["muted_strong"])))
    fig.update_xaxes(gridcolor=C["hairline"], zerolinecolor=C["hairline"], linecolor=C["hairline"],
        tickfont=dict(color=C["muted_strong"]))
    fig.update_yaxes(gridcolor=C["hairline"], zerolinecolor=C["hairline"], linecolor=C["hairline"],
        tickfont=dict(color=C["muted_strong"]))
    return fig


css()
AF = load_activity_factors()
SF = load_spend_factors()

# ==================== 사이드바 입력 ====================
sb = st.sidebar
sb.markdown(f'<p style="font-weight:700;font-size:16px;margin-bottom:4px">🏭 조직 프로필</p>', unsafe_allow_html=True)
org_name = sb.text_input("조직명", "샘플 화학㈜")
employees = sb.number_input("직원 수(명)", 1, 100000, 50, step=10)
revenue = sb.number_input("연매출(억원)", 0.0, 1e6, 200.0, step=10.0)
usd_krw = sb.number_input("적용 환율(원/USD)", 800.0, 2000.0, DEFAULT_USD_KRW, step=10.0,
                          help="Scope 3 지출기반 계수(USD)를 원화로 환산")

sb.markdown("---")
sb.markdown('<p class="section-title">Scope 1 · 직접배출</p>', unsafe_allow_html=True)
gas = sb.number_input("도시가스(m³/년)", 0.0, value=60000.0, step=1000.0)
diesel = sb.number_input("경유(L/년)", 0.0, value=8000.0, step=500.0)
petrol = sb.number_input("휘발유(L/년)", 0.0, value=4000.0, step=500.0)

sb.markdown('<p class="section-title">Scope 2 · 간접배출</p>', unsafe_allow_html=True)
elec = sb.number_input("구매전력(kWh/년)", 0.0, value=1500000.0, step=10000.0)
steam = sb.number_input("스팀·열(MJ/년)", 0.0, value=200000.0, step=10000.0)

sb.markdown('<p class="section-title">Scope 3 · 기타간접</p>', unsafe_allow_html=True)
air = sb.number_input("항공출장(인·km/년)", 0.0, value=300000.0, step=10000.0)
rail = sb.number_input("철도출장(인·km/년)", 0.0, value=150000.0, step=10000.0)
commute_km = sb.number_input("1인 평균 통근거리(편도 km)", 0.0, value=15.0, step=1.0)
work_days = sb.number_input("연간 근무일수", 0, 300, 240, step=10)
sb.caption("구매품(Cat1) — 카테고리별 연간 지출액(백만원)")
spend_inputs = {}
_defaults = {"화학제품(기초화학)": 500, "철강": 200, "IT·프로그래밍 서비스": 80, "화물 트럭운송": 60}
for cat in SF:
    spend_inputs[cat] = sb.number_input(cat, 0.0, value=float(_defaults.get(cat, 0)), step=10.0, key=f"sp_{cat}")

reduction = sb.slider("감축 목표(%)", 0, 50, 15)

# ==================== 인벤토리 구성 ====================
inv = Inventory()
# Scope 1
for act, usage in [("도시가스", gas), ("경유", diesel), ("휘발유", petrol)]:
    d = AF[act]
    inv.add(line_from_activity(1, d["category"], act, usage, d["unit"], d["factor"], d["data_quality"], d["reference"]))
# Scope 2
for act, usage in [("구매전력", elec), ("스팀·열", steam)]:
    d = AF[act]
    inv.add(line_from_activity(2, d["category"], act, usage, d["unit"], d["factor"], d["data_quality"], d["reference"]))
# Scope 3 거리기반
for act, usage in [("항공출장", air), ("철도출장", rail)]:
    d = AF[act]
    inv.add(line_from_activity(3, d["category"], act, usage, d["unit"], d["factor"], d["data_quality"], d["reference"]))
commute_km_total = commute_km * 2 * work_days * employees
dc = AF["차량통근"]
inv.add(line_from_activity(3, dc["category"], "차량통근", commute_km_total, dc["unit"], dc["factor"], dc["data_quality"], dc["reference"]))
# Scope 3 지출기반 (백만원 -> 원)
for cat, mil in spend_inputs.items():
    if mil > 0:
        inv.add(line_from_spend(cat, mil * 1_000_000, SF[cat]["factor"], SF[cat]["reference"], usd_krw))

# AI 자동매핑 반영분 (탭4에서 "반영" 버튼으로 커밋된 항목, session_state에 저장됨)
for line in st.session_state.get("automap_lines", []):
    inv.add(line)

total_kg = inv.total_kg()
total_t = total_kg / 1000
scopes = inv.by_scope()
s3cats = inv.by_s3_category()

# ==================== 헤더 ====================
st.markdown(
    f'<p class="hero-title">{org_name} <span class="accent">온실가스 인벤토리</span></p>'
    '<p class="hero-sub">GHG Protocol 기준 Scope 1·2·3 배출량 산정 · 활동계수(GIR·IPCC·DEFRA) + 지출기반(US EPA Supply Chain v1.3)</p>',
    unsafe_allow_html=True)

_n_auto = len(st.session_state.get("automap_lines", []))
if _n_auto > 0:
    _auto_kg = sum(l.co2e_kg for l in st.session_state["automap_lines"])
    st.markdown(
        f'<span class="badge" style="background:{C["up"]}22;color:{C["up"]}">'
        f'🤖 AI 자동매핑 {_n_auto}건 반영 중 · +{_auto_kg/1000:,.2f} tCO₂e</span>',
        unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 대시보드", "🔍 상세 · 감축", "📄 보고서 · 출처", "🤖 AI 자동매핑", "📐 불확실성"])

# -------------------- 탭 1 --------------------
with tab1:
    st.markdown('<p class="section-title">총 배출량</p>', unsafe_allow_html=True)
    a, b = st.columns([1.1, 2])
    with a:
        st.markdown(f'<div class="total-card"><div class="cap">연간 총 배출량</div>'
                    f'<div class="val">{total_t:,.1f} <small>tCO₂e</small></div></div>', unsafe_allow_html=True)
    with b:
        m1, m2, m3 = st.columns(3)
        m1.metric("Scope 1 (직접)", f"{scopes[1]/1000:,.1f} t")
        m2.metric("Scope 2 (전력·열)", f"{scopes[2]/1000:,.1f} t")
        m3.metric("Scope 3 (기타간접)", f"{scopes[3]/1000:,.1f} t")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<p class="section-title">Scope별 구성</p>', unsafe_allow_html=True)
        labels = [f"Scope {s}" for s in (1, 2, 3)]
        vals = [scopes[s] / 1000 for s in (1, 2, 3)]
        donut = go.Figure(go.Pie(labels=labels, values=vals, hole=0.62,
            marker=dict(colors=[SCOPE_COLOR[s] for s in (1, 2, 3)], line=dict(color=C["canvas"], width=2)),
            textinfo="label+percent", textfont=dict(color=C["body"], size=13),
            hovertemplate="%{label}: %{value:.1f} tCO₂e (%{percent})<extra></extra>"))
        donut.update_layout(annotations=[dict(text=f"{total_t:,.0f}<br>tCO₂e", x=0.5, y=0.5,
            font=dict(color=C["body"], size=18, family="IBM Plex Mono"), showarrow=False)])
        st.plotly_chart(style_fig(donut, 300), use_container_width=True)
    with c2:
        st.markdown('<p class="section-title">원단위 지표 (Intensity)</p>', unsafe_allow_html=True)
        k1, k2 = st.columns(2)
        k1.metric("직원 1인당", f"{intensity_per_employee(total_kg, employees):,.2f} tCO₂e")
        k2.metric("매출 억원당", f"{intensity_per_revenue(total_kg, revenue):,.2f} tCO₂e")
        st.markdown('<p class="section-title" style="margin-top:18px">Scope 누적 막대</p>', unsafe_allow_html=True)
        bar = go.Figure()
        for s in (1, 2, 3):
            bar.add_trace(go.Bar(name=f"Scope {s}", x=["배출량"], y=[scopes[s] / 1000],
                marker_color=SCOPE_COLOR[s]))
        bar.update_layout(barmode="stack", yaxis_title="tCO₂e")
        st.plotly_chart(style_fig(bar, 230, legend=True), use_container_width=True)

# -------------------- 탭 2 --------------------
with tab2:
    st.markdown('<p class="section-title">Scope 3 카테고리별 배출</p>', unsafe_allow_html=True)
    if s3cats:
        items = sorted(s3cats.items(), key=lambda x: x[1], reverse=True)
        cbar = go.Figure(go.Bar(x=[v / 1000 for _, v in items], y=[k for k, _ in items],
            orientation="h", marker_color=C["turquoise"],
            text=[f"{v/1000:,.1f}" for _, v in items], textposition="outside",
            textfont=dict(color=C["body"])))
        cbar.update_layout(xaxis_title="tCO₂e")
        st.plotly_chart(style_fig(cbar, 300), use_container_width=True)

    st.markdown('<p class="section-title">감축 시나리오</p>', unsafe_allow_html=True)
    reduced_t = apply_reduction(total_kg, reduction) / 1000
    saved_t = total_t - reduced_t
    sc1, sc2 = st.columns([2, 1])
    with sc1:
        rb = go.Figure()
        rb.add_trace(go.Bar(name="현재", x=["연 배출량"], y=[total_t], width=0.35, marker_color=C["muted"],
            text=[f"{total_t:,.0f}"], textposition="outside", textfont=dict(color=C["body"])))
        rb.add_trace(go.Bar(name=f"{reduction}% 감축", x=["연 배출량"], y=[reduced_t], width=0.35, marker_color=C["up"],
            text=[f"{reduced_t:,.0f}"], textposition="outside", textfont=dict(color=C["up"])))
        rb.update_layout(barmode="group", yaxis_title="tCO₂e")
        st.plotly_chart(style_fig(rb, 260, legend=True), use_container_width=True)
    with sc2:
        st.markdown(f'<div class="callout"><span class="big">-{saved_t:,.1f}</span>'
            f'<span class="lbl"> tCO₂e/년 감축</span><br>'
            f'<span class="lbl">나무 {tree_equivalent(saved_t*1000):,.0f}그루가 1년간 흡수하는 양</span></div>',
            unsafe_allow_html=True)

    st.markdown('<p class="section-title">데이터 품질 구성</p>', unsafe_allow_html=True)
    dq = inv.data_quality_mix()
    dq_items = sorted(dq.items(), key=lambda x: x[1], reverse=True)
    rows = "".join(f'<tr><td>{k}</td><td class="v">{v/1000:,.1f} t</td>'
                   f'<td class="n">{v/total_kg*100:,.0f}%</td></tr>' for k, v in dq_items)
    st.markdown(f'<table class="rt"><thead><tr><th>데이터 품질 등급</th><th>배출량</th><th>비중</th></tr></thead>'
                f'<tbody>{rows}</tbody></table>', unsafe_allow_html=True)
    st.caption("1차(실측) > 2차(계수기반) > 3차(프록시·지출기반) 순으로 신뢰도가 높습니다. 지출기반 비중이 높을수록 정밀 산정 여지가 큽니다.")

# -------------------- 탭 3 --------------------
with tab3:
    st.markdown('<p class="section-title">GHG Protocol 배출량 명세 (요약)</p>', unsafe_allow_html=True)
    line_rows = ""
    for l in sorted(inv.lines, key=lambda x: (x.scope, -x.co2e_kg)):
        line_rows += (f'<tr><td>Scope {l.scope}</td><td>{l.category}</td><td>{l.activity}</td>'
                      f'<td class="v">{l.co2e_kg/1000:,.2f} t</td><td class="n">{l.data_quality}</td></tr>')
    st.markdown(f'<table class="rt"><thead><tr><th>Scope</th><th>카테고리</th><th>활동</th>'
                f'<th>배출량</th><th>품질</th></tr></thead><tbody>{line_rows}</tbody></table>',
                unsafe_allow_html=True)

    st.markdown('<p class="section-title" style="margin-top:24px">데이터 출처</p>', unsafe_allow_html=True)
    src_rows = "".join(f'<tr><td>{s["구분"]}</td><td>{s["항목"]}</td><td class="v">{s["값"]}</td>'
                       f'<td class="n">{s["출처"]}</td><td class="n">{s["품질"]}</td></tr>'
                       for s in get_sources())
    st.markdown(f'<table class="rt"><thead><tr><th>구분</th><th>항목</th><th>값</th>'
                f'<th>출처</th><th>품질</th></tr></thead><tbody>{src_rows}</tbody></table>',
                unsafe_allow_html=True)
    st.caption("Scope 3 구매품 계수는 US EPA Supply Chain GHG Emission Factors v1.3(USD2022, NAICS 산업별)의 실제 값이며, "
               "적용 환율로 원화 지출을 환산해 산정합니다. 활동계수·환율·통근 가정은 조정 가능합니다.")

# -------------------- 탭 4: AI 자동매핑 --------------------
with tab4:
    st.markdown('<p class="section-title">회계원장 텍스트 → Scope 자동분류</p>', unsafe_allow_html=True)
    st.caption("전표·법인카드 내역을 줄 단위로 붙여넣으면, 문자 n-gram TF-IDF 유사도로 Scope·카테고리를 자동 추정하고 "
               "즉시 배출량까지 계산합니다. \u201c반영\u201d을 누르면 대시보드·상세·보고서 탭의 총계에 실제로 합산됩니다.")

    default_ledger = (
        "전기요금 3,200,000원\n"
        "가스비 결제 850,000원\n"
        "경유 주유 1,200,000원\n"
        "화물 운송비 지급 12,000,000원\n"
        "IT 아웃소싱 결제 5,000,000원\n"
        "철강 원자재 구매 30,000,000원\n"
        "구내식당 식대 2,000,000원\n"
        "회의실 대여료 500,000원"
    )
    ledger_text = st.text_area("회계원장 붙여넣기 (한 줄에 한 항목, 끝에 '~~원' 포함)",
                               value=default_ledger, height=180)
    bcol1, bcol2, bcol3 = st.columns([1.3, 1.3, 3])
    preview = bcol1.button("🔍 미리보기 (분류만)")
    commit = bcol2.button("✅ 인벤토리에 반영")
    clear = bcol3.button("🗑️ 반영 취소 (초기화)")

    if clear:
        st.session_state["automap_lines"] = []
        st.rerun()

    if commit:
        rows = classify_ledger(ledger_text, usd_krw)
        new_lines = []
        for r in rows:
            if r["상태"] != "자동매핑":
                continue
            cat = r["카테고리"]
            if r["매핑유형"] == "activity":
                d = AF[cat]
                line = EmissionLine(
                    scope=d["scope"], category=d["category"],
                    activity=f'{r["설명"]}(AI자동매핑)', usage=r["금액"], unit="원",
                    factor=d["factor"], co2e_kg=r["배출량_kg"],
                    data_quality=f'{d["data_quality"]}·AI역산', reference=d["reference"],
                )
            else:
                sf = SF[cat]
                line = EmissionLine(
                    scope=3, category="구매품(Cat1)",
                    activity=f'{r["설명"]}(AI자동매핑)', usage=r["금액"], unit="원",
                    factor=sf["factor"], co2e_kg=r["배출량_kg"],
                    data_quality="3차(지출기반)·AI", reference=sf["reference"],
                )
            new_lines.append(line)
        st.session_state["automap_lines"] = new_lines
        st.rerun()

    if preview or ledger_text:
        rows = classify_ledger(ledger_text, usd_krw)
        if rows:
            matched = [r for r in rows if r["상태"] == "자동매핑"]
            unmatched = [r for r in rows if r["상태"] != "자동매핑"]
            auto_total_t = sum(r["배출량_kg"] for r in matched) / 1000

            m1, m2, m3 = st.columns(3)
            m1.metric("입력 줄 수", f"{len(rows)}")
            m2.metric("자동매핑 성공", f"{len(matched)} / {len(rows)}")
            m3.metric("자동매핑 배출량", f"{auto_total_t:,.2f} tCO₂e")

            def conf_badge(score):
                if score >= 0.35:
                    color, label = C["up"], "높음"
                elif score >= CONFIDENCE_THRESHOLD:
                    color, label = C["primary"], "보통"
                else:
                    color, label = C["down"], "낮음"
                return f'<span class="badge" style="background:{color}22;color:{color}">{label} {score:.2f}</span>'

            body = ""
            for r in rows:
                badge = conf_badge(r["신뢰도"])
                cat_disp = r["카테고리"] if r["상태"] == "자동매핑" else "-"
                body += (f'<tr><td>{r["설명"]}</td><td class="n">{r["매핑유형"]}</td>'
                        f'<td>{cat_disp}</td><td>{badge}</td>'
                        f'<td class="n">{r["물량표시"]}</td>'
                        f'<td class="v">{r["배출량_kg"]/1000:,.3f} t</td></tr>')
            st.markdown(f'<table class="rt"><thead><tr><th>원문(설명)</th><th>유형</th>'
                        f'<th>매핑 카테고리</th><th>신뢰도</th><th>환산 물량/방식</th>'
                        f'<th>배출량</th></tr></thead><tbody>{body}</tbody></table>',
                        unsafe_allow_html=True)

            if unmatched:
                st.warning(f"{len(unmatched)}건은 신뢰도가 낮아 자동분류하지 않았습니다. "
                          "표현을 구체화하거나(예: '~비', '~요금' 명시) 수동으로 카테고리를 지정하세요. "
                          "이 항목들은 \u201c반영\u201d을 눌러도 인벤토리에 포함되지 않습니다.")
        else:
            st.info("분류할 줄이 없습니다. 각 줄 끝에 금액(예: '1,000,000원')을 포함해 입력하세요.")

    _n = len(st.session_state.get("automap_lines", []))
    if _n > 0:
        st.success(f"현재 {_n}건이 메인 인벤토리에 반영되어 있습니다. 다른 탭에서 합산된 총계를 확인하세요.")

    st.markdown('<p class="section-title" style="margin-top:24px">한계 · 주의사항</p>', unsafe_allow_html=True)
    st.caption(
        "· 문자 n-gram 유사도는 형태소 분석 없이 짧은 한국어 텍스트를 분류하는 경량 기법이며, "
        "완전한 의미 이해가 아닌 표기 유사도 기반입니다. 신뢰도 '낮음' 항목은 반드시 사람이 확인해야 합니다.\n\n"
        "· 전기·가스·연료 항목은 청구 금액을 근사 단가로 나눠 물량(kWh/m³/L)을 역산합니다 — "
        "실제 청구서의 사용량(kWh) 값을 직접 넣는 것보다 정확도가 낮습니다. 그래서 품질 등급에 '·AI역산' 표기가 붙습니다."
    )

# -------------------- 탭 5: 불확실성 정량화 (Monte Carlo) --------------------
with tab5:
    st.markdown('<p class="section-title">배출량 신뢰구간 — Monte Carlo 시뮬레이션</p>', unsafe_allow_html=True)
    st.caption("점추정치 하나 대신, 데이터 품질 등급별 불확실성을 반영해 총배출량의 분포와 90% 신뢰구간을 계산합니다.")

    n_sims = st.select_slider("시뮬레이션 반복 횟수", options=[1000, 2000, 5000, 10000], value=5000)
    sim = simulate(inv.lines, n_sims=n_sims, seed=42)

    if sim["n_lines"] == 0:
        st.info("입력된 배출 항목이 없습니다. 사이드바에 활동량을 입력하면 시뮬레이션이 계산됩니다.")
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric("점추정 총배출량", f"{total_t:,.1f} tCO₂e")
        m2.metric("시뮬레이션 평균", f"{sim['mean']/1000:,.1f} tCO₂e")
        m3.metric("90% 신뢰구간", f"{sim['p5']/1000:,.0f} ~ {sim['p95']/1000:,.0f} t")

        c1, c2 = st.columns([1.6, 1])
        with c1:
            st.markdown('<p class="section-title">총배출량 분포</p>', unsafe_allow_html=True)
            hist = go.Figure()
            hist.add_trace(go.Histogram(x=sim["total_samples"] / 1000, nbinsx=40,
                                        marker_color=C["turquoise"], opacity=0.85))
            hist.add_vline(x=sim["p5"] / 1000, line=dict(color=C["muted_strong"], dash="dash"))
            hist.add_vline(x=sim["p95"] / 1000, line=dict(color=C["muted_strong"], dash="dash"))
            hist.add_vline(x=sim["mean"] / 1000, line=dict(color=C["primary"], width=2))
            hist.update_layout(xaxis_title="tCO₂e", yaxis_title="빈도")
            st.plotly_chart(style_fig(hist, 320), use_container_width=True)
            st.caption("점선 = 90% 신뢰구간(5~95백분위), 굵은 세로선 = 시뮬레이션 평균")

        with c2:
            st.markdown('<p class="section-title">Scope별 90% 신뢰구간</p>', unsafe_allow_html=True)
            for s in (1, 2, 3):
                ci = sim["scope_ci"][s]
                st.markdown(
                    f'<div class="callout" style="margin-bottom:12px">'
                    f'<span class="lbl">Scope {s}</span><br>'
                    f'<span class="big" style="color:{SCOPE_COLOR[s]};font-size:20px">'
                    f'{ci["mean"]/1000:,.1f} t</span><br>'
                    f'<span class="lbl">[{ci["p5"]/1000:,.1f} ~ {ci["p95"]/1000:,.1f}]</span></div>',
                    unsafe_allow_html=True)

        st.markdown('<p class="section-title">라인별 적용 변동계수(CV)</p>', unsafe_allow_html=True)
        cv_rows = ""
        for l in sorted(inv.lines, key=lambda x: -x.co2e_kg)[:8]:
            cv = get_cv(l.data_quality)
            cv_rows += (f'<tr><td>{l.activity}</td><td class="n">{l.data_quality}</td>'
                       f'<td class="v">±{cv*100:.0f}%</td>'
                       f'<td class="n">{l.co2e_kg/1000:,.2f} t</td></tr>')
        st.markdown(f'<table class="rt"><thead><tr><th>항목</th><th>데이터 품질</th>'
                    f'<th>적용 CV</th><th>배출량</th></tr></thead><tbody>{cv_rows}</tbody></table>',
                    unsafe_allow_html=True)
        if len(inv.lines) > 8:
            st.caption(f"배출량 상위 8건만 표시 (전체 {len(inv.lines)}건)")

    st.markdown('<p class="section-title" style="margin-top:24px">방법론 · 한계</p>', unsafe_allow_html=True)
    st.caption(
        "· 각 라인을 정규분포 N(배출량, (CV×배출량)²)로 모델링하고 독립 표본을 합산합니다. "
        "GHG Protocol/IPCC가 권장하는 Monte Carlo 방식의 단순화 구현입니다.\n\n"
        "· 변동계수(CV)는 \u201c품질 등급이 낮을수록 불확실성이 크다\u201d는 일반 원칙에 따른 "
        "예시값(1차 ±5%, 2차 ±15%, 3차 ±35~45%)이며, 이 프로젝트 개별 계수의 실측·문헌 검증치가 아닙니다. "
        "감사·공식 보고 목적이라면 IPCC 국가 인벤토리 가이드라인의 항목별 수치로 교체해야 합니다.\n\n"
        "· 라인 간 상관관계(예: 동일 연료가격 변동이 여러 항목에 동시 영향)는 반영하지 않은 독립 가정입니다."
    )
