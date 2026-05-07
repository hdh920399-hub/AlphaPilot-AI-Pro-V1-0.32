import streamlit as st
from data.binance import get_price_hybrid
from engine.order_queue import OrderQueueManager


def auto_trade(trader, max_price=5.0, max_positions=5, risk_pct=5,
               long_weight=0.6, short_weight=0.4,
               stop_loss_pct=0.05, take_profit_pct=0.15, use_queue=True):
    """自动交易，使用实时价格"""
    from scanner.multi import load_ranking_cached

    ws_feed = st.session_state.get("ws_feed")
    long_df, short_df, _ = load_ranking_cached(max_price, limit=st.session_state.ranking_limit, ws_feed=ws_feed)

    budget = st.session_state.budget_manager
    long_budget_ok = budget.get_long_budget() > 0
    short_budget_ok = budget.get_short_budget() > 0

    queue = OrderQueueManager()
    queue.add_candidates(long_df, short_df, long_weight, short_weight)

    opened = 0
    while not queue.is_empty() and opened < max_positions:
        candidate = queue.pop()
        side = candidate["side"]
        symbol = candidate["symbol"]

        price = get_price_hybrid(symbol, ws_feed=ws_feed)
        if price is None:
            continue
        if st.session_state.circuit_breaker.is_triggered():
            break
        if side == "LONG" and long_budget_ok:
            trader.open_position(symbol, "LONG", price, stop_loss_pct, take_profit_pct)
            opened += 1
        elif side == "SHORT" and short_budget_ok:
            trader.open_position(symbol, "SHORT", price, stop_loss_pct, take_profit_pct)
            opened += 1

    return f"自动交易完成，开仓 {opened} 笔"
