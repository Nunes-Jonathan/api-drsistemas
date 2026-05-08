"""Print request payload + actual response for retMovimentacoesCompleto.

Usage: python scripts/dump_ret_movimentacoes.py [d_inicial] [d_final]
       dates as YYYY-MM-DD; defaults to last 30 days.
"""
from __future__ import annotations

import base64
import gzip
import sys
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET

import requests

from wsretaguarda import client


def main(d_inicial: datetime, d_final: datetime, *, tp_mov: int = 20, ind_status: int = 2) -> None:
    cfg = client.get_config()
    xsenha = cfg.xsenha_override or client.compute_xsenha()

    payload_xml = (
        "<xmlIntegracao>"
        f"<Dominio>{cfg.dominio}</Dominio>"
        f"<TpMov>{tp_mov}</TpMov>"
        f"<IndStatus>{ind_status}</IndStatus>"
        "<xNome></xNome>"
        "<DocEmit></DocEmit>"
        f"<DInicial>{d_inicial.strftime('%Y-%m-%d %H:%M:%S')}</DInicial>"
        f"<DFinal>{d_final.strftime('%Y-%m-%d %H:%M:%S')}</DFinal>"
        "</xmlIntegracao>"
    )
    payload_b64 = base64.b64encode(gzip.compress(payload_xml.encode("utf-8"))).decode("ascii")
    body = client._envelope("retMovimentacoesCompleto", payload_b64, xsenha)
    headers = {
        "Content-Type": "application/soap+xml; charset=utf-8",
        "SOAPAction": '"http://saurus.net.br/retMovimentacoesCompleto"',
    }

    print("ENDPOINT:", cfg.endpoint)
    print("SOAPAction:", headers["SOAPAction"])
    print()
    print("INNER xmlIntegracao (plaintext):")
    print(payload_xml)
    print()
    print("xBytesParametros (gzip + base64):")
    print(payload_b64)
    print()
    print("xSenha (today):")
    print(xsenha)
    print()

    resp = requests.post(cfg.endpoint, data=body.encode("utf-8"), headers=headers, timeout=cfg.timeout)
    print(f"HTTP {resp.status_code}")
    print()
    print("RAW RESPONSE:")
    print(resp.text)
    print()

    root = ET.fromstring(resp.content)
    ns = {"soap": client.NS_SOAP12, "s": client.NS_SAURUS}
    response_el = root.find("soap:Body/s:retMovimentacoesCompletoResponse", ns)
    ret_numero = response_el.findtext("s:xRetNumero", default="?", namespaces=ns)
    ret_texto = response_el.findtext("s:xRetTexto", default="", namespaces=ns)
    result_b64 = response_el.findtext("s:retMovimentacoesCompletoResult", default="", namespaces=ns) or ""

    print("DECODED:")
    print(f"xRetNumero: {ret_numero}")
    print(f"xRetTexto:  {ret_texto}")
    if result_b64:
        decoded = gzip.decompress(base64.b64decode(result_b64)).decode("utf-8")
        print(f"result length: {len(decoded)} chars")
        print(decoded[:4000])
    else:
        print("result: <empty>")


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        di = datetime.strptime(sys.argv[1], "%Y-%m-%d")
        df = datetime.strptime(sys.argv[2], "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    else:
        df = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)
        di = (df - timedelta(days=30)).replace(hour=0, minute=0, second=0)
    main(di, df)
