"""
Módulo 2 — Analizador de tienda Shopify competidora

Dado una URL base de Shopify:
1. Scrapea el producto más vendido (/collections/all?sort_by=best-selling)
2. Scrapea el producto más nuevo (/collections/all?sort_by=created-descending)
3. Cuenta anuncios activos en FB Ad Library para esa página
4. Informa si SimilarWeb requiere consulta manual

Nota: no se hace login ni se bypassean CAPTCHAs;
      funciona con stores que tienen el catálogo público.
"""

import logging
import os
import re
import sys
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from rich.console import Console
from rich.panel import Panel

from config import (
    AD_FIELDS,
    AD_REACHED_COUNTRIES,
    FB_ADS_ARCHIVE_ENDPOINT,
    FB_API_VERSION,
    REQUEST_TIMEOUT,
    SCRAPER_USER_AGENT,
)

logger = logging.getLogger(__name__)
console = Console()


# ─── Helpers ──────────────────────────────────────────────────────────────

def _normalize_url(raw: str) -> str:
    raw = raw.strip().rstrip("/")
    if not raw.startswith("http"):
        raw = "https://" + raw
    return raw


def _get_page(url: str) -> BeautifulSoup | None:
    headers = {"User-Agent": SCRAPER_USER_AGENT}
    try:
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.HTTPError as e:
        logger.warning("HTTP %s al acceder a %s", e.response.status_code, url)
        console.print(f"[yellow]Advertencia:[/] HTTP {e.response.status_code} en {url}")
        return None
    except requests.RequestException as e:
        logger.error("Error de red accediendo a %s: %s", url, e)
        console.print(f"[red]Error de red:[/] {e}")
        return None


def _scrape_first_product(base_url: str, sort_param: str) -> dict | None:
    url = f"{base_url}/collections/all?sort_by={sort_param}"
    soup = _get_page(url)
    if not soup:
        return None

    # Shopify usa distintos esquemas; probamos los más comunes
    # Intento 1: product-card con title y price
    title_el = (
        soup.select_one(".product-card__title")
        or soup.select_one(".product-item__title")
        or soup.select_one(".grid-product__title")
        or soup.select_one("h2.product__title")
        or soup.select_one('[class*="product"][class*="title"]')
        or soup.select_one("h2.h4")          # Dawn theme
        or soup.select_one(".card__heading")  # Dawn theme alternativo
    )
    price_el = (
        soup.select_one(".price__regular")
        or soup.select_one(".product-card__price")
        or soup.select_one(".product-price")
        or soup.select_one('[class*="price"]')
    )

    if not title_el:
        logger.warning("No se pudo encontrar el título del producto en %s", url)
        return {"name": "(título no encontrado)", "price": "(precio no encontrado)", "url": url}

    return {
        "name": title_el.get_text(strip=True),
        "price": price_el.get_text(strip=True) if price_el else "(precio no encontrado)",
        "url": url,
    }


def _get_page_name_from_url(store_url: str) -> str:
    """Extrae el nombre de dominio limpio para buscar en FB Ad Library."""
    parsed = urlparse(store_url)
    domain = parsed.netloc or parsed.path
    # Quitar 'www.' y la extensión para obtener el nombre de marca
    name = re.sub(r"^www\.", "", domain)
    name = re.sub(r"\.[a-z]{2,}$", "", name)
    return name


def _count_fb_ads(page_name: str) -> int | None:
    token = os.getenv("ACCESS_TOKEN", "").strip()
    if not token:
        console.print("[yellow]ACCESS_TOKEN no configurado — saltando conteo de FB Ads.[/]")
        return None

    url = FB_ADS_ARCHIVE_ENDPOINT.format(version=FB_API_VERSION)
    params = {
        "access_token": token,
        "search_page_ids": "",  # se usa search_terms con el nombre
        "search_terms": page_name,
        "ad_reached_countries": AD_REACHED_COUNTRIES,
        "ad_active_status": "ACTIVE",
        "fields": "id",
        "limit": 100,
    }

    total = 0
    while True:
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
        except requests.RequestException as e:
            logger.error("Error al consultar FB Ad Library: %s", e)
            return None

        if "error" in data:
            msg = data["error"].get("message", str(data["error"]))
            logger.warning("FB API error al buscar página '%s': %s", page_name, msg)
            return None

        total += len(data.get("data", []))
        after = data.get("paging", {}).get("cursors", {}).get("after")
        if not after:
            break
        params["after"] = after
        time.sleep(0.2)

    return total


# ─── Función principal ─────────────────────────────────────────────────────

def run() -> None:
    console.rule("[bold cyan]Módulo 2 — Analizador de tienda Shopify[/]")

    raw_url = console.input("[bold]URL de la tienda (ej: tryhydro.com):[/] ").strip()
    if not raw_url:
        console.print("[red]URL vacía. Saliendo.[/]")
        return

    base_url = _normalize_url(raw_url)
    console.print(f"\nAnalizando [bold]{base_url}[/]...\n")

    # 1. Producto más vendido
    console.print("[cyan]→ Obteniendo producto más vendido...[/]")
    best_selling = _scrape_first_product(base_url, "best-selling")

    # 2. Producto más nuevo
    console.print("[cyan]→ Obteniendo producto más nuevo...[/]")
    newest = _scrape_first_product(base_url, "created-descending")

    # 3. Conteo de anuncios en FB Ad Library
    page_name = _get_page_name_from_url(base_url)
    console.print(f"[cyan]→ Buscando anuncios activos en FB para '{page_name}'...[/]")
    fb_count = _count_fb_ads(page_name)

    # 4. SimilarWeb
    similarweb_note = (
        "SimilarWeb no tiene API gratuita pública. "
        f"Consultalo manualmente en: https://www.similarweb.com/website/{urlparse(base_url).netloc}/"
    )

    # Output
    lines = []
    lines.append(f"[bold]Tienda:[/] {base_url}")
    lines.append("")

    if best_selling:
        lines.append(f"[bold]Producto más vendido:[/] {best_selling['name']}")
        lines.append(f"  Precio: {best_selling['price']}")
        lines.append(f"  URL:    {best_selling['url']}")
    else:
        lines.append("[yellow]Producto más vendido:[/] No se pudo obtener.")

    lines.append("")

    if newest:
        lines.append(f"[bold]Producto más nuevo:[/] {newest['name']}")
        lines.append(f"  URL: {newest['url']}")
    else:
        lines.append("[yellow]Producto más nuevo:[/] No se pudo obtener.")

    lines.append("")

    if fb_count is not None:
        lines.append(f"[bold]Anuncios activos en FB Ad Library:[/] {fb_count}")
    else:
        lines.append("[yellow]Anuncios FB:[/] No se pudo obtener (revisá el token).")

    lines.append("")
    lines.append(f"[bold]SimilarWeb:[/] {similarweb_note}")

    console.print(Panel("\n".join(lines), title="[bold cyan]Resumen de tienda[/]", expand=False))
