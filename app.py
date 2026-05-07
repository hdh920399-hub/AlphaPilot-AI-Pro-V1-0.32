import streamlit as st
import time
import datetime
import pandas as pd
import psutil
import os

from config import *
from data.binance import get_klines_cached
from data.websocket_feed import BinanceWebSocketFeed
from scanner.multi import load_ranking_cached, get_priority_symbols
from engine.ai_signals import calculate_directional_signal
from engine.auto_trader import auto_trade
from engine.risk_manager import CircuitBreaker, BudgetManager
from engine.regime_detector import RegimeDetector
from risk.portfolio import SimulatedTrader
from analysis.daily_summary import calculate_performance
from analysis.llm_report import generate_daily_llm_report
from ui.chart import create_pro_chart
from utils.asset_display import render_asset_card
from utils.preload import preload

# ========== 页面配置 ==========
st.set_page_config(
    page_title="AlphaPilot AI v0.33",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========== Session State 安全初始化 ==========
DEFAULTS = {
    "capital": 100.0,
    "max_price": 5.0,
    "stop_loss_pct": 2.0,
    "take_profit_pct": 5.0,
    "long_weight": 0.6,
    "auto_interval": 60,
    "max_positions": 5,
    "risk_pct": 5.0,
    "enable_llm": True,
    "max_leverage": 3,
    "single_coin_limit": 15.0,
    "ranking_limit": MAX_RANKING_DISPLAY,
    "custom_symbol": "",
    "custom_input": "",
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

# 核心对象（只初始化一次）
if "trader" not in st.session_state:
    st.session_state.trader = SimulatedTrader(st.session_state.capital)
if "budget_manager" not in st.session_state:
    st.session_state.budget_manager = BudgetManager(
        st.session_state.capital, LONG_BUDGET_RATIO, SHORT_BUDGET_RATIO
    )
if "circuit_breaker" not in st.session_state:
    st.session_state.circuit_breaker = CircuitBreaker()
if "regime_detector" not in st.session_state:
    st.session_state.regime_detector = RegimeDetector()
if "auto_trade_last_time" not in st.session_state:
    st.session_state.auto_trade_last_time = datetime.datetime.now()
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = True
if "ws_feed" not in st.session_state:
    st.session_state.ws_feed = BinanceWebSocketFeed()
    st.session_state.ws_feed.start()

preload()

# ========== 内存监控 ==========
def get_memory_mb():
    try:
        return psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
    except:
        return 0

# ========== 侧边栏 ==========
st.sidebar.title("⚙️ AlphaPilot v0.33")

capital = st.sidebar.number_input("💰 虚拟本金", min_value=10.0, step=10.0, key="capital")
max_price = st.sidebar.number_input("💲 最高价筛选 (USDT)", min_value=0.1, step=0.1, key="max_price")

st.sidebar.markdown("---")
st.sidebar.subheader("⚖️ 多空配置")
long_weight = st.sidebar.slider("做多权重", 0.0, 1.0, key="long_weight")
st.sidebar.caption(f"做空权重自动: {1 - long_weight:.0%}")

st.sidebar.markdown("---")
st.sidebar.subheader("🛡️ 风控参数")
stop_loss_pct = st.sidebar.slider("止损 (%)", 0.5, 10.0, key="stop_loss_pct") / 100
take_profit_pct = st.sidebar.slider("止盈 (%)", 1.0, 30.0, key="take_profit_pct") / 100
max_leverage = st.sidebar.selectbox("最大杠杆", [1, 2, 3, 5], index=2, key="max_leverage")
single_coin_limit = st.sidebar.slider("单币上限 (%)", 5.0, 30.0, key="single_coin_limit") / 100

st.sidebar.markdown("---")
st.sidebar.subheader("🤖 自动交易")
auto_refresh = st.sidebar.checkbox("启用自动刷新", key="auto_refresh")
auto_interval = st.sidebar.selectbox("扫描间隔(秒)", [30, 60, 120], index=1, key="auto_interval")
enable_llm = st.sidebar.checkbox("启用大模型复盘", key="enable_llm")

st.sidebar.markdown("---")
st.sidebar.subheader("📋 排行榜设置")
ranking_limit = st.sidebar.slider("展示数量", 10, 100, key="ranking_limit")

# 状态栏
ws_feed_obj = st.session_state.ws_feed
st.sidebar.markdown("---")
st.sidebar.caption(f"📡 WS: {ws_feed_obj.get_connection_status()} | 订阅: {len(ws_feed_obj.subscribed_symbols)}")
st.sidebar.caption(f"💾 内存: {get_memory_mb():.0f}MB / 512MB")

# ========== 主界面 ==========
st.title("🚀 AlphaPilot AI v0.33 — 量化交易终端")
st.caption("v0.33：布局优化 · AI复盘增强 · Session State 无警告 · 专业K线 · 多空排行榜")

# ========== 第1板块：龙头识别（顶部实时行情） ==========
st.subheader("🏆 龙头识别 (WebSocket 实时)")
col_leader_long, col_leader_short = st.columns(2)

with col_leader_long:
    st.markdown("**多头龙头**")
    for name, sym in [("BTC", "BTCUSDT"), ("ETH", "ETHUSDT"), ("SOL", "SOLUSDT"), ("BNB", "BNBUSDT")]:
        price = ws_feed_obj.get_price(sym)
        change = ws_feed_obj.get_price_change(sym)
        if price:
            st.metric(f"{name}", f"{price:,.2f}", f"{change:+.2f}%",
                      delta_color="normal" if change >= 0 else "inverse")
        else:
            st.metric(f"{name}", "---")

with col_leader_short:
    st.markdown("**空头龙头**")
    for name, sym in [("TRUMP", "TRUMPUSDT"), ("WIF", "WIFUSDT"), ("ADA", "ADAUSDT"), ("DOGE", "DOGEUSDT")]:
        price = ws_feed_obj.get_price(sym)
        change = ws_feed_obj.get_price_change(sym)
        if price:
            st.metric(f"{name}", f"{price:,.4f}", f"{change:+.2f}%",
                      delta_color="normal" if change >= 0 else "inverse")
        else:
            st.metric(f"{name}", "---")

# ========== 第2板块：资产总览 ==========
st.markdown("---")
perf = calculate_performance(st.session_state.trader)
render_asset_card(perf, st.session_state.trader)

# ========== 第3板块：多空排行榜 ==========
st.markdown("---")
st.subheader("📊 多空排行榜")

long_df, short_df, total_count = load_ranking_cached(max_price, ranking_limit)

priority_symbols = get_priority_symbols(long_df)
if not short_df.empty:
    for sym in get_priority_symbols(short_df):
        if sym not in priority_symbols:
            priority_symbols.append(sym)
ws_feed_obj.update_symbols(priority_symbols[:WS_MAX_SYMBOLS])

col_left, col_right = st.columns(2)
with col_left:
    st.write(f"**做多潜力榜** (前 {len(long_df)} / 共 {total_count})")
    if not long_df.empty:
        st.dataframe(long_df[["币种", "价格", "做多分", "RSI", "量比", "信号摘要"]],
                     use_container_width=True, hide_index=True)
    else:
        st.info("暂无符合条件的做多币种")

with col_right:
    st.write(f"**做空潜力榜** (前 {len(short_df)} / 共 {total_count})")
    if not short_df.empty:
        st.dataframe(short_df[["币种", "价格", "做空分", "RSI", "量比", "信号摘要"]],
                     use_container_width=True, hide_index=True)
    else:
        st.info("暂无符合条件的做空币种")

# ========== 第4板块：专业K线分析 ==========
st.markdown("---")
st.subheader("📈 专业K线分析")

col_sel, col_search, col_interval = st.columns([2, 1.5, 1])
with col_sel:
    if not long_df.empty:
        options_list = [f"{r['币种']} (多:{r['做多分']})" for _, r in long_df.iterrows()]
        idx = 0
        if st.session_state.custom_symbol:
            clean = st.session_state.custom_symbol.replace("USDT", "")
            idx = next((i for i, o in enumerate(options_list) if o.startswith(clean)), 0)
        selected_symbol = st.selectbox("排行榜币种", options_list, index=idx, key="rank_sel").split(" (")[0] + "USDT"
    else:
        selected_symbol = "BTCUSDT"

with col_search:
    custom_input = st.text_input("🔍 自定义币种", key="custom_input", placeholder="如 DOGEUSDT").upper().strip()
    if custom_input:
        if not custom_input.endswith("USDT"):
            custom_input += "USDT"
        st.session_state.custom_symbol = custom_input
        selected_symbol = custom_input

with col_interval:
    interval = st.selectbox("K线周期", ["15m", "1h", "4h", "1d"], index=2, key="interval")

st.caption(f"📌 当前分析: {selected_symbol} | {interval}")

df = get_klines_cached(selected_symbol, interval, 200)
if df is not None and len(df) >= 20:
    col_chart, col_signal = st.columns([2.2, 1])
    with col_chart:
        fig = create_pro_chart(df, selected_symbol, interval)
        st.plotly_chart(fig, use_container_width=True)
    with col_signal:
        st.subheader("🤖 AI 实时信号")
        if len(df) >= 50:
            signal = calculate_directional_signal(df)
            if "做多" in signal["action"]:
                st.success(f"### {signal['action']}")
            elif "做空" in signal["action"]:
                st.error(f"### {signal['action']}")
            else:
                st.info(f"### {signal['action']}")
            c1, c2, c3 = st.columns(3)
            c1.metric("净得分", signal["net_score"])
            c2.metric("做多评分", signal["long_score"])
            c3.metric("做空评分", signal["short_score"])
            st.caption(f"📊 RSI: {signal['rsi']} | 量比: {signal['vol_ratio']}")
            with st.expander("📋 评分理由与操作建议", expanded=True):
                st.markdown(signal["analysis"])
        else:
            st.info("K线数据不足（需≥50根），无法计算信号")
else:
    st.warning("K线数据加载失败，请稍后重试")

# ========== 第5板块：持仓与交易记录 ==========
st.markdown("---")
col_hold, col_trade = st.columns(2)
with col_hold:
    st.subheader("📋 当前持仓")
    if st.session_state.trader.holdings:
        df_hold = pd.DataFrame([
            {"币种": s, "方向": p["side"], "开仓价": p["avg_price"],
             "数量": p["quantity"], "止损": p["stop_loss"],
             "止盈": p["take_profit"], "杠杆": p["leverage"]}
            for s, p in st.session_state.trader.holdings.items()
        ])
        st.dataframe(df_hold, use_container_width=True, hide_index=True)
    else:
        st.info("暂无持仓")

with col_trade:
    st.subheader("📝 交易历史")
    if st.session_state.trader.trades:
        st.dataframe(pd.DataFrame(st.session_state.trader.trades[-10:]),
                     use_container_width=True, hide_index=True)
    else:
        st.info("暂无交易记录")

# ========== 第6板块：AI 每日复盘 ==========
st.markdown("---")
st.subheader("🤖 AI 每日复盘")

if enable_llm:
    col_report_btn, col_report_status = st.columns([1, 3])
    with col_report_btn:
        if st.button("🔄 生成复盘报告", use_container_width=True):
            with st.spinner("AI 分析中..."):
                report = generate_daily_llm_report(
                    st.session_state.trader,
                    perf,
                    st.session_state.regime_detector.get_regime_summary(),
                    long_df
                )
                st.session_state.daily_report = report
    with col_report_status:
        if "daily_report" in st.session_state and st.session_state.daily_report:
            st.success("✅ 报告已生成（见下方）")
        else:
            st.caption("点击按钮生成 AI 复盘（需配置 ZHIPU_API_KEY 环境变量）")

    if "daily_report" in st.session_state and st.session_state.daily_report:
        st.markdown("---")
        st.markdown(st.session_state.daily_report)
else:
    st.caption("请在侧边栏启用大模型复盘")

# ========== 状态栏 ==========
st.markdown("---")
col_st1, col_st2, col_st3, col_st4 = st.columns(4)
with col_st1:
    st.metric("⚡ 市场状态", st.session_state.regime_detector.get_regime_summary())
with col_st2:
    cb = st.session_state.circuit_breaker
    st.metric("🛡️ 熔断状态", "🔴 已触发" if cb.is_triggered() else "🟢 正常")
with col_st3:
    st.metric("📡 WebSocket", ws_feed_obj.get_connection_status())
with col_st4:
    st.metric("💾 内存", f"{get_memory_mb():.0f}MB")

# ========== 自动交易守护 ==========
if auto_refresh:
    now = datetime.datetime.now()
    delta = (now - st.session_state.auto_trade_last_time).total_seconds()
    if delta >= auto_interval:
        cb = st.session_state.circuit_breaker
        cb.reset_daily_if_new_day(now.date())

        daily_start = getattr(st.session_state, 'daily_start_equity', perf["总资产"])
        if ('daily_start_equity' not in st.session_state or
                st.session_state.get('last_reset_date') != now.date()):
            st.session_state.daily_start_equity = perf["总资产"]
            st.session_state.last_reset_date = now.date()

        daily_pnl = perf["总资产"] - st.session_state.daily_start_equity
        cb.update(daily_pnl, perf["总资产"])

        if not cb.is_triggered():
            result = auto_trade(
                st.session_state.trader,
                max_price=st.session_state.max_price,
                max_positions=st.session_state.max_positions,
                risk_pct=st.session_state.risk_pct,
                long_weight=long_weight,
                short_weight=1 - long_weight,
                stop_loss_pct=st.session_state.stop_loss_pct,
                take_profit_pct=st.session_state.take_profit_pct,
            )
            st.toast(f"🤖 {result}")
        else:
            st.toast("🛑 熔断触发，暂停自动交易")

        st.session_state.auto_trade_last_time = now
        time.sleep(1)
        st.rerun()
