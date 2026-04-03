"""Streamlit dashboard: SDL Service Desk metrics from Jira."""

import os
from datetime import date, timedelta

import streamlit as st
from dotenv import load_dotenv

import jira_client
from ui.styles import inject_styles
from ui.charts import COLORS, pie, bar_h, grouped_bar, line, donut, bar_v, csat_bar
from ui.components import top_n, render_stars, kpi_card

load_dotenv()

# ── Constants ─────────────────────────────────────────────────────────────────
CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", "300"))

# Period pill label → internal period key
PERIOD_MAP = {
    "Hoje": "day",
    "Semana": "week",
    "Mês": "month",
    "Período": "custom",
}

# Grid layout: default number of chart columns per row
DEFAULT_COLS = 4

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="HelpMe – Service Desk Dashboard",
    page_icon="🚚",
    layout="wide",
)

inject_styles()


# ── Cached fetchers ───────────────────────────────────────────────────────────
@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def fetch_assignees():
    return jira_client.get_assignees()


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def fetch_metrics(period, date_from, date_to, assignee):
    return jira_client.get_metrics(
        period=period, date_from=date_from, date_to=date_to, assignee=assignee
    )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def fetch_open_by_month():
    return jira_client.get_open_by_month()


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def fetch_csat_by_month():
    return jira_client.get_csat_by_month()


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    "<h1 style='margin:0 0 0.5rem 0;font-size:1.6rem;line-height:1.2'>"
    "<span style='color:#3b82f6;text-shadow:0 0 16px rgba(59,130,246,0.3)'>HelpMe</span> "
    "<span style='font-size:0.95rem;color:#94a3b8;font-weight:400'>Service Desk Dashboard</span>"
    "</h1>",
    unsafe_allow_html=True,
)

# ── Horizontal filter bar ─────────────────────────────────────────────────────
try:
    assignees_list = fetch_assignees()
except Exception:
    assignees_list = []

fcol_period, fcol_layout, fcol_analyst, fcol_btn = st.columns([3.5, 2, 3, 0.8])
with fcol_period:
    period_label = st.radio(
        "Período", list(PERIOD_MAP.keys()), index=1, horizontal=True, label_visibility="collapsed"
    )
with fcol_layout:
    layout_label = st.radio(
        "Colunas", ["3 colunas", "4 colunas"], index=1, horizontal=True,
        label_visibility="collapsed", key="layout_cols",
    )
with fcol_analyst:
    selected_assignee = st.selectbox(
        "Analista", ["Todos os analistas"] + assignees_list, label_visibility="collapsed"
    )
with fcol_btn:
    if st.button("↻ Atualizar", width="stretch"):
        st.cache_data.clear()
        st.rerun()

n_cols = 3 if layout_label == "3 colunas" else 4
period = PERIOD_MAP[period_label]
assignee_filter = None if selected_assignee == "Todos os analistas" else selected_assignee

date_from = date_to = None
if period == "custom":
    dc1, dc2, _ = st.columns([2, 2, 4])
    date_from = str(dc1.date_input("De", value=date.today() - timedelta(days=30)))
    date_to = str(dc2.date_input("Até", value=date.today()))

st.markdown("<hr>", unsafe_allow_html=True)

# ═════════════════════════ MÉTRICAS ══════════════════════════════════════════
with st.spinner("Carregando métricas..."):
    try:
        data = fetch_metrics(period, date_from, date_to, assignee_filter)
        error = data.get("error")
    except Exception:
        data = {}
        error = None
        st.error("Erro ao carregar dados do Jira. Verifique a conexão e as credenciais.")
        st.stop()

if error:
    st.error(f"Erro ao carregar métricas: {error}")
    st.stop()

kpi = data.get("kpi", {})
csat = data.get("csat", {"avg": 0, "count": 0})
csat_avg = csat.get("avg", 0)
stars_html = render_stars(csat_avg) if csat_avg else ""

# ── KPI cards ─────────────────────────────────────────────────────────────
st.markdown(
    '<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:0.75rem;margin-bottom:0.85rem">'
    + kpi_card("Total no período", kpi.get("total_created", 0))
    + kpi_card("Não fechados no período", kpi.get("total_open", 0), color="#ef4444")
    + kpi_card("Resolvidos no período", kpi.get("total_closed", 0), color="#22c55e")
    + kpi_card("Tempo médio resolução", f"{kpi.get('avg_resolution_days', 0)}d", color="#22d3ee")
    + kpi_card(
        f"CSAT médio {stars_html}",
        f"{csat_avg:.1f}",
        color="#f59e0b",
        extra=f"{csat.get('count', 0)} avaliações",
    )
    + "</div>",
    unsafe_allow_html=True,
)

# ── Prepare chart data ────────────────────────────────────────────────────
by_cat = top_n(data.get("by_category", {}))
by_grp = data.get("by_group", {})
by_assignee = data.get("by_assignee", {})
by_day = data.get("by_day", {})
closed_by_day = data.get("closed_by_day", {})
by_priority = data.get("by_priority", {})
priority_meta = data.get("priority_meta", [])
p_color_map = {p["name"]: p["color"] for p in priority_meta}

try:
    obm = fetch_open_by_month()
except Exception:
    obm = []

try:
    cbm = fetch_csat_by_month()
except Exception:
    cbm = []


# ── Chart render functions ────────────────────────────────────────────────
def _render_cat(col):
    if by_cat:
        col.plotly_chart(pie(
            list(by_cat.keys()), list(by_cat.values()),
            "Chamados por Categoria",
            "Distribuição por categoria — identifica o que mais demanda o time",
        ), width="stretch")
    else:
        col.info("Sem dados de categoria")


def _render_grp(col):
    if by_grp:
        col.plotly_chart(pie(
            list(by_grp.keys()), list(by_grp.values()),
            "Chamados por Grupo",
            "Volume por grupo do portal de serviços — visão de área de suporte",
        ), width="stretch")
    else:
        col.info("Sem dados de grupo")


def _render_assignee(col):
    if by_assignee:
        sorted_a = sorted(by_assignee.items(), key=lambda x: x[1])
        col.plotly_chart(bar_h(
            [k for k, _ in sorted_a], [v for _, v in sorted_a],
            "Chamados por Analista",
            "Volume atribuído a cada analista — apoia gestão de capacidade",
        ), width="stretch")
    else:
        col.info("Sem dados de analista")


def _render_opened_closed(col):
    if by_day or closed_by_day:
        all_days = sorted(set(list(by_day.keys()) + list(closed_by_day.keys())))
        col.plotly_chart(grouped_bar(
            all_days,
            [by_day.get(d, 0) for d in all_days],
            [closed_by_day.get(d, 0) for d in all_days],
            "Abertos vs Fechados por Dia",
            "Comparativo de entradas e resoluções no período",
        ), width="stretch")
    else:
        col.info("Sem dados diários")


def _render_trend(col):
    if by_day:
        all_days_s = sorted(by_day.keys())
        col.plotly_chart(line(
            all_days_s, [by_day[d] for d in all_days_s],
            "Volume Diário (Tendência)",
            "Evolução diária de chamados criados — identifica picos e sazonalidade",
        ), width="stretch")
    else:
        col.info("Sem dados diários")


def _render_priority(col):
    if by_priority:
        p_labels = list(by_priority.keys())
        p_values = list(by_priority.values())
        p_colors = [p_color_map.get(lbl, "#94a3b8") for lbl in p_labels]
        col.plotly_chart(donut(
            p_labels, p_values, p_colors,
            "Chamados por Prioridade",
            "Breakdown por prioridade — útil para avaliar impacto e urgência",
        ), width="stretch")
    else:
        col.info("Sem dados de prioridade")


def _render_open_month(col):
    if obm:
        col.plotly_chart(bar_v(
            [m["label"] for m in obm], [m["count"] for m in obm],
            [COLORS[0]] * len(obm),
            "Chamados Abertos por Mês",
            "Tickets criados em cada mês que ainda estão em aberto hoje",
        ), width="stretch")
    else:
        col.info("Sem dados de abertos por mês")


def _render_csat_month(col):
    if cbm:
        col.plotly_chart(csat_bar(
            [m["label"] for m in cbm], [m["avg"] for m in cbm],
            "CSAT por Mês",
            "Nota média de satisfação por mês nos últimos 6 meses",
        ), width="stretch")
    else:
        col.info("Sem dados de CSAT")


charts = [
    _render_cat, _render_grp, _render_assignee, _render_opened_closed,
    _render_trend, _render_priority, _render_open_month, _render_csat_month,
]

# ── Render charts in rows of n_cols ───────────────────────────────────────
for row_start in range(0, len(charts), n_cols):
    row_charts = charts[row_start:row_start + n_cols]
    cols = st.columns(n_cols)
    for i, render_fn in enumerate(row_charts):
        render_fn(cols[i])
