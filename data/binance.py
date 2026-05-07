import time
import requests
import pandas as pd
import streamlit as st

# 改为备用域名
BASE_URL = "https://fapi.binance.com"
ALT_BASE_URL = "https://api.binance.com"
REQUEST_DELAY = 0.05
MAX_RETRIES = 3


def _make_request(url, params=None, timeout=10):
    """带重试和自动退避的请求"""
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 2))
                if attempt < MAX_RETRIES:
                    time.sleep(retry_after)
                    continue
                else:
                    resp.raise_for_status()
            resp.raise_for_status()
            time.sleep(REQUEST_DELAY)
            return resp.json()
        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)
            else:
                raise e


@st.cache_data(ttl=30, show_spinner=False)
def get_klines_cached(symbol, interval="4h", limit=200):
    """获取K线（带缓存）"""
    try:
        data = _make_request(
            f"{BASE_URL}/fapi/v1/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit}
        )
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
        data = _make_request(f"{BASE_URL}/fapi/v1/ticker/price")
        return {item["symbol"]: float(item["price"]) for item in data}
    except Exception:
        return {}


def get_current_price(symbol, tickers=None):
    """获取单一价格（支持预取字典）"""
    if tickers and symbol in tickers:
        return tickers[symbol]
    try:
        data = _make_request(
            f"{BASE_URL}/fapi/v1/ticker/price",
            params={"symbol": symbol}
        )
        return float(data["price"])
    except Exception:
        return None


def get_price_hybrid(symbol, ws_feed=None, tickers=None):
    """混合价格获取：优先 WebSocket，降级 REST"""
    if ws_feed and ws_feed.is_running:
        price = ws_feed.get_price(symbol)
        if price is not None:
            return price
    if tickers:
        return tickers.get(symbol)
    return get_current_price(symbol)


@st.cache_data(ttl=300, show_spinner=False)
def get_all_symbols():
    """获取所有 USDT 永续合约交易对"""
    try:
        data = _make_request(f"{BASE_URL}/fapi/v1/exchangeInfo")
        return [
            s["symbol"] for s in data["symbols"]
            if s["contractType"] == "PERPETUAL" and s["status"] == "TRADING"
        ]
    except Exception:
        return [
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "ADAUSDT",
            "TRUMPUSDT", "WIFUSDT", "LINKUSDT", "AVAXUSDT", "MATICUSDT"
        ]
