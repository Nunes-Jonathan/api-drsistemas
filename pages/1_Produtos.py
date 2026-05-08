"""Detailed product list with filtering, drill-in, and Excel/CSV export."""
from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from db import repository

st.set_page_config(page_title="Produtos — DR Sistemas", page_icon="📋", layout="wide")
st.title("📋 Produtos")


@st.cache_data(ttl=300, show_spinner="Carregando produtos…")
def load_products() -> pd.DataFrame:
    return repository.fetch_products()


df = load_products()

if df.empty:
    st.info("Nenhum produto sincronizado ainda. Volte à página inicial e rode o **Sweep de produtos**.")
    st.stop()

# --- Filters ------------------------------------------------------------------
with st.container():
    f1, f2, f3, f4 = st.columns([3, 2, 2, 1])
    search = f1.text_input("Buscar (descrição ou EAN)", placeholder="ex.: leite, 7891000…")
    categorias = sorted(df["desc_categoria"].dropna().unique().tolist())
    marcas = sorted(df["desc_marca"].dropna().unique().tolist())
    sel_cat = f2.multiselect("Categoria", categorias)
    sel_mar = f3.multiselect("Marca", marcas)
    only_active = f4.checkbox("Apenas ativos", value=True)

filtered = df.copy()
if search:
    s = search.strip().lower()
    mask_desc = filtered["desc_produto"].fillna("").str.lower().str.contains(s, na=False)
    mask_code = filtered["codigos"].fillna("").str.lower().str.contains(s, na=False)
    filtered = filtered[mask_desc | mask_code]
if sel_cat:
    filtered = filtered[filtered["desc_categoria"].isin(sel_cat)]
if sel_mar:
    filtered = filtered[filtered["desc_marca"].isin(sel_mar)]
if only_active:
    filtered = filtered[filtered["status"].fillna(0) == 0]

st.caption(f"Exibindo **{len(filtered)}** de {len(df)} produtos.")

# --- Table --------------------------------------------------------------------
display_cols = [
    "id_produto", "desc_produto", "codigos", "desc_categoria", "desc_marca",
    "desc_medida", "v_compra", "v_preco_min", "v_preco_max", "estoque_total", "last_synced_at",
]
st.dataframe(
    filtered[display_cols],
    use_container_width=True,
    hide_index=True,
    column_config={
        "id_produto":   st.column_config.NumberColumn("ID", width="small"),
        "desc_produto": st.column_config.TextColumn("Descrição"),
        "codigos":      st.column_config.TextColumn("Códigos / EAN"),
        "desc_categoria": "Categoria",
        "desc_marca":     "Marca",
        "desc_medida":    "UM",
        "v_compra":     st.column_config.NumberColumn("Compra (R$)", format="%.2f"),
        "v_preco_min":  st.column_config.NumberColumn("Preço mín. (R$)", format="%.2f"),
        "v_preco_max":  st.column_config.NumberColumn("Preço máx. (R$)", format="%.2f"),
        "estoque_total": st.column_config.NumberColumn("Estoque", format="%.2f"),
        "last_synced_at": st.column_config.DatetimeColumn("Sincronizado em"),
    },
)

# --- Exports ------------------------------------------------------------------
st.subheader("Exportar visualização atual")
col_csv, col_xlsx, _ = st.columns([1, 1, 4])

csv_bytes = filtered[display_cols].to_csv(index=False).encode("utf-8-sig")
col_csv.download_button(
    "⬇️ CSV",
    data=csv_bytes,
    file_name=f"produtos_{len(filtered)}.csv",
    mime="text/csv",
    use_container_width=True,
)

excel_df = filtered[display_cols].copy()
for col in excel_df.select_dtypes(include=["datetimetz"]).columns:
    excel_df[col] = excel_df[col].dt.tz_localize(None)

excel_buf = BytesIO()
with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
    excel_df.to_excel(writer, index=False, sheet_name="Produtos")
col_xlsx.download_button(
    "⬇️ Excel",
    data=excel_buf.getvalue(),
    file_name=f"produtos_{len(filtered)}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)

# --- Drill-in -----------------------------------------------------------------
st.subheader("Detalhes do produto")
ids = filtered["id_produto"].tolist()
if ids:
    selected = st.selectbox(
        "Selecione um produto para ver preços, códigos, estoque e últimas vendas",
        options=ids,
        format_func=lambda i: f"#{i} — {filtered.loc[filtered['id_produto'] == i, 'desc_produto'].iloc[0]}",
    )
    if selected:
        detail = repository.fetch_product_detail(int(selected))
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Cadastro**")
            st.dataframe(detail["info"].T, use_container_width=True)
            st.markdown("**Códigos / EAN**")
            st.dataframe(detail["codes"], use_container_width=True, hide_index=True)
        with c2:
            st.markdown("**Preços por loja / tabela**")
            st.dataframe(detail["prices"], use_container_width=True, hide_index=True)
            st.markdown("**Estoque por loja**")
            st.dataframe(detail["stock"], use_container_width=True, hide_index=True)

        st.markdown("**Últimas 50 vendas**")
        st.dataframe(detail["recent_sales"], use_container_width=True, hide_index=True)
