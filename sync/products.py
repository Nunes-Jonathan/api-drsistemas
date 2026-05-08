"""Sweep ``IdProduto`` 1..N over the SOAP API and refresh products from sales."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from db import repository
from wsretaguarda import methods
from wsretaguarda.client import WsRetaguardaError


ProgressFn = Callable[[int, int, str], None]


def _fetch_one(id_produto: int) -> tuple[int, dict | None, str | None]:
    try:
        parsed = methods.ret_produto(id_produto)
        if parsed is None:
            return id_produto, None, "produto vazio"
        return id_produto, parsed, None
    except WsRetaguardaError as exc:
        return id_produto, None, exc.ret_texto
    except Exception as exc:  # noqa: BLE001
        return id_produto, None, str(exc)


def sweep(
    start_id: int,
    end_id: int,
    *,
    max_workers: int = 4,
    on_progress: ProgressFn | None = None,
) -> dict[str, int]:
    """Sweep ``IdProduto`` from ``start_id`` to ``end_id`` (inclusive)."""
    ids = list(range(int(start_id), int(end_id) + 1))
    total = len(ids)
    counters = {"ok": 0, "missing": 0, "errors": 0}

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_fetch_one, i): i for i in ids}
        done = 0
        for fut in as_completed(futures):
            id_produto, parsed, err = fut.result()
            done += 1
            if parsed is not None:
                try:
                    repository.upsert_product(parsed)
                    counters["ok"] += 1
                    msg = f"id={id_produto} ok"
                except Exception as exc:  # noqa: BLE001
                    counters["errors"] += 1
                    msg = f"id={id_produto} db-error: {exc}"
            else:
                counters["missing"] += 1
                msg = f"id={id_produto} skipped: {err}"
            if on_progress:
                on_progress(done, total, msg)

    repository.update_sync_log(
        "products_sweep",
        status="ok",
        message=f"ok={counters['ok']} missing={counters['missing']} errors={counters['errors']}",
        cursor=f"{start_id}-{end_id}",
    )
    return counters


def refresh_from_sales(*, max_workers: int = 4, on_progress: ProgressFn | None = None) -> dict[str, int]:
    """Fetch any ``id_produto`` seen in sales_items but missing from products."""
    ids = repository.fetch_unsynced_product_ids()
    total = len(ids)
    counters = {"ok": 0, "missing": 0, "errors": 0}

    if not ids:
        if on_progress:
            on_progress(0, 0, "Nada a sincronizar.")
        repository.update_sync_log("products_from_sales", status="ok", message="nothing to do")
        return counters

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_fetch_one, i): i for i in ids}
        done = 0
        for fut in as_completed(futures):
            id_produto, parsed, err = fut.result()
            done += 1
            if parsed is not None:
                try:
                    repository.upsert_product(parsed)
                    counters["ok"] += 1
                    msg = f"id={id_produto} ok"
                except Exception as exc:  # noqa: BLE001
                    counters["errors"] += 1
                    msg = f"id={id_produto} db-error: {exc}"
            else:
                counters["missing"] += 1
                msg = f"id={id_produto} skipped: {err}"
            if on_progress:
                on_progress(done, total, msg)

    repository.update_sync_log(
        "products_from_sales",
        status="ok",
        message=f"ok={counters['ok']} missing={counters['missing']} errors={counters['errors']}",
    )
    return counters
