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

# Países donde se buscan los anuncios
AD_REACHED_COUNTRIES = ["US"]

# Anuncios creados hace al menos N días (si llevan meses pagando = convierte)
MIN_DAYS_ACTIVE = 90

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
