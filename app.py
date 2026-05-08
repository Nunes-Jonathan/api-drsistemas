"""WsRetaguarda dashboard — landing page with sync controls."""
from __future__ import annotations

from datetime import datetime, timedelta

import streamlit as st

from db import repository
from db.connection import init_db
from sync import products as sync_products
from sync import sales as sync_sales

st.set_page_config(page_title="DR Sistemas — Retaguarda", page_icon="📦", layout="wide")


@st.cache_resource
def _bootstrap() -> None:
    init_db()


_bootstrap()

st.title("📦 DR Sistemas — Retaguarda")
st.caption(
    "Sincronize produtos e vendas do WsRetaguarda para o Postgres local e explore os dados nas páginas "
    "**Produtos** e **Dashboard**."
)

sync_log = repository.get_sync_log()
if not sync_log.empty:
    st.subheader("Última sincronização")
    st.dataframe(sync_log, use_container_width=True, hide_index=True)
else:
    st.info("Ainda não houve sincronização. Use a barra lateral para começar.")

# --- Sidebar: sync controls ---------------------------------------------------
sync_cfg = st.secrets.get("sync", {})
default_max_id = int(sync_cfg.get("max_id_produto", 10000))
default_lookback = int(sync_cfg.get("default_sales_lookback_days", 90))
default_workers = int(sync_cfg.get("soap_max_workers", 4))

with st.sidebar:
    st.header("Sincronização")

    with st.expander("Sweep de produtos (1..N)", expanded=False):
        col1, col2 = st.columns(2)
        start_id = col1.number_input("ID inicial", min_value=1, value=1, step=1)
        end_id = col2.number_input("ID final", min_value=1, value=default_max_id, step=100)
        workers = st.slider("Threads simultâneas", 1, 16, default_workers)
        if st.button("▶️ Sincronizar produtos", type="primary", key="sweep"):
            with st.status("Sincronizando produtos…", expanded=True) as status:
                progress = st.progress(0.0)
                log = st.empty()

                def on_progress(done: int, total: int, msg: str) -> None:
                    progress.progress(done / max(total, 1))
                    log.text(msg)

                counters = sync_products.sweep(
                    int(start_id),
                    int(end_id),
                    max_workers=int(workers),
                    on_progress=on_progress,
                )
                status.update(
                    label=f"OK: {counters['ok']} | sem cadastro: {counters['missing']} | erros: {counters['errors']}",
                    state="complete",
                )

    with st.expander("Vendas (incremental)", expanded=True):
        last_seen = repository.fetch_max_dh_emi()
        if last_seen:
            st.caption(f"Última venda no banco: **{last_seen:%Y-%m-%d %H:%M}**")
        col1, col2 = st.columns(2)
        d_ini = col1.date_input("Data inicial", value=datetime.now().date() - timedelta(days=default_lookback))
        d_fim = col2.date_input("Data final", value=datetime.now().date())
        if st.button("▶️ Sincronizar vendas", type="primary", key="sales"):
            with st.status("Buscando vendas…", expanded=True) as status:
                log = st.empty()

                def on_progress(msg: str) -> None:
                    log.text(msg)

                counters = sync_sales.pull(
                    datetime.combine(d_ini, datetime.min.time()),
                    datetime.combine(d_fim, datetime.max.time()),
                    on_progress=on_progress,
                )
                status.update(
                    label=f"Movimentações: {counters['movements']} | itens: {counters['items']}",
                    state="complete",
                )

    with st.expander("Produtos vistos em vendas mas não cadastrados"):
        st.caption("Busca `id_produto` que apareceram em vendas e ainda não estão na tabela de produtos.")
        if st.button("▶️ Backfill", key="backfill"):
            with st.status("Buscando produtos faltantes…", expanded=True) as status:
                progress = st.progress(0.0)
                log = st.empty()

                def on_progress(done: int, total: int, msg: str) -> None:
                    progress.progress(done / max(total, 1))
                    log.text(msg)

                counters = sync_products.refresh_from_sales(
                    max_workers=default_workers, on_progress=on_progress
                )
                status.update(
                    label=f"OK: {counters['ok']} | sem cadastro: {counters['missing']} | erros: {counters['errors']}",
                    state="complete",
                )

    st.divider()
    st.caption("Páginas")
    st.page_link("pages/1_Produtos.py", label="📋 Produtos (lista detalhada + export)")
    st.page_link("pages/2_Dashboard.py", label="📊 Dashboard (top, duplicados, heatmap)")
