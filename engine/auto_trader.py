import streamlit as st
from scanner.multi import load_ranking_cached
from data.binance import get_current_price
from engine.ai_signals import calculate_directional_signal
from engine.order_queue import OrderQueueManager


def auto_trade(trader, max_price, max_positions, risk_pct, long_weight, short_weight, sl_pct, tp_pct):
    """自动交易：动态仓位、做多做空均可"""
    ws = st.session_state.ws_feed
    long_df, short_df, _ = load_ranking_cached(max_price, max_positions * 2)
    queue = OrderQueueManager()
    queue.add_candidates(long_df, short_df, long_weight, short_weight)
    opened = 0
    while not queue.is_empty() and opened < max_positions:
        cand = queue.pop()
        sym = cand["symbol"]
        side = cand["side"]
        if sym in trader.holdings: continue
        price = ws.get_price(sym) or get_current_price(sym)
        if price is None: continue
        if st.session_state.circuit_breaker.is_triggered(): break
        result = trader.open_position(sym, side, price, sl_pct, tp_pct)
        opened += 1
    return f"开仓 {opened} 笔"


def auto_open_after_close(trader, max_price, max_positions, long_weight, sl_pct, tp_pct):
    """平仓后自动开新仓"""
    ws = st.session_state.ws_feed
    long_df, short_df, _ = load_ranking_cached(max_price, max_positions * 2)
    queue = OrderQueueManager()
    queue.add_candidates(long_df, short_df, long_weight, 1 - long_weight)
    count = 0
    while not queue.is_empty() and count < 2:  # 平仓后最多补 2 个
        cand = queue.pop()
        sym = cand["symbol"]
        side = cand["side"]
        if sym in trader.holdings: continue
        price = ws.get_price(sym) or get_current_price(sym)
        if price is None: continue
        trader.open_position(sym, side, price, sl_pct, tp_pct)
        count += 1
