"""Parse WsRetaguarda XML payloads into plain dicts.

The service returns attribute-heavy XML; helpers here flatten that into shapes
that map cleanly onto the database tables in ``db/schema.sql``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from xml.etree import ElementTree as ET


def _attrs(el: ET.Element | None) -> dict[str, str]:
    return dict(el.attrib) if el is not None else {}


def _to_int(value: Any) -> int | None:
    if value in (None, "", "None"):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _to_decimal(value: Any) -> float | None:
    if value in (None, "", "None"):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _to_dt(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("T", " ").split(".")[0]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def parse_produto(xml: str) -> dict[str, Any] | None:
    """Parse a ``<Produto>`` payload returned by ``retProduto``.

    Returns a dict with ``produto`` (master), ``codigos``, ``precos``, ``lojas``,
    or ``None`` if the response carried no recognizable product data (e.g.
    ``<Produto />`` for an unknown ID).

    Some dominios only return ``<ProdutoCodigos>`` with no ``<ProdutoDados>``;
    in that case ``id_produto`` is harvested from the child elements and the
    other fields stay ``None``.
    """
    root = ET.fromstring(xml)
    dados = _attrs(root.find("ProdutoDados"))

    id_produto = _to_int(dados.get("pro_idProduto"))
    if id_produto is None:
        for child_xpath in ("ProdutoCodigos/produtoCodigo", "ProdutoPrecos/produtoPreco", "ProdutoLojas/produtoLoja"):
            child = root.find(child_xpath)
            if child is not None:
                id_produto = _to_int(child.attrib.get("pro_idProduto"))
                if id_produto is not None:
                    break
    if id_produto is None:
        return None

    produto = {
        "id_produto": id_produto,
        "origem": _to_int(dados.get("pro_origem")),
        "status": _to_int(dados.get("pro_status")),
        "id_imposto": _to_int(dados.get("pro_idImposto")),
        "desc_produto": dados.get("pro_descProduto"),
        "d_val": _to_int(dados.get("pro_dVal")),
        "id_marca": _to_int(dados.get("pro_idMarca")),
        "desc_marca": dados.get("pro_descMarca"),
        "id_medida": _to_int(dados.get("pro_idMedida")),
        "desc_medida": dados.get("pro_descMedida") or dados.get("pro_medida"),
        "id_ncm": _to_int(dados.get("pro_idNcm")),
        "cod_ncm": dados.get("pro_codNcm"),
        "id_categoria": _to_int(dados.get("pro_idCategoria")),
        "desc_categoria": dados.get("pro_descCategoria"),
        "id_subcategoria": _to_int(dados.get("pro_idSubCategoria")),
        "desc_subcategoria": dados.get("pro_descSubCategoria"),
        "inf_adic": dados.get("pro_infAdic"),
        "tp_balanca": _to_int(dados.get("pro_tpBalanca")),
        "tp_item": _to_int(dados.get("pro_tpItem")),
        "v_compra": _to_decimal(dados.get("pro_vCompra")),
        "v_minimo": _to_decimal(dados.get("pro_vMinimo")),
        "raw_xml": xml,
    }

    codigos = []
    for el in root.findall("ProdutoCodigos/produtoCodigo"):
        a = el.attrib
        codigos.append(
            {
                "id_produto": _to_int(a.get("pro_idProduto")) or id_produto,
                "id_codigo": _to_int(a.get("pro_idCodigo")),
                "cod_produto": a.get("pro_codProduto"),
                "id_tp_codigo": _to_int(a.get("pro_idTpCodigo")),
                "ind_status": _to_int(a.get("pro_indStatus")),
            }
        )

    precos = []
    for el in root.findall("ProdutoPrecos/produtoPreco"):
        a = el.attrib
        precos.append(
            {
                "id_produto": _to_int(a.get("pro_idProduto")) or id_produto,
                "id_preco": _to_int(a.get("pro_idPreco")),
                "id_loja": _to_int(a.get("pro_idLoja")),
                "id_tab_preco": _to_int(a.get("pro_idTabPreco")),
                "tp_preco": _to_int(a.get("pro_tpPreco")),
                "status": _to_int(a.get("pro_status")),
                "v_compra": _to_decimal(a.get("pro_vCompra")),
                "v_custo": _to_decimal(a.get("pro_vCusto")),
                "v_preco": _to_decimal(a.get("pro_vPreco")),
            }
        )

    lojas = []
    for el in root.findall("ProdutoLojas/produtoLoja"):
        a = el.attrib
        lojas.append(
            {
                "id_produto": _to_int(a.get("pro_idProduto")) or id_produto,
                "id_loja": _to_int(a.get("pro_idLoja")),
                "id_produto_loja": _to_int(a.get("pro_idProdutoLoja")),
                "desc_local": a.get("pro_descLocal"),
                "qtd_minimo": _to_decimal(a.get("pro_qtdMinimo")),
                "v_minimo": _to_decimal(a.get("pro_vMinimo")),
            }
        )

    return {"produto": produto, "codigos": codigos, "precos": precos, "lojas": lojas}


def parse_estoque(xml: str, id_produto: int) -> list[dict[str, Any]]:
    root = ET.fromstring(xml)
    rows = []
    for el in root.findall("EstoqueLoja"):
        a = el.attrib
        rows.append(
            {
                "id_produto": id_produto,
                "id_loja": _to_int(a.get("idLoja")),
                "fant": a.get("fant"),
                "q_saldo": _to_decimal(a.get("qSaldo")),
                "dh_saldo": _to_dt(a.get("dhSaldo")),
            }
        )
    return rows


def parse_movimentacoes(xml: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse ``retMovimentacoesCompleto`` payload.

    Returns ``(movements, items)`` ready to upsert into ``sales_movements`` and
    ``sales_items``. An empty XML payload (no movements in window) yields
    ``([], [])``.
    """
    if not xml or not xml.strip():
        return [], []
    root = ET.fromstring(xml)
    movements: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []

    for mov in root.findall("MovDados"):
        a = mov.attrib
        id_mov = a.get("mov_idMov")
        if not id_mov:
            continue
        movements.append(
            {
                "id_mov": id_mov,
                "dh_emi": _to_dt(a.get("mov_dhEmi")),
                "tp_mov": _to_int(a.get("mov_tpMov")),
                "ind_status": _to_int(a.get("mov_indStatus")),
                "tp_status": _to_int(a.get("mov_tpStatus")),
                "desc_status": a.get("mov_descStatus"),
                "desc_tp": a.get("mov_descTp"),
                "tp_amb": _to_int(a.get("mov_tpAmb")),
                "emit_id_loja": _to_int(a.get("emit_idLoja")),
                "emit_doc": a.get("emit_doc"),
                "dest_id_cadastro": _to_int(a.get("dest_idCadastro")),
                "dest_doc": a.get("dest_doc"),
                "dest_x_nome": a.get("dest_xNome"),
                "id_operador": _to_int(a.get("mov_idOperador")),
                "id_caixa": _to_int(a.get("mov_idCaixa")),
                "num_caixa": _to_int(a.get("mov_numCaixa")),
                "n_nf": _to_int(a.get("mov_nNf")),
                "tot_v_nf": _to_decimal(a.get("tot_vNF")),
                "tot_q_com": _to_decimal(a.get("tot_qCom")),
                "tot_qtd_itens": _to_int(a.get("tot_qtdItens")),
                "tot_v_prod": _to_decimal(a.get("tot_vProd")),
                "tot_v_desc": _to_decimal(a.get("tot_vDesc")),
                "tot_v_outro": _to_decimal(a.get("tot_vOutro")),
            }
        )

        for prod in mov.findall("MovProds/MovProd") or mov.findall("Produtos/MovProd"):
            pa = prod.attrib
            items.append(
                {
                    "id_mov": id_mov,
                    "n_item": _to_int(pa.get("prod_nItem")),
                    "id_produto": _to_int(pa.get("prod_idProduto")),
                    "id_prod": pa.get("prod_idProd"),
                    "c_prod": pa.get("prod_cProd"),
                    "x_prod": pa.get("prod_xProd"),
                    "u_com": pa.get("prod_uCom"),
                    "q_com": _to_decimal(pa.get("prod_qCom")),
                    "v_un_com": _to_decimal(pa.get("prod_vUnCom")),
                    "v_prod": _to_decimal(pa.get("prod_vProd")),
                    "v_desc": _to_decimal(pa.get("prod_vDesc")),
                    "v_outro": _to_decimal(pa.get("prod_vOutro")),
                    "id_vendedor": _to_int(pa.get("prod_idVendedor")),
                    "login_vendedor": pa.get("prod_loginVendedor"),
                    "inf_ad_prod": pa.get("prod_infAdProd"),
                }
            )

    return movements, items
