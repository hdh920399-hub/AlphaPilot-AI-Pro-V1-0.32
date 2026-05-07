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
from utils.asset_display import render_asset_card, render_liquidation_panel
from utils.preload import preload

# ========== 页面配置 ==========
st.set_page_config(
    page_title="AlphaPilot AI v0.35",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========== Session State 安全初始化（只设置默认值，不绑定控件） ==========
# 原则：控件只传 key，默认值统一在这里设置，控件不传 value/index
def init_session(key, default):
    if key not in st.session_state:
        st.session_state[key] = default

init_session("capital", 100.0)
init_session("max_price", 5.0)
init_session("stop_loss_pct", 2.0)
init_session("take_profit_pct", 5.0)
init_session("long_weight", 0.6)
init_session("auto_interval", 60)
init_session("max_positions", 5)
init_session("risk_pct", 5.0)
init_session("enable_llm", True)
init_session("max_leverage", 3)
init_session("single_coin_limit", 15.0)
init_session("ranking_limit", 20)
init_session("auto_refresh", True)
init_session("custom_symbol", "")
init_session("custom_input", "")
init_session("selected_symbol", "BTCUSDT")
init_session("interval", "4h")
init_session("daily_report", "")
init_session("liquidation_msg", "")

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

# ========== 侧边栏（问题5修复：所有控件不传 value/index，只传 key） ==========
with st.sidebar:
    st.title("⚙️ AlphaPilot v0.35")
    
    st.number_input("💰 虚拟本金", min_value=10.0, step=10.0, key="capital")
    st.number_input("💲 最高价筛选 (USDT)", min_value=0.1, step=0.1, key="max_price")
    
    st.markdown("---")
    st.subheader("⚖️ 多空配置")
    st.slider("做多权重", 0.0, 1.0, key="long_weight")
    st.caption(f"做空权重自动: {1 - st.session_state.long_weight:.0%}")
    
    st.markdown("---")
    st.subheader("🛡️ 风控参数")
    st.slider("止损 (%)", 0.5, 10.0, key="stop_loss_pct")
    st.slider("止盈 (%)", 1.0, 30.0, key="take_profit_pct")
    st.selectbox("最大杠杆", [1, 2, 3, 5], key="max_leverage")
    st.slider("单币上限 (%)", 5.0, 30.0, key="single_coin_limit")
    
    st.markdown("---")
    st.subheader("🤖 自动交易")
    st.checkbox("启用自动刷新", key="auto_refresh")
    st.selectbox("扫描间隔(秒)", [30, 60, 120], key="auto_interval")
    st.checkbox("启用大模型复盘", key="enable_llm")
    
    st.markdown("---")
    st.subheader("📋 排行榜设置")
    st.slider("展示数量", 10, 100, key="ranking_limit")
    
    st.markdown("---")
    ws_feed_obj = st.session_state.ws_feed
    st.caption(f"📡 WS: {ws_feed_obj.get_connection_status()} | 订阅: {len(ws_feed_obj.subscribed_symbols)}")
    st.caption(f"💾 内存: {get_memory_mb():.0f}MB / 512MB")

# ========== 侧边栏参数提取（供后续使用） ==========
capital = st.session_state.capital
max_price = st.session_state.max_price
long_weight = st.session_state.long_weight
stop_loss_pct = st.session_state.stop_loss_pct / 100
take_profit_pct = st.session_state.take_profit_pct / 100
max_leverage = st.session_state.max_leverage
single_coin_limit = st.session_state.single_coin_limit / 100
auto_refresh = st.session_state.auto_refresh
auto_interval = st.session_state.auto_interval
enable_llm = st.session_state.enable_llm
ranking_limit = st.session_state.ranking_limit

# ========== 主界面 ==========
st.title("🚀 AlphaPilot AI v0.35 — 量化交易终端")
st.caption("v0.35：布局重构 · 强平模拟 · 资产/K线调换 · 币安风格 · Session State 彻底修复")

# ========== 数据加载 ==========
long_df, short_df, total_count = load_ranking_cached(max_price, ranking_limit)
perf = calculate_performance(st.session_state.trader)
ws_feed_obj = st.session_state.ws_feed

# 动态更新 WebSocket 订阅
priority_symbols = get_priority_symbols(long_df)
if not short_df.empty:
    for sym in get_priority_symbols(short_df):
        if sym not in priority_symbols:
            priority_symbols.append(sym)
ws_feed_obj.update_symbols(priority_symbols[:WS_MAX_SYMBOLS])

# ========== 第1板块：龙头识别（问题2修复：从排行榜动态获取） ==========
st.subheader("🏆 龙头识别 (排行榜 Top 3)")

col_leader_long, col_leader_short = st.columns(2)

with col_leader_long:
    st.markdown("**📈 多头龙头**")
    if not long_df.empty:
        top3_long = long_df.head(3)
        for _, row in top3_long.iterrows():
            sym = row["币种"] + "USDT"
            price = ws_feed_obj.get_price(sym) or row["价格"]
            change = ws_feed_obj.get_price_change(sym)
            col_name, col_price, col_score = st.columns([2, 2, 1])
            col_name.markdown(f"**{row['币种']}**")
            col_price.metric("价格", f"{price:,.4f}" if price < 1 else f"{price:,.2f}",
                           f"{change:+.2f}%" if change else "",
                           delta_color="normal" if (change or 0) >= 0 else "inverse")
            col_score.metric("评分", f"{row['做多分']:.0f}")
    else:
        st.info("等待扫描...")

with col_leader_short:
    st.markdown("**📉 空头龙头**")
    if not short_df.empty:
        top3_short = short_df.head(3)
        for _, row in top3_short.iterrows():
            sym = row["币种"] + "USDT"
            price = ws_feed_obj.get_price(sym) or row["价格"]
            change = ws_feed_obj.get_price_change(sym)
            col_name, col_price, col_score = st.columns([2, 2, 1])
            col_name.markdown(f"**{row['币种']}**")
            col_price.metric("价格", f"{price:,.4f}" if price < 1 else f"{price:,.2f}",
                           f"{change:+.2f}%" if change else "",
                           delta_color="normal" if (change or 0) >= 0 else "inverse")
            col_score.metric("评分", f"{row['做空分']:.0f}")
    else:
        st.info("等待扫描...")

# ========== 第2板块：K线分析（问题3修复：K线在账户情况下方） ==========
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
        selected_label = st.selectbox("排行榜币种", options_list, index=idx, key="rank_sel")
        st.session_state.selected_symbol = selected_label.split(" (")[0] + "USDT"
    else:
        st.session_state.selected_symbol = "BTCUSDT"

with col_search:
    custom_input = st.text_input(
        "🔍 自定义币种",
        value=st.session_state.custom_input,
        placeholder="如 DOGEUSDT",
        key="custom_input"
    ).upper().strip()
    if custom_input:
        if not custom_input.endswith("USDT"):
            custom_input += "USDT"
        st.session_state.custom_symbol = custom_input
        st.session_state.selected_symbol = custom_input

with col_interval:
    st.selectbox("K线周期", ["15m", "1h", "4h", "1d"], key="interval")

selected_symbol = st.session_state.selected_symbol
interval = st.session_state.interval

st.caption(f"📌 当前分析: {selected_symbol} | {interval}")

df = get_klines_cached(selected_symbol, interval, 200)
if df is not None and len(df) >= 20:
    col_chart, col_signal = st.columns([2.2, 1])
    with col_chart:
        fig = create_pro_chart(df, selected_symbol, interval)
        st.plotly_chart(fig, width='stretch')
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

# ========== 第3板块：账户情况（含强平模拟）+ 多空排行榜 ==========
st.markdown("---")

# --- 账户情况（问题3修复：全宽布局） ---
st.subheader("💰 账户总览")
render_asset_card(perf, st.session_state.trader)

# --- 强平模拟（问题7新增） ---
st.markdown("---")
render_liquidation_panel(st.session_state.trader)

# --- 多空排行榜 ---
st.markdown("---")
st.subheader("📊 多空排行榜")

col_left, col_right = st.columns(2)
with col_left:
    st.write(f"**做多潜力榜** (前 {len(long_df)} / 共 {total_count})")
    if not long_df.empty:
        st.dataframe(
            long_df[["币种", "价格", "做多分", "RSI", "量比", "信号摘要"]],
            width='stretch', hide_index=True
        )
    else:
        st.info("暂无符合条件的做多币种")

with col_right:
    st.write(f"**做空潜力榜** (前 {len(short_df)} / 共 {total_count})")
    if not short_df.empty:
        st.dataframe(
            short_df[["币种", "价格", "做空分", "RSI", "量比", "信号摘要"]],
            width='stretch', hide_index=True
        )
    else:
        st.info("暂无符合条件的做空币种")

# ========== 第4板块：持仓与交易历史（问题4修复：币安风格） ==========
st.markdown("---")
col_hold, col_trade = st.columns(2)

with col_hold:
    st.subheader("📋 当前持仓")
    if st.session_state.trader.holdings:
        hold_data = []
        for s, p in st.session_state.trader.holdings.items():
            hold_data.append({
                "币种": s.replace("USDT", ""),
                "方向": "📈 多" if p["side"] == "LONG" else "📉 空",
                "开仓价": f"{p['avg_price']:.6f}",
                "数量": p["quantity"],
                "止损": f"{p['stop_loss']:.6f}",
                "止盈": f"{p['take_profit']:.6f}",
                "杠杆": f"{p['leverage']}x"
            })
        st.dataframe(pd.DataFrame(hold_data), width='stretch', hide_index=True)
    else:
        st.info("暂无持仓")

with col_trade:
    st.subheader("📝 交易历史")
    if st.session_state.trader.trades:
        trade_data = []
        for t in st.session_state.trader.trades[-20:]:
            trade_data.append({
                "时间": t.get("timestamp", ""),
                "币种": t.get("symbol", "").replace("USDT", ""),
                "方向": t.get("side", ""),
                "盈亏": f"{t.get('pnl', 0):+.2f} USDT"
            })
        st.dataframe(pd.DataFrame(trade_data), width='stretch', hide_index=True)
    else:
        st.info("暂无交易记录")

# ========== 第5板块：AI 每日复盘 ==========
st.markdown("---")
st.subheader("🤖 AI 每日复盘")

if enable_llm:
    col_btn, col_status = st.columns([1, 3])
    with col_btn:
        if st.button("🔄 生成复盘报告", width='stretch'):
            with st.spinner("AI 分析中..."):
                report = generate_daily_llm_report(
                    st.session_state.trader,
                    perf,
                    st.session_state.regime_detector.get_regime_summary(),
                    long_df
                )
                st.session_state.daily_report = report
    with col_status:
        if st.session_state.daily_report:
            st.success("✅ 报告已生成")
        else:
            st.caption("点击按钮生成 AI 复盘（需配置 ZHIPU_API_KEY）")
    
    if st.session_state.daily_report:
        st.markdown("---")
        st.markdown(st.session_state.daily_report)
else:
    st.caption("请在侧边栏启用大模型复盘")

# ========== 第6板块：状态栏 ==========
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
                stop_loss_pct=st.session_state.stop_loss_pct / 100,
                take_profit_pct=st.session_state.take_profit_pct / 100,
            )
            st.toast(f"🤖 {result}")
        else:
            st.toast("🛑 熔断触发，暂停自动交易")

        st.session_state.auto_trade_last_time = now
        time.sleep(1)
        st.rerun()
