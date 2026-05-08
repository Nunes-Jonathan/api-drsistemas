"""Scan a range of IdProduto via retProduto until a non-empty Produto is found."""
from __future__ import annotations

import sys

from wsretaguarda import client


def main(start: int, end: int) -> None:
    cfg = client.get_config()
    for pid in range(start, end + 1):
        payload = (
            "<xmlIntegracao>"
            f"<Dominio>{cfg.dominio}</Dominio>"
            f"<IdProduto>{pid}</IdProduto>"
            "</xmlIntegracao>"
        )
        try:
            xml = client.call("retProduto", payload, config=cfg)
        except Exception as e:  # noqa: BLE001
            print(f"id={pid}  ERROR  {e}")
            continue
        body = (xml or "").strip()
        if not body or body == "<Produto />" or body == "<Produto/>":
            continue
        print(f"id={pid}  len={len(body)}")
        print(body[:2000])
        return
    print(f"no non-empty product found in [{start}, {end}]")


if __name__ == "__main__":
    a, b = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (1, 50)
    main(a, b)
