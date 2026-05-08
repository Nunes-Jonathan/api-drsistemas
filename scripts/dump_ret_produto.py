"""Capture raw request + response of retProduto for the API admin.

Usage: python scripts/dump_ret_produto.py <id_produto>
"""
from __future__ import annotations

import base64
import gzip
import sys
from xml.etree import ElementTree as ET

import requests
import streamlit as st

from wsretaguarda import client


def main(id_produto: int) -> None:
    cfg = client.get_config()
    xsenha = cfg.xsenha_override or client.compute_xsenha()

    payload_xml = (
        "<xmlIntegracao>"
        f"<Dominio>{cfg.dominio}</Dominio>"
        f"<IdProduto>{id_produto}</IdProduto>"
        "</xmlIntegracao>"
    )
    payload_b64 = base64.b64encode(gzip.compress(payload_xml.encode("utf-8"))).decode("ascii")
    body = client._envelope("retProduto", payload_b64, xsenha)
    headers = {
        "Content-Type": "application/soap+xml; charset=utf-8",
        "SOAPAction": '"http://saurus.net.br/retProduto"',
    }

    print("=" * 80)
    print("ENDPOINT")
    print("=" * 80)
    print(f"POST {cfg.endpoint}")
    print()
    print("=" * 80)
    print("REQUEST HEADERS")
    print("=" * 80)
    for k, v in headers.items():
        print(f"{k}: {v}")
    print()
    print("=" * 80)
    print("REQUEST BODY (SOAP envelope)")
    print("=" * 80)
    print(body)
    print()
    print("=" * 80)
    print("REQUEST PAYLOAD (xmlIntegracao, plaintext before gzip+base64)")
    print("=" * 80)
    print(payload_xml)
    print()

    resp = requests.post(cfg.endpoint, data=body.encode("utf-8"), headers=headers, timeout=cfg.timeout)
    print("=" * 80)
    print(f"HTTP {resp.status_code}")
    print("=" * 80)
    for k, v in resp.headers.items():
        print(f"{k}: {v}")
    print()
    print("=" * 80)
    print("RESPONSE BODY (raw SOAP envelope)")
    print("=" * 80)
    print(resp.text)
    print()

    # Decode the inner result blob
    root = ET.fromstring(resp.content)
    ns = {"soap": client.NS_SOAP12, "s": client.NS_SAURUS}
    response_el = root.find("soap:Body/s:retProdutoResponse", ns)
    ret_numero = response_el.findtext("s:xRetNumero", default="?", namespaces=ns)
    ret_texto = response_el.findtext("s:xRetTexto", default="", namespaces=ns)
    result_b64 = response_el.findtext("s:retProdutoResult", default="", namespaces=ns) or ""

    print("=" * 80)
    print("RESPONSE — DECODED PAYLOAD")
    print("=" * 80)
    print(f"xRetNumero: {ret_numero}")
    print(f"xRetTexto:  {ret_texto}")
    print()
    if result_b64:
        decoded = gzip.decompress(base64.b64decode(result_b64)).decode("utf-8")
        print("retProdutoResult (gunzipped + b64-decoded):")
        print(decoded)
    else:
        print("retProdutoResult: <empty>")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python scripts/dump_ret_produto.py <id_produto>", file=sys.stderr)
        sys.exit(2)
    main(int(sys.argv[1]))
