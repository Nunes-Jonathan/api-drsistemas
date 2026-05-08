"""SOAP smoke test for WsRetaguarda — runs OUTSIDE of Streamlit.

It (1) verifies the daily xSenha formula matches the documented example,
(2) builds a SOAP envelope for retProduto, (3) POSTs it to the live endpoint
with the configured Dominio, and (4) prints the parsed response (or a clean
error if the server rejects the request).
"""
from __future__ import annotations

import sys
import tomllib
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Import the transport without touching streamlit.secrets.
from wsretaguarda import client, parsers  # noqa: E402

SECRETS = ROOT / ".streamlit" / "secrets.toml"


def load_secrets() -> dict:
    if not SECRETS.exists():
        sys.exit(f"missing {SECRETS} — copy secrets.toml.example and fill in dominio")
    return tomllib.loads(SECRETS.read_text(encoding="utf-8"))


def main(id_produto: int = 1) -> None:
    print("=" * 60)
    print("1) xSenha formula self-test")
    print("=" * 60)
    expected = "b3BoZDAyb3BoZDAyfEA0NXxtaXNhbQ=="
    got = client.compute_xsenha(date(2026, 5, 14))  # Saurus example date
    print(f"  14/05/2026 → {got}")
    print(f"  expected   → {expected}")
    assert got == expected, "FORMULA MISMATCH"
    today_pw = client.compute_xsenha()
    print(f"  today      → {today_pw}")
    print("  ✅ formula matches documented example.")

    print()
    print("=" * 60)
    print(f"2) Live SOAP call: retProduto IdProduto={id_produto}")
    print("=" * 60)
    secrets = load_secrets()
    ws = secrets["wsretaguarda"]
    dominio = ws["dominio"]
    cfg = client.WsConfig(
        endpoint=ws["endpoint"],
        dominio=dominio,
        xsenha_override=ws.get("xsenha") or None,
        timeout=30,
    )
    print(f"  endpoint : {cfg.endpoint}")
    print(f"  dominio  : {dominio}")
    print(f"  xsenha   : {cfg.xsenha_override or '(daily, computed)'}")

    payload = (
        "<xmlIntegracao>"
        f"<Dominio>{dominio}</Dominio>"
        f"<IdProduto>{int(id_produto)}</IdProduto>"
        "</xmlIntegracao>"
    )
    try:
        xml = client.call("retProduto", payload, config=cfg)
    except client.WsRetaguardaError as exc:
        print(f"  ⚠️  server rejected request: {exc}")
        print(
            "  → Transport works. Common causes: invalid Dominio, "
            "IdProduto doesn't exist, or daily xSenha was rotated."
        )
        return
    except Exception as exc:  # noqa: BLE001
        print(f"  ❌ network/parse error: {exc.__class__.__name__}: {exc}")
        sys.exit(1)

    print(f"  ✅ response OK ({len(xml)} chars of XML)")
    print(f"  raw      : {xml[:300]!r}")
    parsed = parsers.parse_produto(xml)
    if parsed is None:
        print(f"  ⚠️  <Produto /> vazio para IdProduto={id_produto} (id não existe)")
    else:
        p = parsed["produto"]
        print(f"     id_produto      : {p['id_produto']}")
        print(f"     desc_produto    : {p['desc_produto']}")
        print(f"     desc_categoria  : {p['desc_categoria']}")
        print(f"     v_compra        : {p['v_compra']}")
        print(f"     codigos (EAN)   : {len(parsed['codigos'])}")
        print(f"     precos          : {len(parsed['precos'])}")
        print(f"     lojas           : {len(parsed['lojas'])}")

    # ------------------------------------------------------------------
    # Sales pull — probe a few TpMov values
    # ------------------------------------------------------------------
    from datetime import datetime, timedelta
    print()
    print("=" * 60)
    print("3) Live SOAP call: retMovimentacoesCompleto")
    print("=" * 60)
    d_fim = datetime.now()
    combos = [
        ("365d NFCe(20) Final(2)", 365, 20, 2),
        ("365d NFCe(20) Aberto(0)", 365, 20, 0),
        ("365d NFe(10) Final(2)",  365, 10, 2),
        ("365d Pedido(30) Final(2)", 365, 30, 2),
        ("365d Pedido(30) Aberto(0)", 365, 30, 0),
    ]
    for label, days, tp_mov, ind_status in combos:
        d_ini = d_fim - timedelta(days=days)
        sales_payload = (
            "<xmlIntegracao>"
            f"<Dominio>{dominio}</Dominio>"
            f"<TpMov>{tp_mov}</TpMov>"
            f"<IndStatus>{ind_status}</IndStatus>"
            "<xNome></xNome>"
            "<DocEmit></DocEmit>"
            f"<DInicial>{d_ini:%Y-%m-%d %H:%M:%S}</DInicial>"
            f"<DFinal>{d_fim:%Y-%m-%d %H:%M:%S}</DFinal>"
            "</xmlIntegracao>"
        )
        for method in ("retMovimentacoesCompleto", "retMovimentacoes"):
            try:
                sales_xml = client.call(method, sales_payload, config=cfg)
            except client.WsRetaguardaError as exc:
                print(f"  {label} [{method}]: ⚠️  {exc.ret_texto}")
                continue
            movs, items = parsers.parse_movimentacoes(sales_xml)
            print(f"  {label} [{method}]: {len(movs)} movs, {len(items)} itens, xml={len(sales_xml)} chars")
            if movs:
                m = movs[0]
                print(f"     ↳ primeira mov: id={m['id_mov']} dh={m['dh_emi']} nNf={m['n_nf']} vNF={m['tot_v_nf']}")
                if items:
                    i = items[0]
                    print(f"     ↳ primeiro item: id_produto={i['id_produto']} x_prod={i['x_prod']!r} q={i['q_com']} v={i['v_prod']}")
                return

    # Service status (no auth needed beyond xSenha)
    print()
    print("=" * 60)
    print("4) retStatusServico (health check)")
    print("=" * 60)
    try:
        status_xml = client.call("retStatusServico", "<xmlIntegracao/>", config=cfg)
        print(f"  ✅ status: {status_xml[:300]!r}")
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠️  {exc}")


if __name__ == "__main__":
    arg = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    main(arg)
