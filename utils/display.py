"""
Helpers compartidos de visualización: semáforo de 3 niveles y consola rich.

Centraliza lo que antes estaba duplicado en margin_calc.py y se necesita
ahora también en fb_scraper.py y ml_validator.py.
"""

from rich.console import Console

console = Console()

_LABELS = {
    "green": "[bold green]VERDE ✓[/]",
    "yellow": "[bold yellow]AMARILLO ⚠[/]",
    "red": "[bold red]ROJO ✗[/]",
}


def semaforo_color(value: float, green_threshold: float, yellow_threshold: float) -> str:
    """Clasifica un valor en 'green' / 'yellow' / 'red' según dos umbrales.

    green_threshold y yellow_threshold se comparan con '>' y '>=' respectivamente,
    de forma consistente con el resto de la app (ej: margen, días activo).
    """
    if value > green_threshold:
        return "green"
    elif value >= yellow_threshold:
        return "yellow"
    return "red"


def semaforo_label(color: str) -> str:
    """Devuelve el string rich-formateado (VERDE ✓ / AMARILLO ⚠ / ROJO ✗) para un color."""
    return _LABELS[color]


def semaforo(value: float, green_threshold: float, yellow_threshold: float) -> str:
    """Atajo: calcula el color a partir de umbrales y devuelve la etiqueta formateada."""
    return semaforo_label(semaforo_color(value, green_threshold, yellow_threshold))
