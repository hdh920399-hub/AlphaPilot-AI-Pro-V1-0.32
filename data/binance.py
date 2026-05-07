import time
import requests
import pandas as pd
import streamlit as st

# 币安 API 域名列表（451 时自动切换）
BASE_URLS = [
    "https://fapi.binance.com",
    "https://api.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
]

REQUEST_DELAY = 0.05
MAX_RETRIES = 3

# 当前使用的域名索引
_current_url_index = 0


def _get_base_url():
    """获取当前可用的 BASE_URL"""
    global _current_url_index
    return BASE_URLS[_current_url_index]


def _switch_base_url():
    """切换到下一个备用域名"""
    global _current_url_index
    _current_url_index = (_current_url_index + 1) % len(BASE_URLS)
    new_url = BASE_URLS[_current_url_index]
    st.warning(f"⚠️ 切换到备用域名: {new_url}")
    return new_url


def _build_url(path, use_fapi=True):
    """构建完整 URL，支持 fapi 和 api 前缀"""
    base = _get_base_url()
    if use_fapi and "fapi" not in base:
        base = base.replace("api", "fapi") if "fapi" not in base else base
    return f"{base}{path}"


def _make_request(url, params=None, timeout=10):
    """带重试和自动切换域名的请求"""
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=timeout)

            # 451 错误：因法律原因不可用，切换到备用域名
            if resp.status_code == 451:
                st.warning(f"⚠️ 当前域名被限制 (451)，自动切换...")
                _switch_base_url()
                # 重新构建 URL
                old_path = url.replace(_get_base_url(), "")
                for base in BASE_URLS:
                    if base != _get_base_url():
                        url = base + old_path
                        break
                continue

            # 429 错误：请求过于频繁，等待后重试
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 2))
                if attempt < MAX_RETRIES:
                    time.sleep(retry_after)
                    continue
                else:
                    resp.raise_for_status()

            # 其他 HTTP 错误
            resp.raise_for_status()

            time.sleep(REQUEST_DELAY)
            return resp.json()

        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES:
                wait_time = 2 ** attempt
                time.sleep(wait_time)
            else:
                raise e

    return None


@st.cache_data(ttl=30, show_spinner=False)
def get_klines_cached(symbol, interval="4h", limit=200):
    """获取K线数据（带缓存）"""
    try:
        url = _build_url("/fapi/v1/klines", use_fapi=True)
        data = _make_request(
            url,
            params={"symbol": symbol, "interval": interval, "limit": limit}
        )
        if data is None:
            return None

        df = pd.DataFrame(data, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_buy_volume",
            "taker_buy_quote_volume", "ignore"
        ])
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col])
        df.set_index("open_time", inplace=True)
        return df
    except Exception as e:
        st.error(f"K线获取失败 {symbol}: {e}")
        return None


@st.cache_data(ttl=60, show_spinner=False)
def get_all_tickers():
    """一次性获取全部合约最新价格"""
    try:
        url = _build_url("/fapi/v1/ticker/price", use_fapi=True)
        data = _make_request(url)
        if data is None:
            return {}
        return {item["symbol"]: float(item["price"]) for item in data}
    except Exception:
        return {}


def get_current_price(symbol, tickers=None):
    """获取单一价格（支持预取字典）"""
    if tickers and symbol in tickers:
        return tickers[symbol]
    try:
        url = _build_url("/fapi/v1/ticker/price", use_fapi=True)
        data = _make_request(url, params={"symbol": symbol})
        if data and "price" in data:
            return float(data["price"])
        return None
    except Exception:
        return None


def get_price_hybrid(symbol, ws_feed=None, tickers=None):
    """混合价格获取：优先 WebSocket，降级 REST"""
    # 优先 WebSocket 实时价格
    if ws_feed and ws_feed.is_running:
        price = ws_feed.get_price(symbol)
        if price is not None:
            return price
    # 降级到 REST 缓存
    if tickers:
        return tickers.get(symbol)
    return get_current_price(symbol)


@st.cache_data(ttl=300, show_spinner=False)
def get_all_symbols():
    """获取所有 USDT 永续合约交易对"""
    try:
        url = _build_url("/fapi/v1/exchangeInfo", use_fapi=True)
        data = _make_request(url)
        if data is None:
            return _fallback_symbols()
        return [
            s["symbol"] for s in data["symbols"]
            if s["contractType"] == "PERPETUAL" and s["status"] == "TRADING"
        ]
    except Exception:
        return _fallback_symbols()


def _fallback_symbols():
    """API 失败时的备用交易对列表"""
    return [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
        "DOGEUSDT", "ADAUSDT", "XRPUSDT", "LINKUSDT",
        "AVAXUSDT", "MATICUSDT", "TRUMPUSDT", "WIFUSDT",
        "ARBUSDT", "OPUSDT", "SUIUSDT", "APTUSDT",
        "DOTUSDT", "UNIUSDT", "ATOMUSDT", "FILUSDT"
    ]
