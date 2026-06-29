"""
Módulo 4 — Comparador de Google Trends Argentina vs Estados Unidos

Compara el interés de búsqueda de un producto entre AR y US usando pytrends.

ADVERTENCIA: pytrends está archivado/sin mantenimiento desde abril 2025 y es
propenso a errores 429 (Too Many Requests) sin rotación de proxies, además de
romperse con versiones nuevas de sus dependencias (urllib3, etc). Por eso cada
llamada está envuelta en su propio try/except amplio: si pytrends falla por
cualquier motivo (429, error de import, cambio de API no documentado), el
módulo cae a imprimir links manuales de Google Trends en vez de fallar
directamente. No depende exclusivamente de esta librería.
"""

import logging
import time
from urllib.parse import quote

from config import (
    TRENDS_GEO_AR,
    TRENDS_GEO_US,
    TRENDS_HL,
    TRENDS_RETRY_DELAYS,
    TRENDS_TIMEFRAME,
    TRENDS_TZ,
)
from utils.display import console

logger = logging.getLogger(__name__)


def _manual_url(query: str, geo: str) -> str:
    return (
        "https://trends.google.com/trends/explore?"
        f"date={quote(TRENDS_TIMEFRAME)}&geo={geo}&q={quote(query)}"
    )


def _get_trendreq():
    from pytrends.request import TrendReq

    return TrendReq(hl=TRENDS_HL, tz=TRENDS_TZ)


def _snapshot_by_region(query: str) -> dict | None:
    """Compara interés relativo AR vs US en una sola consulta (geo='', resolución país)."""
    try:
        pytrends = _get_trendreq()
        pytrends.build_payload(kw_list=[query], timeframe=TRENDS_TIMEFRAME, geo="")
        df = pytrends.interest_by_region(resolution="COUNTRY", inc_low_vol=True, inc_geo_code=True)
    except Exception as e:
        logger.warning("Snapshot por región falló: %s", e)
        return None

    if df is None or df.empty or "geoCode" not in df.columns:
        return None

    ar_rows = df[df["geoCode"] == TRENDS_GEO_AR]
    us_rows = df[df["geoCode"] == TRENDS_GEO_US]
    ar_score = int(ar_rows[query].iloc[0]) if not ar_rows.empty else 0
    us_score = int(us_rows[query].iloc[0]) if not us_rows.empty else 0
    return {"ar": ar_score, "us": us_score}


def _classify_trend(values: list[float]) -> str | None:
    """Compara el promedio de la 1ra mitad de la serie vs la 2da para inferir dirección."""
    if len(values) < 2:
        return None

    mid = len(values) // 2
    first_half_avg = sum(values[:mid]) / mid if mid else 0
    second_half_avg = sum(values[mid:]) / (len(values) - mid)

    if second_half_avg > first_half_avg * 1.15:
        return "creciente"
    elif second_half_avg < first_half_avg * 0.85:
        return "decreciente"
    return "estable"


def _trend_direction(query: str, geo: str) -> str | None:
    try:
        pytrends = _get_trendreq()
        pytrends.build_payload(kw_list=[query], timeframe=TRENDS_TIMEFRAME, geo=geo)
        df = pytrends.interest_over_time()
    except Exception as e:
        logger.warning("Serie temporal para geo=%s falló: %s", geo, e)
        return None

    if df is None or df.empty or query not in df.columns:
        return None

    return _classify_trend(df[query].tolist())


def _with_retries(fn, *args, **kwargs):
    result = None
    for delay in [0] + TRENDS_RETRY_DELAYS:
        if delay:
            time.sleep(delay)
        result = fn(*args, **kwargs)
        if result is not None:
            return result
    return result


def run() -> None:
    console.rule("[bold cyan]Módulo 4 — Comparador Trends AR vs US[/]")
    console.print(
        "[dim]pytrends está sin mantenimiento y puede fallar con 429. "
        "Si falla, te dejamos los links manuales de Google Trends.[/]\n"
    )

    query = console.input("[bold]Producto a comparar (ej: posture corrector):[/] ").strip()
    if not query:
        console.print("[red]Búsqueda vacía. Saliendo.[/]")
        return

    console.print("\n[cyan]→ Comparando interés relativo AR vs US...[/]")
    snapshot = _with_retries(_snapshot_by_region, query)

    if not snapshot:
        console.print(
            "[yellow]pytrends no devolvió datos (probablemente 429 o cambio de API). "
            "Comparación manual:[/]"
        )
        console.print(f"  AR: {_manual_url(query, TRENDS_GEO_AR)}")
        console.print(f"  US: {_manual_url(query, TRENDS_GEO_US)}")
        return

    console.print(
        f"[bold]Interés relativo (0-100):[/] "
        f"Argentina = [bold]{snapshot['ar']}[/] · Estados Unidos = [bold]{snapshot['us']}[/]"
    )

    console.print("\n[cyan]→ Calculando tendencia temporal en cada país...[/]")
    ar_trend = _with_retries(_trend_direction, query, TRENDS_GEO_AR)
    us_trend = _with_retries(_trend_direction, query, TRENDS_GEO_US)

    if ar_trend:
        console.print(f"  Argentina: [bold]{ar_trend}[/]")
    else:
        console.print(
            f"  Argentina: [yellow]no disponible[/] — revisá manualmente: "
            f"{_manual_url(query, TRENDS_GEO_AR)}"
        )

    if us_trend:
        console.print(f"  Estados Unidos: [bold]{us_trend}[/]")
    else:
        console.print(
            f"  Estados Unidos: [yellow]no disponible[/] — revisá manualmente: "
            f"{_manual_url(query, TRENDS_GEO_US)}"
        )

    console.print(
        "\n[dim]Lectura sugerida:[/] si US está estable/decreciente y AR recién está "
        "creciendo, el producto puede estar llegando tarde a EEUU pero todavía a tiempo "
        "en Argentina.\n"
    )
