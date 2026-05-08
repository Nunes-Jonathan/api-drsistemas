"""Pull sales movements from ``retMovimentacoesCompleto`` into Postgres."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from db import repository
from wsretaguarda import methods

ProgressFn = Callable[[str], None]


def pull(
    d_inicial: datetime | None = None,
    d_final: datetime | None = None,
    *,
    lookback_days: int = 90,
    on_progress: ProgressFn | None = None,
) -> dict[str, int]:
    """Fetch authorized sales between ``d_inicial`` and ``d_final``.

    When ``d_inicial`` is omitted it picks up from ``MAX(dh_emi)`` in
    ``sales_movements`` (or ``now() - lookback_days`` on cold start).
    """
    if d_final is None:
        d_final = datetime.now()
    if d_inicial is None:
        last = repository.fetch_max_dh_emi()
        d_inicial = (
            (last - timedelta(minutes=5)).replace(tzinfo=None) if last else d_final - timedelta(days=lookback_days)
        )

    if on_progress:
        on_progress(f"Buscando vendas {d_inicial:%Y-%m-%d %H:%M} → {d_final:%Y-%m-%d %H:%M}")
    movs, items = methods.ret_movimentacoes_completo(d_inicial, d_final)
    if on_progress:
        on_progress(f"Recebidas {len(movs)} movimentações com {len(items)} itens. Gravando…")
    repository.upsert_movements(movs, items)

    counters = {"movements": len(movs), "items": len(items)}
    repository.update_sync_log(
        "sales_pull",
        status="ok",
        message=f"movs={counters['movements']} items={counters['items']}",
        cursor=d_final.strftime("%Y-%m-%d %H:%M:%S"),
    )
    if on_progress:
        on_progress(f"Sincronização concluída: {counters['movements']} movs, {counters['items']} itens.")
    return counters
