"""
Módulo 1 — Facebook Ad Library Scraper

Busca anuncios activos en EEUU usando la Graph API v25.0.
Filtra por anuncios con 90+ días de antigüedad (señal de conversión).
Exporta CSV ordenado por días activo descendente.
"""

import csv
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from config import (
    AD_FIELDS,
    AD_REACHED_COUNTRIES,
    FB_ADS_ARCHIVE_ENDPOINT,
    FB_API_VERSION,
    FB_OUTPUT_FILENAME,
    KEYWORDS,
    MAX_ADS_PER_KEYWORD,
    MIN_DAYS_ACTIVE,
)

logger = logging.getLogger(__name__)
console = Console()

OUTPUT_DIR = Path(__file__).parent.parent / "output"


def _get_token() -> str:
    token = os.getenv("ACCESS_TOKEN", "").strip()
    if not token:
        console.print(
            "[bold red]ERROR:[/] ACCESS_TOKEN no encontrado en el .env.\n"
            "Asegurate de tener el archivo .env con ACCESS_TOKEN=tu_token"
        )
        sys.exit(1)
    return token


def _is_token_expired_error(response_json: dict) -> bool:
    error = response_json.get("error", {})
    code = error.get("code")
    subcode = error.get("error_subcode")
    msg = error.get("message", "").lower()
    return code in (190, 102) or subcode == 463 or "expired" in msg or "invalid oauth" in msg


def _fetch_page(token: str, params: dict) -> dict | None:
    url = FB_ADS_ARCHIVE_ENDPOINT.format(version=FB_API_VERSION)
    try:
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
    except requests.RequestException as e:
        logger.error("Error de red al consultar la API: %s", e)
        console.print(f"[red]Error de red:[/] {e}")
        return None

    if "error" in data:
        if _is_token_expired_error(data):
            console.print(
                "\n[bold red]⚠  Token expirado.[/]\n"
                "Renovalo en [link=https://developers.facebook.com/tools/explorer/]"
                "Meta Explorer[/link] y actualizá [bold]ACCESS_TOKEN[/] en el [bold].env[/].\n"
            )
            sys.exit(1)
        msg = data["error"].get("message", str(data["error"]))
        logger.error("Error de API: %s", msg)
        console.print(f"[red]Error de API:[/] {msg}")
        return None

    return data


def _fetch_all_ads_for_keyword(token: str, keyword: str) -> list[dict]:
    params = {
        "access_token": token,
        "search_terms": keyword,
        "ad_reached_countries": AD_REACHED_COUNTRIES,
        "ad_active_status": "ACTIVE",
        "fields": AD_FIELDS,
        "limit": 500,
    }

    ads: list[dict] = []
    page_num = 0

    while True:
        page_num += 1
        logger.debug("Keyword '%s' — página %d", keyword, page_num)
        data = _fetch_page(token, params)
        if data is None:
            break

        batch = data.get("data", [])
        ads.extend(batch)
        logger.info("Keyword '%s' — acumulados %d anuncios", keyword, len(ads))

        if MAX_ADS_PER_KEYWORD and len(ads) >= MAX_ADS_PER_KEYWORD:
            ads = ads[:MAX_ADS_PER_KEYWORD]
            break

        next_cursor = data.get("paging", {}).get("cursors", {}).get("after")
        if not next_cursor:
            break

        params["after"] = next_cursor
        time.sleep(0.3)  # respeto rate-limits

    return ads


def _calc_days_active(ad_creation_time: str) -> int:
    try:
        created = datetime.fromisoformat(ad_creation_time.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - created
        return delta.days
    except (ValueError, TypeError):
        return 0


def _filter_and_enrich(ads: list[dict], keyword: str) -> list[dict]:
    enriched = []
    for ad in ads:
        creation_time = ad.get("ad_creation_time", "")
        days = _calc_days_active(creation_time)
        if days < MIN_DAYS_ACTIVE:
            continue
        enriched.append(
            {
                "keyword": keyword,
                "page_name": ad.get("page_name", ""),
                "ad_creation_time": creation_time,
                "dias_activo": days,
                "ad_snapshot_url": ad.get("ad_snapshot_url", ""),
            }
        )
    return enriched


def _save_csv(rows: list[dict], path: Path) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = ["keyword", "page_name", "ad_creation_time", "dias_activo", "ad_snapshot_url"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    console.print(f"\n[green]CSV guardado en:[/] {path}")


def _print_summary(all_rows: list[dict], counts_by_keyword: dict[str, int]) -> None:
    console.rule("[bold cyan]RESUMEN FB Ad Library[/]")

    # Totales por keyword
    kw_table = Table(title="Anuncios encontrados por keyword (90+ días activos)", show_lines=True)
    kw_table.add_column("Keyword", style="cyan")
    kw_table.add_column("Total", justify="right", style="green")
    for kw, count in sorted(counts_by_keyword.items(), key=lambda x: -x[1]):
        kw_table.add_row(kw, str(count))
    console.print(kw_table)

    # Top 10 más longevos
    top10 = sorted(all_rows, key=lambda x: -x["dias_activo"])[:10]
    top_table = Table(title="Top 10 anuncios más longevos", show_lines=True)
    top_table.add_column("#", justify="right")
    top_table.add_column("Días activo", justify="right", style="bold yellow")
    top_table.add_column("Página", style="magenta")
    top_table.add_column("Keyword", style="cyan")
    top_table.add_column("URL", style="blue")
    for i, row in enumerate(top10, 1):
        top_table.add_row(
            str(i),
            str(row["dias_activo"]),
            row["page_name"],
            row["keyword"],
            row["ad_snapshot_url"],
        )
    console.print(top_table)
    console.print(f"\n[bold]Total anuncios exportados:[/] {len(all_rows)}")


def run() -> None:
    token = _get_token()
    all_rows: list[dict] = []
    counts_by_keyword: dict[str, int] = {}

    console.rule("[bold cyan]Módulo 1 — FB Ad Library Scraper[/]")
    console.print(
        f"Buscando [bold]{len(KEYWORDS)}[/] keywords · "
        f"filtro [bold]{MIN_DAYS_ACTIVE}+ días[/] activos · "
        f"país: [bold]{', '.join(AD_REACHED_COUNTRIES)}[/]\n"
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Iniciando...", total=len(KEYWORDS))

        for keyword in KEYWORDS:
            progress.update(task, description=f"Buscando: [cyan]{keyword}[/]")
            raw_ads = _fetch_all_ads_for_keyword(token, keyword)
            filtered = _filter_and_enrich(raw_ads, keyword)
            all_rows.extend(filtered)
            counts_by_keyword[keyword] = len(filtered)
            logger.info("Keyword '%s': %d raw → %d filtrados", keyword, len(raw_ads), len(filtered))
            progress.advance(task)

    if not all_rows:
        console.print("[yellow]No se encontraron anuncios con los filtros aplicados.[/]")
        return

    all_rows.sort(key=lambda x: -x["dias_activo"])
    output_path = OUTPUT_DIR / FB_OUTPUT_FILENAME
    _save_csv(all_rows, output_path)
    _print_summary(all_rows, counts_by_keyword)
