#!/usr/bin/env python3
"""
ecommR — Herramienta de investigación de productos para e-commerce
Menú principal para seleccionar y ejecutar cada módulo.
"""

import logging
import sys
from pathlib import Path

# Permite importar config y modules desde cualquier CWD
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
# Silenciar logs de requests/urllib3 salvo errores
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)

console = Console()

MENU = """
  [bold cyan]1.[/] FB Ad Library Scraper   — encontrar anuncios ganadores en EEUU
  [bold cyan]2.[/] Analizador de tienda     — analizar una Shopify competidora
  [bold cyan]3.[/] Calculadora de margen    — evaluar rentabilidad en Argentina
  [bold cyan]4.[/] Trends AR vs US          — comparar interés de búsqueda
  [bold cyan]5.[/] Validador de demanda ML  — señales de competencia en MercadoLibre
  [bold cyan]q.[/] Salir
"""


def main() -> None:
    console.print(
        Panel.fit(
            "[bold white]ecommR[/] — Investigación de productos para Argentina",
            subtitle="MercadoLibre · Meta Ads · Shopify",
            border_style="cyan",
        )
    )

    while True:
        console.print(MENU)
        choice = console.input("[bold]Elegí una opción:[/] ").strip().lower()

        if choice == "1":
            from modules.fb_scraper import run
            run()
        elif choice == "2":
            from modules.store_analyzer import run
            run()
        elif choice == "3":
            from modules.margin_calc import run
            run()
        elif choice == "4":
            from modules.trends_analyzer import run
            run()
        elif choice == "5":
            from modules.ml_validator import run
            run()
        elif choice in ("q", "quit", "exit", "salir"):
            console.print("\n[dim]Hasta luego.[/]")
            break
        else:
            console.print("[yellow]Opción inválida. Ingresá 1, 2, 3, 4, 5 o q.[/]")


if __name__ == "__main__":
    main()
