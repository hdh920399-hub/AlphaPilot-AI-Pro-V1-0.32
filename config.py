import os

# ========== 币安 API ==========
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "")

# ========== 费率与滑点 ==========
TRADING_FEE = 0.0004
SLIPPAGE = 0.001

# ========== 大模型配置 ==========
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "zhipu")
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "glm-4-flash")

# ========== 资金池比例 ==========
LONG_BUDGET_RATIO = 0.6
SHORT_BUDGET_RATIO = 0.4

# ========== 排行榜 ==========
MAX_RANKING_DISPLAY = 20
MAX_RANKING_LIMIT = 100

# ========== 数据缓存 ==========
CACHE_TTL = 30
REQUEST_DELAY = 0.05
MAX_RETRIES = 3

# ========== WebSocket 配置 ==========
WS_DEFAULT_SYMBOLS = [
    "btcusdt", "ethusdt", "solusdt", "bnbusdt",
    "dogeusdt", "adausdt", "xrpusdt", "linkusdt",
    "avaxusdt", "maticusdt", "trumpusdt", "wifusdt"
]
WS_MAX_SYMBOLS = 50
WS_PRICE_STALE_SECONDS = 10
WS_RECONNECT_DELAY = 5
WS_MAX_RECONNECT = 10
WS_TARGET_MEMORY_MB = 350
