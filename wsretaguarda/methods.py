"""High-level wrappers around individual WsRetaguarda SOAP methods.

These accept Python args, build the request XML, call the transport, parse the
response, and return plain dicts ready for the DB layer.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st

from . import client, parsers


def _dominio() -> str:
    return st.secrets["wsretaguarda"]["dominio"]


def ret_produto(id_produto: int) -> dict[str, Any]:
    payload = (
        "<xmlIntegracao>"
        f"<Dominio>{_dominio()}</Dominio>"
        f"<IdProduto>{int(id_produto)}</IdProduto>"
        "</xmlIntegracao>"
    )
    xml = client.call("retProduto", payload)
    return parsers.parse_produto(xml)


def ret_produto_estoque(id_produto: int, dh_referencia: datetime | None = None) -> list[dict[str, Any]]:
    ref = (dh_referencia or datetime.utcnow()).strftime("%Y-%m-%d %H:%M:%S")
    payload = (
        "<xmlIntegracao>"
        f"<Dominio>{_dominio()}</Dominio>"
        f"<IdProduto>{int(id_produto)}</IdProduto>"
        "<CodProduto/>"
        f"<DhReferencia>{ref}</DhReferencia>"
        "</xmlIntegracao>"
    )
    xml = client.call("retProdutoEstoque", payload)
    return parsers.parse_estoque(xml, id_produto)


def ret_movimentacoes_completo(
    d_inicial: datetime,
    d_final: datetime,
    *,
    tp_mov: int = 20,
    ind_status: int = 2,
    x_nome: str = "",
    doc_emit: str = "",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Pull finalized PDV sales (TpMov=20 NFCe, IndStatus=2 Finalizado) in [d_inicial, d_final]."""
    payload = (
        "<xmlIntegracao>"
        f"<Dominio>{_dominio()}</Dominio>"
        f"<TpMov>{int(tp_mov)}</TpMov>"
        f"<IndStatus>{int(ind_status)}</IndStatus>"
        f"<xNome>{x_nome}</xNome>"
        f"<DocEmit>{doc_emit}</DocEmit>"
        f"<DInicial>{d_inicial.strftime('%Y-%m-%d %H:%M:%S')}</DInicial>"
        f"<DFinal>{d_final.strftime('%Y-%m-%d %H:%M:%S')}</DFinal>"
        "</xmlIntegracao>"
    )
    xml = client.call("retMovimentacoesCompleto", payload)
    return parsers.parse_movimentacoes(xml)
