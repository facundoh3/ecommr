"""
Módulo 1 — Facebook Ad Library Scraper

Busca anuncios activos en EEUU usando la Graph API v25.0.
Clasifica cada anuncio en un semáforo de 3 niveles (verde/amarillo/rojo)
combinando días activo, variedad creativa y expansión multi-país (ver
utils/scoring.py), en vez de un corte binario fijo de 90 días.
Exporta CSV ordenado por días activo descendente.
"""

import csv
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
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
    MULTI_GEO_CHECK_COUNTRIES,
    MULTI_GEO_CHECK_LIMIT,
)
from utils.display import console, semaforo_label
from utils.scoring import PERSISTENCE_YELLOW_DAYS, score_signals

logger = logging.getLogger(__name__)

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
        "ad_reached_countries": json.dumps(AD_REACHED_COUNTRIES),
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
    """Mantiene solo los anuncios que superan el umbral mínimo (amarillo+verde).

    El tier final (verde/amarillo/rojo) se calcula después, una vez agregadas
    las señales de variedad creativa y multi-país por página (ver run()).
    """
    enriched = []
    for ad in ads:
        creation_time = ad.get("ad_creation_time", "")
        days = _calc_days_active(creation_time)
        if days < PERSISTENCE_YELLOW_DAYS:
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


def _check_multi_geo(token: str, page_name: str) -> bool:
    """Chequea si la página tiene anuncios activos en mercados adicionales (capado)."""
    params = {
        "access_token": token,
        "search_terms": page_name,
        "ad_reached_countries": json.dumps(MULTI_GEO_CHECK_COUNTRIES),
        "ad_active_status": "ACTIVE",
        "fields": "id",
        "limit": 1,
    }
    data = _fetch_page(token, params)
    if data is None:
        return False
    return len(data.get("data", [])) > 0


def _attach_signals(all_rows: list[dict], token: str) -> None:
    """Agrega variedad creativa (sin costo de API) y expansión multi-país (capada),
    y calcula el tier final de cada fila in-place."""
    page_urls: dict[str, set] = {}
    page_max_days: dict[str, int] = {}
    for row in all_rows:
        pn = row["page_name"]
        page_urls.setdefault(pn, set()).add(row["ad_snapshot_url"])
        page_max_days[pn] = max(page_max_days.get(pn, 0), row["dias_activo"])
    creative_counts = {pn: len(urls) for pn, urls in page_urls.items()}

    candidates = sorted(page_max_days.items(), key=lambda x: -x[1])[:MULTI_GEO_CHECK_LIMIT]
    console.print(
        f"\n[cyan]→ Verificando expansión multi-país para los {len(candidates)} "
        f"candidatos más longevos...[/]"
    )
    multi_geo_map: dict[str, bool] = {}
    for page_name, _ in candidates:
        multi_geo_map[page_name] = _check_multi_geo(token, page_name)
        time.sleep(0.3)

    for row in all_rows:
        pn = row["page_name"]
        signals = score_signals(
            row["dias_activo"], multi_geo_map.get(pn, False), creative_counts.get(pn, 1)
        )
        row["creative_variety"] = creative_counts.get(pn, 1)
        row["multi_geo"] = multi_geo_map.get(pn, False)
        row["tier"] = signals["tier"]


def _save_csv(rows: list[dict], path: Path) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "keyword",
        "page_name",
        "ad_creation_time",
        "dias_activo",
        "creative_variety",
        "multi_geo",
        "tier",
        "ad_snapshot_url",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    console.print(f"\n[green]CSV guardado en:[/] {path}")


def _print_summary(all_rows: list[dict], counts_by_keyword: dict[str, int]) -> None:
    console.rule("[bold cyan]RESUMEN FB Ad Library[/]")

    # Totales por keyword, desglosado por tier
    tier_counts_by_kw: dict[str, dict[str, int]] = {}
    for row in all_rows:
        d = tier_counts_by_kw.setdefault(row["keyword"], {"green": 0, "yellow": 0})
        d[row["tier"]] = d.get(row["tier"], 0) + 1

    kw_table = Table(
        title=f"Anuncios encontrados por keyword ({PERSISTENCE_YELLOW_DAYS}+ días activos)",
        show_lines=True,
    )
    kw_table.add_column("Keyword", style="cyan")
    kw_table.add_column("Total", justify="right", style="green")
    kw_table.add_column("Verde", justify="right", style="bold green")
    kw_table.add_column("Amarillo", justify="right", style="bold yellow")
    for kw, count in sorted(counts_by_keyword.items(), key=lambda x: -x[1]):
        tiers = tier_counts_by_kw.get(kw, {"green": 0, "yellow": 0})
        kw_table.add_row(kw, str(count), str(tiers.get("green", 0)), str(tiers.get("yellow", 0)))
    console.print(kw_table)

    # Top 10 más longevos
    top10 = sorted(all_rows, key=lambda x: -x["dias_activo"])[:10]
    top_table = Table(title="Top 10 anuncios más longevos", show_lines=True)
    top_table.add_column("#", justify="right")
    top_table.add_column("Tier", justify="center")
    top_table.add_column("Días activo", justify="right", style="bold yellow")
    top_table.add_column("Multi-país", justify="center")
    top_table.add_column("Creativos", justify="right")
    top_table.add_column("Página", style="magenta")
    top_table.add_column("Keyword", style="cyan")
    top_table.add_column("URL", style="blue")
    for i, row in enumerate(top10, 1):
        top_table.add_row(
            str(i),
            semaforo_label(row["tier"]),
            str(row["dias_activo"]),
            "Sí" if row["multi_geo"] else "—",
            str(row["creative_variety"]),
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
        f"umbral mínimo [bold]{PERSISTENCE_YELLOW_DAYS}+ días[/] activos · "
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

    _attach_signals(all_rows, token)

    all_rows.sort(key=lambda x: -x["dias_activo"])
    output_path = OUTPUT_DIR / FB_OUTPUT_FILENAME
    _save_csv(all_rows, output_path)
    _print_summary(all_rows, counts_by_keyword)
