"""Dashboard: KPIs, top sellers, duplicate EANs, weekday/hour heatmap."""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from db import repository

st.set_page_config(page_title="Dashboard — DR Sistemas", page_icon="📊", layout="wide")
st.title("📊 Dashboard")

WEEKDAYS_PT = ["Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"]

# --- Date range ---------------------------------------------------------------
default_end = datetime.now().date()
default_start = default_end - timedelta(days=30)
col_d1, col_d2, col_top = st.columns([1, 1, 1])
d_ini = col_d1.date_input("Data inicial", value=default_start)
d_fim = col_d2.date_input("Data final", value=default_end)
top_n = col_top.slider("Top N produtos", min_value=5, max_value=50, value=20, step=5)

if d_ini > d_fim:
    st.error("Data inicial deve ser anterior à data final.")
    st.stop()

d_ini_dt = datetime.combine(d_ini, datetime.min.time())
d_fim_dt = datetime.combine(d_fim, datetime.max.time())


@st.cache_data(ttl=300, show_spinner="Carregando KPIs…")
def _kpis(a: datetime, b: datetime) -> dict:
    return repository.fetch_kpis(a, b)


@st.cache_data(ttl=300, show_spinner="Top vendidos…")
def _top(a: datetime, b: datetime, n: int) -> pd.DataFrame:
    return repository.fetch_top_sellers(a, b, limit=n)


@st.cache_data(ttl=300, show_spinner="Detectando EANs duplicados…")
def _dups() -> pd.DataFrame:
    return repository.fetch_duplicate_eans()


@st.cache_data(ttl=300, show_spinner="Heatmap de vendas…")
def _heat(a: datetime, b: datetime) -> pd.DataFrame:
    return repository.fetch_sales_heatmap(a, b)


# --- KPIs ---------------------------------------------------------------------
kpis = _kpis(d_ini_dt, d_fim_dt)
k1, k2, k3, k4 = st.columns(4)
k1.metric("Receita", f"R$ {float(kpis['revenue'] or 0):,.2f}")
k2.metric("Itens vendidos", f"{float(kpis['qty'] or 0):,.2f}")
k3.metric("SKUs distintos", f"{int(kpis['distinct_skus'] or 0)}")
k4.metric("Tickets / NFs", f"{int(kpis['distinct_tickets'] or 0)}")

st.divider()

# --- Top sellers --------------------------------------------------------------
st.subheader("🥇 Produtos mais vendidos")
metric = st.radio("Ordenar por", ["Quantidade", "Receita"], horizontal=True, index=0)
top = _top(d_ini_dt, d_fim_dt, top_n)
if top.empty:
    st.info("Nenhuma venda no período.")
else:
    sort_col = "qty" if metric == "Quantidade" else "revenue"
    top = top.sort_values(sort_col, ascending=True)
    fig = px.bar(
        top,
        x=sort_col,
        y="desc_produto",
        orientation="h",
        text=sort_col,
        labels={"desc_produto": "Produto", "qty": "Quantidade", "revenue": "Receita (R$)"},
        height=max(360, 22 * len(top)),
    )
    fig.update_traces(texttemplate="%{text:,.2f}", textposition="outside")
    fig.update_layout(margin=dict(l=10, r=40, t=10, b=10), yaxis_title=None)
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("Tabela completa"):
        st.dataframe(top.sort_values(sort_col, ascending=False), use_container_width=True, hide_index=True)

st.divider()

# --- Duplicate EANs -----------------------------------------------------------
st.subheader("🧬 Produtos duplicados por EAN")
st.caption(
    "Mesmo código de barras (cod_produto) cadastrado em mais de um id_produto. Útil para revisão do cadastro."
)
dups = _dups()
if dups.empty:
    st.success("Nenhum EAN duplicado encontrado.")
else:
    st.dataframe(
        dups.rename(columns={
            "cod_produto": "EAN", "n_products": "Qtd. produtos", "ids": "IDs", "names": "Descrições",
        }),
        use_container_width=True,
        hide_index=True,
    )

st.divider()

# --- Heatmap ------------------------------------------------------------------
st.subheader("🕒 Heatmap dia da semana × hora (cores escuras = menor receita)")
heat = _heat(d_ini_dt, d_fim_dt)
if heat.empty:
    st.info("Sem dados de vendas no período.")
else:
    pivot = heat.pivot_table(index="weekday", columns="hour", values="revenue", aggfunc="sum").fillna(0.0)
    pivot = pivot.reindex(index=range(7), columns=range(24), fill_value=0.0)
    pivot.index = [WEEKDAYS_PT[i] for i in pivot.index]

    fig = px.imshow(
        pivot,
        labels=dict(x="Hora", y="Dia da semana", color="Receita (R$)"),
        x=[f"{h:02d}h" for h in pivot.columns],
        y=pivot.index,
        aspect="auto",
        color_continuous_scale="Viridis_r",  # reversed: dark = lowest
    )
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=420)
    st.plotly_chart(fig, use_container_width=True)

    flat = pivot.reset_index().melt(id_vars="index", var_name="hour", value_name="revenue")
    flat = flat.rename(columns={"index": "weekday"})
    flat = flat[flat["revenue"] > 0].sort_values("revenue").head(5)
    if not flat.empty:
        st.markdown("**5 horários com menor receita (apenas slots com venda > 0):**")
        flat["revenue"] = flat["revenue"].map(lambda v: f"R$ {v:,.2f}")
        st.dataframe(flat, use_container_width=True, hide_index=True)
