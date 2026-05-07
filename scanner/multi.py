import pandas as pd
import streamlit as st
from engine.ai_signals import calculate_directional_signal
from data.binance import get_klines_cached, get_all_tickers, get_all_symbols, get_price_hybrid


def _scan_coins_with_signal_impl(max_price=5.0, limit=20):
    """内部实现：从 session_state 获取 ws_feed，避免哈希问题"""
    symbols = get_all_symbols()
    tickers = get_all_tickers()
    results = []
    
    ws_feed = st.session_state.get("ws_feed")
    
    for sym in symbols:
        if not sym.endswith("USDT"):
            continue
        price = get_price_hybrid(sym, ws_feed=ws_feed, tickers=tickers)
        if price is None or price > max_price:
            continue
        df = get_klines_cached(sym, "4h", limit=80)  # 从 100 减少到 80，加快扫描
        if df is None or len(df) < 50:
            continue
        signal = calculate_directional_signal(df)
        results.append({
            "币种": sym.replace("USDT", ""),
            "价格": round(price, 4),
            "做多分": signal["long_score"],
            "做空分": signal["short_score"],
            "净得分": signal["net_score"],
            "RSI": signal["rsi"],
            "量比": signal["vol_ratio"],
            "信号摘要": signal["action"],
        })
        
        # 提前终止：一旦收集到足够数据就停止
        if len(results) >= limit * 3:
            break
    
    if not results:
        return pd.DataFrame(), pd.DataFrame(), 0
    
    df = pd.DataFrame(results)
    df_long = df.sort_values("做多分", ascending=False).head(limit)
    df_short = df.sort_values("做空分", ascending=False).head(limit)
    return df_long, df_short, len(results)


@st.cache_data(ttl=120, show_spinner="正在扫描市场...")  # TTL 从 60 延长到 120
def scan_cheap_coins_with_signal(max_price=5.0, limit=20):
    """带缓存的扫描函数"""
    return _scan_coins_with_signal_impl(max_price=max_price, limit=limit)


def load_ranking_cached(max_price, limit, ws_feed=None):
    """封装调用，保持接口兼容"""
    return scan_cheap_coins_with_signal(max_price=max_price, limit=limit)


def get_priority_symbols(ranking_df, max_count=40, holdings=None):
    """获取优先订阅的 WebSocket 币种列表"""
    priority = set()
    if holdings:
        for sym in holdings:
            priority.add(sym.upper() if sym.upper().endswith("USDT") else sym.upper() + "USDT")
    if not ranking_df.empty:
        for _, row in ranking_df.iterrows():
            priority.add(row["币种"].upper() + "USDT")
    leaders = {"BTCUSDT", "ETHUSDT", "SOLUSDT"}
    priority.update(leaders)
    return list(priority)[:max_count]
