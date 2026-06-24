"""
Módulo 5 — Validador de demanda en MercadoLibre Argentina

Dado un término de búsqueda:
1. Consulta /sites/MLA/search: cantidad de listados, rango de precios,
   presencia de tiendas oficiales y de catálogo (señales de competencia).
2. Para los primeros N resultados, consulta /users/{seller_id} para ver
   reputación del vendedor (nivel, power seller, transacciones).
3. Opcional (opt-in): scrapea un puñado de permalinks buscando texto
   "vendidos" en la página — best-effort, no garantizado, con riesgo de
   bloqueo de IP si se abusa.

Nota importante: el campo "sold_quantity" NO está disponible en la API
pública de MercadoLibre desde 2016 — solo lo puede ver el dueño del ítem
con su propio token. Cualquier valor de "vendidos" que se obtenga acá viene
del scraping opcional del HTML, no de la API, y puede fallar o no estar.
Por eso este módulo no inventa un score de "demanda" falso: muestra señales
de competencia/confianza reales y deja la interpretación final a criterio
humano.
"""

import logging
import re
import time

import requests
from bs4 import BeautifulSoup
from rich.table import Table
from rich.panel import Panel

from config import (
    ML_SEARCH_ENDPOINT,
    ML_SITE_ID,
    ML_SEARCH_LIMIT,
    ML_TOP_N_SELLER_REPUTATION,
    ML_USER_ENDPOINT,
    ML_VENDIDOS_SCRAPE_CAP,
    REQUEST_TIMEOUT,
    SCRAPER_USER_AGENT,
)
from utils.display import console

logger = logging.getLogger(__name__)


def _search(query: str) -> dict | None:
    url = ML_SEARCH_ENDPOINT.format(site_id=ML_SITE_ID)
    params = {"q": query, "limit": ML_SEARCH_LIMIT}
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error("Error consultando ML search: %s", e)
        console.print(f"[red]Error de red consultando MercadoLibre:[/] {e}")
        return None


def _get_seller_reputation(seller_id: int) -> dict | None:
    url = ML_USER_ENDPOINT.format(seller_id=seller_id)
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.warning("Error consultando reputación del vendedor %s: %s", seller_id, e)
        return None


def _scrape_vendidos(permalink: str) -> str | None:
    headers = {"User-Agent": SCRAPER_USER_AGENT}
    try:
        resp = requests.get(permalink, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("Error scrapeando 'vendidos' en %s: %s", permalink, e)
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    match = re.search(r"\d[\d.,]*\s+vendidos?", soup.get_text(), re.IGNORECASE)
    return match.group(0) if match else None


def _summarize_listings(results: list[dict]) -> dict:
    prices = [r["price"] for r in results if r.get("price") is not None]
    official_count = sum(1 for r in results if r.get("official_store_id"))
    catalog_count = sum(1 for r in results if r.get("catalog_product_id"))
    free_shipping_count = sum(
        1 for r in results if r.get("shipping", {}).get("free_shipping")
    )
    return {
        "min_price": min(prices) if prices else None,
        "max_price": max(prices) if prices else None,
        "avg_price": sum(prices) / len(prices) if prices else None,
        "official_count": official_count,
        "catalog_count": catalog_count,
        "free_shipping_count": free_shipping_count,
        "sample_size": len(results),
    }


def _print_listing_summary(query: str, total_listings: int, summary: dict) -> None:
    t = Table(title=f"Listados para '{query}'", show_lines=True)
    t.add_column("Señal", style="cyan")
    t.add_column("Valor", justify="right", style="white")

    t.add_row("Total de listados", str(total_listings))
    n = summary["sample_size"]
    if summary["min_price"] is not None:
        t.add_row(
            "Rango de precios (muestra)",
            f"${summary['min_price']:,.0f} – ${summary['max_price']:,.0f} "
            f"(prom. ${summary['avg_price']:,.0f})",
        )
    t.add_row("Tiendas oficiales (muestra)", f"{summary['official_count']}/{n}")
    t.add_row("En catálogo / buybox (muestra)", f"{summary['catalog_count']}/{n}")
    t.add_row("Envío gratis (muestra)", f"{summary['free_shipping_count']}/{n}")

    console.print(t)


def _print_reputation_table(reputations: list[tuple[str, dict]]) -> None:
    t = Table(title="Reputación de los primeros vendedores", show_lines=True)
    t.add_column("Vendedor", style="magenta")
    t.add_column("Nivel", justify="center")
    t.add_column("Power Seller", justify="center")
    t.add_column("Transacciones", justify="right")
    t.add_column("% Positivas", justify="right")

    for nickname, rep in reputations:
        seller_rep = rep.get("seller_reputation", {}) or {}
        level = seller_rep.get("level_id") or "—"
        power = seller_rep.get("power_seller_status") or "—"
        transactions = seller_rep.get("transactions", {}) or {}
        total_tx = transactions.get("total")
        positive = transactions.get("ratings", {}).get("positive")
        t.add_row(
            nickname or "—",
            str(level),
            str(power),
            str(total_tx) if total_tx is not None else "—",
            f"{positive*100:.0f}%" if positive is not None else "—",
        )

    console.print(t)


def run() -> None:
    console.rule("[bold cyan]Módulo 5 — Validador de demanda ML Argentina[/]")
    console.print(
        "[dim]Nota: la API pública de MercadoLibre no expone 'sold_quantity' desde 2016 "
        "(solo el dueño del ítem lo ve con su propio token). Este módulo usa cantidad de "
        "listados, tiendas oficiales/catálogo y reputación de vendedores como señales "
        "indirectas de demanda y competencia.[/]\n"
    )

    query = console.input(
        "[bold]Producto a buscar en MercadoLibre (ej: corrector de postura):[/] "
    ).strip()
    if not query:
        console.print("[red]Búsqueda vacía. Saliendo.[/]")
        return

    data = _search(query)
    if not data:
        return

    results = data.get("results", [])
    total_listings = data.get("paging", {}).get("total", len(results))

    if not results:
        console.print(f"[yellow]No se encontraron resultados para '{query}'.[/]")
        return

    summary = _summarize_listings(results)
    _print_listing_summary(query, total_listings, summary)

    console.print(
        f"\n[cyan]→ Consultando reputación de los primeros "
        f"{ML_TOP_N_SELLER_REPUTATION} vendedores...[/]"
    )
    reputations = []
    for r in results[:ML_TOP_N_SELLER_REPUTATION]:
        seller_id = r.get("seller", {}).get("id")
        if not seller_id:
            continue
        rep = _get_seller_reputation(seller_id)
        if rep:
            reputations.append((rep.get("nickname", str(seller_id)), rep))
        time.sleep(0.2)

    if reputations:
        _print_reputation_table(reputations)
    else:
        console.print("[yellow]No se pudo obtener reputación de vendedores.[/]")

    do_scrape = console.input(
        f"\n¿Scrapear texto 'vendidos' de los primeros {ML_VENDIDOS_SCRAPE_CAP} "
        "listados? Riesgo de bloqueo de IP si se abusa (s/N): "
    ).strip().lower() in ("s", "si", "sí", "y", "yes")

    if do_scrape:
        console.print(f"[cyan]→ Scrapeando hasta {ML_VENDIDOS_SCRAPE_CAP} permalinks...[/]")
        vendidos_lines = []
        for r in results[:ML_VENDIDOS_SCRAPE_CAP]:
            permalink = r.get("permalink")
            if not permalink:
                continue
            vendidos = _scrape_vendidos(permalink)
            vendidos_lines.append(
                f"{r.get('title', '(sin título)')[:60]} → "
                f"{vendidos if vendidos else '(no encontrado)'}"
            )
            time.sleep(0.3)
        console.print(Panel("\n".join(vendidos_lines), title="[bold]Vendidos (best-effort)[/]"))

    console.print(
        "\n[dim]Lectura sugerida:[/] pocos listados + vendedores con buena reputación y "
        "sin tiendas oficiales dominantes puede indicar una oportunidad poco explotada. "
        "Muchos listados + tiendas oficiales/catálogo dominante suele indicar mercado "
        "saturado — conviene validar diferenciación antes de importar.\n"
    )
