"""
Módulo 3 — Calculadora de margen para Argentina

Calcula margen bruto, margen neto y CPA breakeven
considerando comisiones de MercadoLibre, cuotas sin interés,
IIBB Mendoza y tipo de cambio.
"""

import logging
from rich.console import Console
from rich.table import Table
from rich.prompt import FloatPrompt, Confirm

from config import (
    CUOTAS_SIN_INTERES_PCT,
    IIBB_MENDOZA_PCT,
    MARGIN_GREEN_THRESHOLD,
    MARGIN_YELLOW_THRESHOLD,
    ML_COMMISSION_PCT,
    USD_TO_ARS,
)

logger = logging.getLogger(__name__)
console = Console()


def _semaforo(margin_net: float) -> str:
    if margin_net > MARGIN_GREEN_THRESHOLD:
        return "[bold green]VERDE ✓[/]"
    elif margin_net >= MARGIN_YELLOW_THRESHOLD:
        return "[bold yellow]AMARILLO ⚠[/]"
    else:
        return "[bold red]ROJO ✗[/]"


def _ask_float(prompt: str, default: float) -> float:
    raw = console.input(f"{prompt} [[bold]{default}[/]]: ").strip()
    if not raw:
        return default
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        console.print(f"[yellow]Valor inválido, usando default: {default}[/]")
        return default


def _calculate(
    cost_usd: float,
    sale_price_ars: float,
    shipping_ars: float,
    cpa_ars: float,
    ml_commission: float,
    cuotas_pct: float,
    iibb_pct: float,
    usd_to_ars: float,
    apply_cuotas: bool,
) -> dict:
    cost_ars = cost_usd * usd_to_ars

    # Costos que descuenta ML y cuotas del precio de venta
    ml_fee = sale_price_ars * ml_commission
    cuotas_fee = sale_price_ars * cuotas_pct if apply_cuotas else 0.0
    iibb_fee = sale_price_ars * iibb_pct

    # Ingresos netos después de comisiones
    net_revenue = sale_price_ars - ml_fee - cuotas_fee - iibb_fee

    # Margen bruto (sin envío ni CPA)
    gross_margin_ars = net_revenue - cost_ars
    gross_margin_pct = gross_margin_ars / sale_price_ars if sale_price_ars else 0

    # Margen neto (con envío y CPA)
    net_margin_ars = gross_margin_ars - shipping_ars - cpa_ars
    net_margin_pct = net_margin_ars / sale_price_ars if sale_price_ars else 0

    # CPA breakeven = máximo CPA sin perder plata
    cpa_breakeven = gross_margin_ars - shipping_ars

    return {
        "cost_ars": cost_ars,
        "ml_fee": ml_fee,
        "cuotas_fee": cuotas_fee,
        "iibb_fee": iibb_fee,
        "net_revenue": net_revenue,
        "gross_margin_ars": gross_margin_ars,
        "gross_margin_pct": gross_margin_pct,
        "net_margin_ars": net_margin_ars,
        "net_margin_pct": net_margin_pct,
        "cpa_breakeven": cpa_breakeven,
    }


def _print_results(inputs: dict, results: dict) -> None:
    t = Table(title="Calculadora de margen — ecommR", show_lines=True, min_width=55)
    t.add_column("Concepto", style="cyan")
    t.add_column("Valor (ARS)", justify="right", style="white")
    t.add_column("% sobre venta", justify="right", style="dim")

    sale = inputs["sale_price_ars"]

    def pct(val: float) -> str:
        return f"{val/sale*100:.1f}%" if sale else "—"

    t.add_row("Precio de venta", f"${sale:,.0f}", "100%")
    t.add_row("  Costo del producto (USD→ARS)", f"${results['cost_ars']:,.0f}", pct(results["cost_ars"]))
    t.add_row("  Comisión MercadoLibre", f"${results['ml_fee']:,.0f}", pct(results["ml_fee"]))
    if inputs["apply_cuotas"]:
        t.add_row("  Cuotas sin interés", f"${results['cuotas_fee']:,.0f}", pct(results["cuotas_fee"]))
    t.add_row("  IIBB Mendoza", f"${results['iibb_fee']:,.0f}", pct(results["iibb_fee"]))
    t.add_row("")
    t.add_row(
        "[bold]Margen bruto[/]",
        f"[bold]${results['gross_margin_ars']:,.0f}[/]",
        f"[bold]{results['gross_margin_pct']*100:.1f}%[/]",
    )
    t.add_row("  Envío local", f"${inputs['shipping_ars']:,.0f}", pct(inputs["shipping_ars"]))
    t.add_row("  CPA Meta Ads", f"${inputs['cpa_ars']:,.0f}", pct(inputs["cpa_ars"]))
    t.add_row("")

    net_color = (
        "green" if results["net_margin_pct"] > MARGIN_GREEN_THRESHOLD
        else "yellow" if results["net_margin_pct"] >= MARGIN_YELLOW_THRESHOLD
        else "red"
    )
    t.add_row(
        "[bold]Margen neto[/]",
        f"[bold {net_color}]${results['net_margin_ars']:,.0f}[/]",
        f"[bold {net_color}]{results['net_margin_pct']*100:.1f}%[/]",
    )
    t.add_row("")
    t.add_row(
        "[bold]CPA breakeven[/]",
        f"[bold magenta]${results['cpa_breakeven']:,.0f}[/]",
        "—",
    )

    console.print(t)
    semaforo = _semaforo(results["net_margin_pct"])
    console.print(f"\n[bold]Semáforo:[/] {semaforo}\n")

    if results["cpa_ars"] > results["cpa_breakeven"]:
        console.print(
            "[red]⚠  El CPA ingresado supera el breakeven. "
            f"Máximo CPA permitido: ${results['cpa_breakeven']:,.0f} ARS[/]"
        )


def run() -> None:
    console.rule("[bold cyan]Módulo 3 — Calculadora de margen Argentina[/]")
    console.print("[dim]Presioná Enter para aceptar el valor por defecto entre [corchetes].[/]\n")

    while True:
        cost_usd = _ask_float("Costo del producto en USD", 5.0)
        sale_price_ars = _ask_float("Precio de venta en MercadoLibre (ARS)", 15000.0)
        shipping_ars = _ask_float("Costo de envío local (ARS)", 3000.0)
        cpa_ars = _ask_float("CPA estimado Meta Ads (ARS)", 8000.0)
        usd_to_ars = _ask_float(f"Tipo de cambio USD → ARS", USD_TO_ARS)
        ml_commission = _ask_float("Comisión MercadoLibre (ej: 0.17 = 17%)", ML_COMMISSION_PCT)
        apply_cuotas = console.input(
            f"¿Aplica cuotas sin interés? (s/N) [[bold]N[/]]: "
        ).strip().lower() in ("s", "si", "sí", "y", "yes")
        cuotas_pct = CUOTAS_SIN_INTERES_PCT if apply_cuotas else 0.0
        iibb_pct = _ask_float("IIBB Mendoza (ej: 0.03 = 3%)", IIBB_MENDOZA_PCT)

        inputs = {
            "cost_usd": cost_usd,
            "sale_price_ars": sale_price_ars,
            "shipping_ars": shipping_ars,
            "cpa_ars": cpa_ars,
            "usd_to_ars": usd_to_ars,
            "ml_commission": ml_commission,
            "apply_cuotas": apply_cuotas,
            "iibb_pct": iibb_pct,
        }

        results = _calculate(
            cost_usd=cost_usd,
            sale_price_ars=sale_price_ars,
            shipping_ars=shipping_ars,
            cpa_ars=cpa_ars,
            ml_commission=ml_commission,
            cuotas_pct=cuotas_pct,
            iibb_pct=iibb_pct,
            usd_to_ars=usd_to_ars,
            apply_cuotas=apply_cuotas,
        )

        _print_results(inputs, results)

        again = console.input("¿Calcular otro producto? (s/N): ").strip().lower()
        if again not in ("s", "si", "sí", "y", "yes"):
            break
