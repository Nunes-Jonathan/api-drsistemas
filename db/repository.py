"""Database repository: upserts and analytics queries."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

import pandas as pd
from sqlalchemy import text

from .connection import get_engine, schema_name


def _qual(table: str) -> str:
    return f'"{schema_name()}"."{table}"'


# ---------------------------------------------------------------------------
# Upserts (called from sync modules)
# ---------------------------------------------------------------------------

def upsert_product(parsed: dict[str, Any]) -> None:
    p = parsed["produto"]
    sql = text(
        f"""
        INSERT INTO {_qual('products')} (
            id_produto, origem, status, id_imposto, desc_produto, d_val,
            id_marca, desc_marca, id_medida, desc_medida, id_ncm, cod_ncm,
            id_categoria, desc_categoria, id_subcategoria, desc_subcategoria,
            inf_adic, tp_balanca, tp_item, v_compra, v_minimo, raw_xml,
            last_synced_at
        ) VALUES (
            :id_produto, :origem, :status, :id_imposto, :desc_produto, :d_val,
            :id_marca, :desc_marca, :id_medida, :desc_medida, :id_ncm, :cod_ncm,
            :id_categoria, :desc_categoria, :id_subcategoria, :desc_subcategoria,
            :inf_adic, :tp_balanca, :tp_item, :v_compra, :v_minimo, :raw_xml,
            now()
        )
        ON CONFLICT (id_produto) DO UPDATE SET
            origem            = EXCLUDED.origem,
            status            = EXCLUDED.status,
            id_imposto        = EXCLUDED.id_imposto,
            desc_produto      = EXCLUDED.desc_produto,
            d_val             = EXCLUDED.d_val,
            id_marca          = EXCLUDED.id_marca,
            desc_marca        = EXCLUDED.desc_marca,
            id_medida         = EXCLUDED.id_medida,
            desc_medida       = EXCLUDED.desc_medida,
            id_ncm            = EXCLUDED.id_ncm,
            cod_ncm           = EXCLUDED.cod_ncm,
            id_categoria      = EXCLUDED.id_categoria,
            desc_categoria    = EXCLUDED.desc_categoria,
            id_subcategoria   = EXCLUDED.id_subcategoria,
            desc_subcategoria = EXCLUDED.desc_subcategoria,
            inf_adic          = EXCLUDED.inf_adic,
            tp_balanca        = EXCLUDED.tp_balanca,
            tp_item           = EXCLUDED.tp_item,
            v_compra          = EXCLUDED.v_compra,
            v_minimo          = EXCLUDED.v_minimo,
            raw_xml           = EXCLUDED.raw_xml,
            last_synced_at    = now();
        """
    )
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(sql, p)
        # Replace child rows (codes/prices/lojas) for idempotent re-sync.
        conn.execute(
            text(f"DELETE FROM {_qual('product_codes')} WHERE id_produto = :id"),
            {"id": p["id_produto"]},
        )
        if parsed["codigos"]:
            conn.execute(
                text(
                    f"""
                    INSERT INTO {_qual('product_codes')}
                        (id_produto, id_codigo, cod_produto, id_tp_codigo, ind_status)
                    VALUES (:id_produto, :id_codigo, :cod_produto, :id_tp_codigo, :ind_status)
                    """
                ),
                [c for c in parsed["codigos"] if c.get("id_codigo") is not None],
            )

        conn.execute(
            text(f"DELETE FROM {_qual('product_prices')} WHERE id_produto = :id"),
            {"id": p["id_produto"]},
        )
        if parsed["precos"]:
            conn.execute(
                text(
                    f"""
                    INSERT INTO {_qual('product_prices')}
                        (id_produto, id_preco, id_loja, id_tab_preco, tp_preco, status,
                         v_compra, v_custo, v_preco)
                    VALUES (:id_produto, :id_preco, :id_loja, :id_tab_preco, :tp_preco, :status,
                            :v_compra, :v_custo, :v_preco)
                    """
                ),
                [p for p in parsed["precos"] if p.get("id_preco") is not None],
            )

        conn.execute(
            text(f"DELETE FROM {_qual('product_lojas')} WHERE id_produto = :id"),
            {"id": p["id_produto"]},
        )
        if parsed["lojas"]:
            conn.execute(
                text(
                    f"""
                    INSERT INTO {_qual('product_lojas')}
                        (id_produto, id_loja, id_produto_loja, desc_local, qtd_minimo, v_minimo)
                    VALUES (:id_produto, :id_loja, :id_produto_loja, :desc_local, :qtd_minimo, :v_minimo)
                    """
                ),
                [l for l in parsed["lojas"] if l.get("id_loja") is not None],
            )


def upsert_stock(rows: Iterable[dict[str, Any]]) -> None:
    rows = list(rows)
    if not rows:
        return
    sql = text(
        f"""
        INSERT INTO {_qual('product_stock')}
            (id_produto, id_loja, fant, q_saldo, dh_saldo, last_synced_at)
        VALUES (:id_produto, :id_loja, :fant, :q_saldo, :dh_saldo, now())
        ON CONFLICT (id_produto, id_loja) DO UPDATE SET
            fant           = EXCLUDED.fant,
            q_saldo        = EXCLUDED.q_saldo,
            dh_saldo       = EXCLUDED.dh_saldo,
            last_synced_at = now();
        """
    )
    with get_engine().begin() as conn:
        conn.execute(sql, rows)


def upsert_movements(movements: list[dict[str, Any]], items: list[dict[str, Any]]) -> None:
    if not movements:
        return
    mov_sql = text(
        f"""
        INSERT INTO {_qual('sales_movements')} (
            id_mov, dh_emi, tp_mov, ind_status, tp_status, desc_status, desc_tp,
            tp_amb, emit_id_loja, emit_doc, dest_id_cadastro, dest_doc, dest_x_nome,
            id_operador, id_caixa, num_caixa, n_nf, tot_v_nf, tot_q_com, tot_qtd_itens,
            tot_v_prod, tot_v_desc, tot_v_outro
        ) VALUES (
            :id_mov, :dh_emi, :tp_mov, :ind_status, :tp_status, :desc_status, :desc_tp,
            :tp_amb, :emit_id_loja, :emit_doc, :dest_id_cadastro, :dest_doc, :dest_x_nome,
            :id_operador, :id_caixa, :num_caixa, :n_nf, :tot_v_nf, :tot_q_com, :tot_qtd_itens,
            :tot_v_prod, :tot_v_desc, :tot_v_outro
        )
        ON CONFLICT (id_mov) DO UPDATE SET
            dh_emi           = EXCLUDED.dh_emi,
            ind_status       = EXCLUDED.ind_status,
            tp_status        = EXCLUDED.tp_status,
            desc_status      = EXCLUDED.desc_status,
            tot_v_nf         = EXCLUDED.tot_v_nf,
            tot_q_com        = EXCLUDED.tot_q_com,
            tot_qtd_itens    = EXCLUDED.tot_qtd_itens,
            tot_v_prod       = EXCLUDED.tot_v_prod,
            tot_v_desc       = EXCLUDED.tot_v_desc,
            tot_v_outro      = EXCLUDED.tot_v_outro;
        """
    )
    with get_engine().begin() as conn:
        conn.execute(mov_sql, movements)

        mov_ids = [m["id_mov"] for m in movements]
        if mov_ids:
            conn.execute(
                text(f"DELETE FROM {_qual('sales_items')} WHERE id_mov = ANY(:ids)"),
                {"ids": mov_ids},
            )
        if items:
            conn.execute(
                text(
                    f"""
                    INSERT INTO {_qual('sales_items')} (
                        id_mov, n_item, id_produto, id_prod, c_prod, x_prod, u_com,
                        q_com, v_un_com, v_prod, v_desc, v_outro,
                        id_vendedor, login_vendedor, inf_ad_prod
                    ) VALUES (
                        :id_mov, :n_item, :id_produto, :id_prod, :c_prod, :x_prod, :u_com,
                        :q_com, :v_un_com, :v_prod, :v_desc, :v_outro,
                        :id_vendedor, :login_vendedor, :inf_ad_prod
                    )
                    """
                ),
                [it for it in items if it.get("n_item") is not None],
            )


def update_sync_log(resource: str, status: str, message: str = "", cursor: str | None = None) -> None:
    with get_engine().begin() as conn:
        conn.execute(
            text(
                f"""
                INSERT INTO {_qual('sync_log')} (resource, last_run, status, message, last_cursor)
                VALUES (:resource, now(), :status, :message, :cursor)
                ON CONFLICT (resource) DO UPDATE SET
                    last_run    = EXCLUDED.last_run,
                    status      = EXCLUDED.status,
                    message     = EXCLUDED.message,
                    last_cursor = EXCLUDED.last_cursor;
                """
            ),
            {"resource": resource, "status": status, "message": message, "cursor": cursor},
        )


def get_sync_log() -> pd.DataFrame:
    with get_engine().connect() as conn:
        return pd.read_sql(
            text(f"SELECT resource, last_run, status, message, last_cursor FROM {_qual('sync_log')} ORDER BY resource"),
            conn,
        )


# ---------------------------------------------------------------------------
# Read queries (powering the Streamlit pages)
# ---------------------------------------------------------------------------

def fetch_products() -> pd.DataFrame:
    sql = text(
        f"""
        SELECT
            p.id_produto,
            p.desc_produto,
            p.desc_categoria,
            p.desc_subcategoria,
            p.desc_marca,
            p.desc_medida,
            p.status,
            p.v_compra,
            p.v_minimo,
            (SELECT MIN(v_preco) FROM {_qual('product_prices')} pr WHERE pr.id_produto = p.id_produto) AS v_preco_min,
            (SELECT MAX(v_preco) FROM {_qual('product_prices')} pr WHERE pr.id_produto = p.id_produto) AS v_preco_max,
            (SELECT STRING_AGG(DISTINCT cod_produto, ', ')
                FROM {_qual('product_codes')} pc
                WHERE pc.id_produto = p.id_produto AND pc.cod_produto IS NOT NULL) AS codigos,
            (SELECT COALESCE(SUM(q_saldo), 0)
                FROM {_qual('product_stock')} ps WHERE ps.id_produto = p.id_produto) AS estoque_total,
            p.last_synced_at
        FROM {_qual('products')} p
        ORDER BY p.id_produto
        """
    )
    with get_engine().connect() as conn:
        return pd.read_sql(sql, conn)


def fetch_product_detail(id_produto: int) -> dict[str, pd.DataFrame]:
    with get_engine().connect() as conn:
        info = pd.read_sql(
            text(f"SELECT * FROM {_qual('products')} WHERE id_produto = :id"),
            conn, params={"id": id_produto},
        )
        codes = pd.read_sql(
            text(f"SELECT * FROM {_qual('product_codes')} WHERE id_produto = :id"),
            conn, params={"id": id_produto},
        )
        prices = pd.read_sql(
            text(f"SELECT * FROM {_qual('product_prices')} WHERE id_produto = :id"),
            conn, params={"id": id_produto},
        )
        stock = pd.read_sql(
            text(f"SELECT * FROM {_qual('product_stock')} WHERE id_produto = :id"),
            conn, params={"id": id_produto},
        )
        recent_sales = pd.read_sql(
            text(
                f"""
                SELECT m.dh_emi, m.n_nf, i.q_com, i.v_un_com, i.v_prod, i.login_vendedor
                FROM {_qual('sales_items')} i
                JOIN {_qual('sales_movements')} m USING (id_mov)
                WHERE i.id_produto = :id
                ORDER BY m.dh_emi DESC
                LIMIT 50
                """
            ),
            conn, params={"id": id_produto},
        )
    return {"info": info, "codes": codes, "prices": prices, "stock": stock, "recent_sales": recent_sales}


def fetch_top_sellers(d_inicial: datetime, d_final: datetime, limit: int = 20) -> pd.DataFrame:
    sql = text(
        f"""
        SELECT i.id_produto,
               COALESCE(p.desc_produto, MAX(i.x_prod)) AS desc_produto,
               SUM(i.q_com)  AS qty,
               SUM(i.v_prod) AS revenue
        FROM {_qual('sales_items')} i
        JOIN {_qual('sales_movements')} m USING (id_mov)
        LEFT JOIN {_qual('products')} p ON p.id_produto = i.id_produto
        WHERE m.dh_emi BETWEEN :d_ini AND :d_fim
        GROUP BY i.id_produto, p.desc_produto
        ORDER BY qty DESC
        LIMIT :limit
        """
    )
    with get_engine().connect() as conn:
        return pd.read_sql(sql, conn, params={"d_ini": d_inicial, "d_fim": d_final, "limit": limit})


def fetch_duplicate_eans() -> pd.DataFrame:
    """Group product_codes by cod_produto where the same code maps to >1 product."""
    sql = text(
        f"""
        SELECT pc.cod_produto,
               COUNT(*)              AS n_products,
               ARRAY_AGG(pc.id_produto ORDER BY pc.id_produto) AS ids,
               ARRAY_AGG(p.desc_produto ORDER BY pc.id_produto) AS names
        FROM {_qual('product_codes')} pc
        LEFT JOIN {_qual('products')} p ON p.id_produto = pc.id_produto
        WHERE pc.cod_produto IS NOT NULL AND pc.cod_produto <> ''
        GROUP BY pc.cod_produto
        HAVING COUNT(*) > 1
        ORDER BY n_products DESC, pc.cod_produto
        """
    )
    with get_engine().connect() as conn:
        df = pd.read_sql(sql, conn)
    if not df.empty:
        df["ids"] = df["ids"].apply(lambda xs: ", ".join(str(x) for x in xs))
        df["names"] = df["names"].apply(
            lambda xs: " | ".join(str(x) if x is not None else "(sem cadastro)" for x in xs)
        )
    return df


def fetch_sales_heatmap(d_inicial: datetime, d_final: datetime) -> pd.DataFrame:
    """Revenue per (weekday, hour). Weekday: 0=Sunday … 6=Saturday (Postgres DOW)."""
    sql = text(
        f"""
        SELECT EXTRACT(DOW  FROM dh_emi)::INT AS weekday,
               EXTRACT(HOUR FROM dh_emi)::INT AS hour,
               SUM(tot_v_nf) AS revenue,
               COUNT(*)      AS n_movs
        FROM {_qual('sales_movements')}
        WHERE dh_emi BETWEEN :d_ini AND :d_fim
        GROUP BY 1, 2
        ORDER BY 1, 2
        """
    )
    with get_engine().connect() as conn:
        return pd.read_sql(sql, conn, params={"d_ini": d_inicial, "d_fim": d_final})


def fetch_kpis(d_inicial: datetime, d_final: datetime) -> dict[str, float]:
    sql = text(
        f"""
        SELECT
            COALESCE(SUM(m.tot_v_nf), 0)            AS revenue,
            COALESCE(SUM(i.q_com), 0)               AS qty,
            COUNT(DISTINCT i.id_produto)            AS distinct_skus,
            COUNT(DISTINCT m.id_mov)                AS distinct_tickets
        FROM {_qual('sales_movements')} m
        LEFT JOIN {_qual('sales_items')} i USING (id_mov)
        WHERE m.dh_emi BETWEEN :d_ini AND :d_fim
        """
    )
    with get_engine().connect() as conn:
        row = conn.execute(sql, {"d_ini": d_inicial, "d_fim": d_final}).mappings().first()
    return dict(row) if row else {"revenue": 0, "qty": 0, "distinct_skus": 0, "distinct_tickets": 0}


def fetch_max_dh_emi() -> datetime | None:
    with get_engine().connect() as conn:
        row = conn.execute(text(f"SELECT MAX(dh_emi) FROM {_qual('sales_movements')}")).first()
    return row[0] if row and row[0] else None


def fetch_unsynced_product_ids() -> list[int]:
    sql = text(
        f"""
        SELECT DISTINCT i.id_produto
        FROM {_qual('sales_items')} i
        LEFT JOIN {_qual('products')} p ON p.id_produto = i.id_produto
        WHERE i.id_produto IS NOT NULL AND p.id_produto IS NULL
        ORDER BY i.id_produto
        """
    )
    with get_engine().connect() as conn:
        return [r[0] for r in conn.execute(sql)]
