"""SOAP transport for the WsRetaguarda Saurus web service.

Payload XML is gzipped + base64-encoded into the `xBytesParametros` element of a
SOAP 1.2 envelope; the server returns a gzipped + base64 blob in the
`<{method}Result>` field that decodes back to XML.
"""
from __future__ import annotations

import base64
import gzip
from dataclasses import dataclass
from datetime import date
from xml.etree import ElementTree as ET

import requests
import streamlit as st

NS_SAURUS = "http://saurus.net.br/"
NS_SOAP12 = "http://www.w3.org/2003/05/soap-envelope"


class WsRetaguardaError(RuntimeError):
    def __init__(self, method: str, ret_numero: int, ret_texto: str):
        super().__init__(f"{method} failed (xRetNumero={ret_numero}): {ret_texto}")
        self.method = method
        self.ret_numero = ret_numero
        self.ret_texto = ret_texto


@dataclass(frozen=True)
class WsConfig:
    endpoint: str
    dominio: str
    xsenha_override: str | None = None  # only for testing — leave empty in prod
    timeout: int = 60


def compute_xsenha(today: date | None = None) -> str:
    """Build the daily xSenha expected by WsRetaguarda.

    The plaintext is ``ophd02ophd02|@{day + month + (year - 2000)}|misam`` (the
    middle token is a numeric **sum**, not a concatenation). The whole string
    is then base64-encoded.

    Example: 14/05/2026 → 14 + 5 + 26 = 45 → ``ophd02ophd02|@45|misam`` →
    ``b3BoZDAyb3BoZDAyfEA0NXxtaXNhbQ==``.
    """
    today = today or date.today()
    n = today.day + today.month + (today.year - 2000)
    plain = f"ophd02ophd02|@{n}|misam"
    return base64.b64encode(plain.encode("utf-8")).decode("ascii")


def get_config() -> WsConfig:
    cfg = st.secrets["wsretaguarda"]
    sync_cfg = st.secrets.get("sync", {})
    return WsConfig(
        endpoint=cfg["endpoint"],
        dominio=cfg["dominio"],
        xsenha_override=cfg.get("xsenha") or None,
        timeout=int(sync_cfg.get("soap_timeout_seconds", 60)),
    )


def _encode(payload_xml: str) -> str:
    return base64.b64encode(gzip.compress(payload_xml.encode("utf-8"))).decode("ascii")


def _decode(b64_blob: str) -> str:
    return gzip.decompress(base64.b64decode(b64_blob)).decode("utf-8")


def _envelope(method: str, payload_b64: str, xsenha: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<soap12:Envelope xmlns:soap12="{NS_SOAP12}">'
        "<soap12:Body>"
        f'<{method} xmlns="{NS_SAURUS}">'
        f"<xBytesParametros>{payload_b64}</xBytesParametros>"
        f"<xSenha>{xsenha}</xSenha>"
        f"</{method}>"
        "</soap12:Body>"
        "</soap12:Envelope>"
    )


def call(method: str, payload_xml: str, *, config: WsConfig | None = None) -> str:
    """Call a SOAP method and return the decoded XML response payload."""
    cfg = config or get_config()
    xsenha = cfg.xsenha_override or compute_xsenha()
    body = _envelope(method, _encode(payload_xml), xsenha)
    headers = {
        "Content-Type": "application/soap+xml; charset=utf-8",
        "SOAPAction": f'"{NS_SAURUS}{method}"',
    }
    resp = requests.post(cfg.endpoint, data=body.encode("utf-8"), headers=headers, timeout=cfg.timeout)
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    ns = {"soap": NS_SOAP12, "s": NS_SAURUS}
    response_el = root.find(f"soap:Body/s:{method}Response", ns)
    if response_el is None:
        raise RuntimeError(f"{method}: missing {method}Response element in SOAP body")

    ret_numero = int(response_el.findtext("s:xRetNumero", default="-1", namespaces=ns))
    ret_texto = response_el.findtext("s:xRetTexto", default="", namespaces=ns) or ""
    result_b64 = response_el.findtext(f"s:{method}Result", default="", namespaces=ns) or ""

    if ret_numero != 0:
        raise WsRetaguardaError(method, ret_numero, ret_texto)

    if not result_b64:
        return ""
    return _decode(result_b64)
