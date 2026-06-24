"""
Scoring de señales de anuncios (Meta Ad Library) — usado por fb_scraper.py.

Señales FUERTES que sí se pueden medir con los campos públicos de la API:
  - Persistencia: el anuncio sigue activo después de muchos días (gasto sostenido).
  - Expansión multi-país: la misma página corre anuncios en más de un mercado.
  - Variedad creativa: la página tiene varios anuncios/creativos distintos.

Señales del handover que NO se incluyen en el score porque no son medibles
de forma confiable con los campos públicos de ads_archive (sin spend/impresiones
ni histórico de anuncios inactivos):
  - "Spike de 7 días y desaparece" — requeriría snapshots históricos del anuncio
    (la API solo devuelve el estado ACTIVO actual, no su historia).
  - Catálogo DPA multi-SKU — requeriría el campo dpa_ad/dpa_product_catalog,
    no incluido en AD_FIELDS.
  - Lanzamiento financiado con VC — no es un dato observable vía API.
"""

PERSISTENCE_GREEN_DAYS = 90
PERSISTENCE_YELLOW_DAYS = 45
CREATIVE_VARIETY_THRESHOLD = 5


def score_signals(days_active: int, multi_geo: bool, creative_variety: int) -> dict:
    """Combina señales de una página/anunciante en un tier (green/yellow/red).

    Regla:
      - green:  > 90 días activo Y (expansión multi-país O 5+ creativos distintos)
      - yellow: >= 45 días activo (sin cumplir el combo completo de green)
      - red:    < 45 días activo
    """
    has_bonus_signal = multi_geo or creative_variety >= CREATIVE_VARIETY_THRESHOLD

    if days_active > PERSISTENCE_GREEN_DAYS and has_bonus_signal:
        tier = "green"
    elif days_active >= PERSISTENCE_YELLOW_DAYS:
        tier = "yellow"
    else:
        tier = "red"

    return {
        "tier": tier,
        "days_active": days_active,
        "multi_geo": multi_geo,
        "creative_variety": creative_variety,
        "has_bonus_signal": has_bonus_signal,
    }
