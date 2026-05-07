import streamlit as st
import pandas as pd


def render_asset_card(perf, trader):
    """资产总览卡片"""
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("💰 总资产", f"{perf.get('总资产', 0):,.2f} USDT")
    with col2:
        st.metric("可用余额", f"{trader.balance:,.2f} USDT")
    with col3:
        st.metric("已实现盈亏", f"{perf.get('已实现盈亏', 0):+,.2f} USDT")
    with col4:
        closed_trades = [t for t in trader.trades if t.get("action") == "CLOSE"]
        if closed_trades:
            wins = sum(1 for t in closed_trades if t.get("pnl", 0) > 0)
            st.metric("胜率", f"{wins / len(closed_trades) * 100:.1f}%")
        else:
            st.metric("胜率", "N/A")
    with col5:
        total_lev = sum(p.get("leverage", 1) for p in trader.holdings.values())
        st.metric("杠杆率", f"{total_lev}x" if total_lev > 0 else "0x")


def render_liquidation_panel(trader):
    """强平模拟面板"""
    st.subheader("⚡ 强平模拟")
    
    if not trader.holdings:
        st.info("暂无持仓，无法模拟强平")
        return
    
    if st.button("🔍 计算强平价格", width='stretch'):
        results = []
        for sym, pos in trader.holdings.items():
            entry = pos["avg_price"]
            leverage = pos.get("leverage", 2)
            side = pos["side"]
            
            # 强平价格计算（维持保证金率 0.5%）
            mmr = 0.005  # 维持保证金率
            if side == "LONG":
                liq_price = entry * (1 - 1 / leverage + mmr)
            else:
                liq_price = entry * (1 + 1 / leverage - mmr)
            
            # 当前价格（使用 ws_feed 或开仓价估算）
            ws_feed = st.session_state.get("ws_feed")
            current_price = ws_feed.get_price(sym) if ws_feed else entry
            
            # 距离强平百分比
            if current_price and liq_price > 0:
                if side == "LONG":
                    distance_pct = (current_price - liq_price) / current_price * 100
                else:
                    distance_pct = (liq_price - current_price) / current_price * 100
            else:
                distance_pct = 0
            
            results.append({
                "币种": sym.replace("USDT", ""),
                "方向": "📈 多" if side == "LONG" else "📉 空",
                "开仓价": f"{entry:.6f}",
                "强平价": f"{liq_price:.6f}",
                "杠杆": f"{leverage}x",
                "距强平": f"{distance_pct:.2f}%",
                "风险": "🔴 危险" if distance_pct < 5 else "🟡 注意" if distance_pct < 15 else "🟢 安全"
            })
        
        st.dataframe(pd.DataFrame(results), width='stretch', hide_index=True)
        st.caption("💡 强平价格基于维持保证金率 0.5% 计算，实际以币安为准。距强平 <5% 为危险，5-15% 需注意。")
