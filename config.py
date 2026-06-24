# ecommR — Configuración central
# Modificá estos valores sin tocar el código de los módulos.

# ─── Módulo 1: FB Ad Library ───────────────────────────────────────────────
FB_API_VERSION = "v25.0"
FB_ADS_ARCHIVE_ENDPOINT = "https://graph.facebook.com/{version}/ads_archive"

KEYWORDS = [
    "pain relief",
    "back pain",
    "posture corrector",
    "knee pain",
    "sleep better",
    "hair loss",
    "organize home",
    "pet hair",
    "phone mount",
    "kitchen gadget",
    "neck pain",
    "foot pain",
    "weight loss",
    "skin care",
    "eye strain",
    "baldness",
    "snore",
    "anxiety relief",
    "joint pain",
    "cable management",
]

# Países donde se buscan los anuncios (mercado principal)
AD_REACHED_COUNTRIES = ["US"]

# Países adicionales para detectar señal de expansión multi-mercado.
# Se consulta solo para los candidatos que ya superan el umbral amarillo
# (ver utils/scoring.py), y como máximo MULTI_GEO_CHECK_LIMIT páginas por
# corrida, para no multiplicar las llamadas a la API.
MULTI_GEO_CHECK_COUNTRIES = ["GB", "AU"]
MULTI_GEO_CHECK_LIMIT = 15

# El umbral mínimo de días activo para incluir un anuncio ahora vive en
# utils/scoring.py (PERSISTENCE_YELLOW_DAYS) junto con el resto del scoring
# de 3 niveles, para no tener dos fuentes de verdad distintas.

# Máximo de anuncios por keyword (None = todos)
MAX_ADS_PER_KEYWORD = None

# Campos que devuelve la API
AD_FIELDS = "id,ad_creation_time,ad_snapshot_url,page_name"

# Nombre del CSV de salida
FB_OUTPUT_FILENAME = "fb_ads_results.csv"

# ─── Módulo 2: Store Analyzer ──────────────────────────────────────────────
# Tiempo máximo de espera por request (segundos)
REQUEST_TIMEOUT = 15

# User-Agent para el scraper
SCRAPER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# ─── Módulo 3: Calculadora de margen ──────────────────────────────────────
# Tipo de cambio USD → ARS (actualizá manualmente o conectá a una API)
USD_TO_ARS = 1200.0

# Comisiones y costos por defecto (editables al correr el módulo)
ML_COMMISSION_PCT = 0.17        # MercadoLibre 17%
CUOTAS_SIN_INTERES_PCT = 0.19  # Cuotas sin interés 19%
IIBB_MENDOZA_PCT = 0.03         # IIBB Mendoza 3%

# Umbrales del semáforo
MARGIN_GREEN_THRESHOLD = 0.30   # > 30% → VERDE
MARGIN_YELLOW_THRESHOLD = 0.15  # 15-30% → AMARILLO
                                  # < 15% → ROJO

# ─── Módulo 4: Comparador Trends AR vs US ─────────────────────────────────
# pytrends está sin mantenimiento (archivado desde abril 2025) y propenso a
# 429 sin proxies. Estos valores controlan la ventana de comparación y los
# reintentos antes de caer al link manual de Google Trends.
TRENDS_TIMEFRAME = "today 12-m"
TRENDS_HL = "en-US"
TRENDS_TZ = 360
TRENDS_GEO_AR = "AR"
TRENDS_GEO_US = "US"
TRENDS_RETRY_DELAYS = [5, 15]  # segundos entre reintentos tras el primer intento

# ─── Módulo 5: Validador de demanda MercadoLibre ──────────────────────────
ML_SITE_ID = "MLA"  # MLA = Argentina
ML_SEARCH_ENDPOINT = "https://api.mercadolibre.com/sites/{site_id}/search"
ML_USER_ENDPOINT = "https://api.mercadolibre.com/users/{seller_id}"

# Cantidad de resultados a traer por búsqueda
ML_SEARCH_LIMIT = 50

# A cuántos de los primeros vendedores se les consulta reputación
ML_TOP_N_SELLER_REPUTATION = 5

# Tope de permalinks a scrapear buscando texto "vendidos" (best-effort,
# riesgo de bloqueo de IP — por eso se mantiene bajo y es opt-in)
ML_VENDIDOS_SCRAPE_CAP = 3
