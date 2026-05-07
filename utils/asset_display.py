import streamlit as st


def render_asset_card(perf, trader):
    """渲染资产总览卡片"""
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("总资产", f"{perf.get('总资产', 0):.2f} USDT")
    with col2:
        st.metric("可用余额", f"{trader.balance:.2f} USDT")
    with col3:
        st.metric("已实现盈亏", f"{perf.get('已实现盈亏', 0):+.2f} USDT")
    with col4:
        closed = [t for t in trader.trades if t.get("action") == "CLOSE"]
        if closed:
            wins = sum(1 for t in closed if t["pnl"] > 0)
            st.metric("胜率", f"{wins / len(closed) * 100:.1f}%")
        else:
            st.metric("胜率", "N/A")
    with col5:
        lev = sum(p.get("leverage", 1) for p in trader.holdings.values())
        st.metric("杠杆率", f"{lev}x")

    # 强平价格估算
    if trader.holdings:
        for sym, pos in trader.holdings.items():
            lev = pos.get("leverage", 1)
            if lev > 0:
                if pos["side"] == "LONG":
                    liq_price = pos["avg_price"] * (1 - 1 / lev)
                else:
                    liq_price = pos["avg_price"] * (1 + 1 / lev)
                st.caption(f"🔸 {sym} 强平估算: {liq_price:.4f}")
