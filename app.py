import streamlit as st
import time, datetime, pandas, os, psutil, json

from config import *
from data.binance import get_klines_cached, get_current_price
from data.websocket_feed import BinanceWebSocketFeed
from scanner.multi import load_ranking_cached, get_priority_symbols
from engine.ai_signals import calculate_directional_signal
from engine.auto_trader import auto_trade, auto_open_after_close
from engine.risk_manager import CircuitBreaker, BudgetManager
from engine.regime_detector import RegimeDetector
from risk.portfolio import SimulatedTrader
from analysis.daily_summary import calculate_performance
from analysis.llm_report import generate_daily_llm_report
from ui.chart import create_pro_chart
from utils.asset_display import render_asset_card
from utils.preload import preload

st.set_page_config(page_title="AlphaPilot AI v0.36", layout="wide", initial_sidebar_state="expanded")

# ==================== Session State 安全初始化 ====================
def init(key, default):
    if key not in st.session_state:
        st.session_state[key] = default

init("capital", 1000.0)
init("max_price", 8.0)
init("stop_loss_pct", 2.84)
init("take_profit_pct", 8.02)
init("long_weight", 0.6)
init("auto_interval", 60)
init("risk_pct", 5.0)
init("enable_llm", True)
init("max_leverage", 5)
init("single_coin_limit", 17.70)
init("ranking_limit", 32)
init("auto_refresh", True)
init("custom_symbol", "")
init("custom_input", "")
init("selected_symbol", "BTCUSDT")
init("interval", "4h")
init("daily_report", "")

# 预算管理
init("long_budget", st.session_state.capital * LONG_BUDGET_RATIO)
init("short_budget", st.session_state.capital * SHORT_BUDGET_RATIO)

# 核心对象
if "trader" not in st.session_state:
    st.session_state.trader = SimulatedTrader(st.session_state.capital)
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

# ==================== 内存监控 ====================
def get_memory_mb():
    try: return psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
    except: return 0

# ==================== 动态仓位计算 ====================
def calc_max_positions(capital, max_price, leverage):
    per_position = max_price * leverage * 10
    if per_position <= 0: return 10
    count = int(capital / per_position)
    return max(1, min(15, count))

# ==================== 侧边栏 ====================
with st.sidebar:
    st.title("⚙️ AlphaPilot v0.36")
    st.number_input("虚拟本金", min_value=10.0, step=10.0, key="capital")
    st.number_input("最高价筛选 (USDT)", min_value=0.1, step=0.1, key="max_price")
    st.markdown("---"); st.subheader("多空配置")
    st.slider("做多权重", 0.0, 1.0, key="long_weight")
    st.markdown("---"); st.subheader("风控参数")
    st.slider("止损 (%)", 0.5, 10.0, key="stop_loss_pct")
    st.slider("止盈 (%)", 1.0, 30.0, key="take_profit_pct")
    st.selectbox("最大杠杆", [1, 2, 3, 5], key="max_leverage")
    st.markdown("---"); st.subheader("自动交易")
    st.checkbox("启用自动刷新", key="auto_refresh")
    st.selectbox("扫描间隔(秒)", [30, 60, 120], key="auto_interval")
    st.checkbox("启用大模型复盘", key="enable_llm")
    st.markdown("---"); st.subheader("排行榜设置")
    st.slider("展示数量", 10, 100, key="ranking_limit")
    st.markdown("---")
    ws = st.session_state.ws_feed
    st.caption(f"WS: {ws.get_status()} | 订阅: {len(ws.subscribed_symbols)}")
    st.caption(f"内存: {get_memory_mb():.0f}MB / 512MB")
    if st.button("💾 保存快照"):
        st.session_state._trader_backup = json.dumps(st.session_state.trader.to_dict())
        st.success("快照已保存")
    if st.button("📂 加载快照"):
        if "_trader_backup" in st.session_state:
            st.session_state.trader = SimulatedTrader.from_dict(json.loads(st.session_state._trader_backup))
            st.success("快照已恢复")
            st.rerun()

# 参数提取
capital = st.session_state.capital
max_price = st.session_state.max_price
long_weight = st.session_state.long_weight
sl_pct = st.session_state.stop_loss_pct / 100
tp_pct = st.session_state.take_profit_pct / 100
max_lev = st.session_state.max_leverage
auto = st.session_state.auto_refresh
auto_int = st.session_state.auto_interval
llm_on = st.session_state.enable_llm
rank_n = st.session_state.ranking_limit

max_pos = calc_max_positions(capital, max_price, max_lev)

# ==================== 数据加载 ====================
ws = st.session_state.ws_feed
trader = st.session_state.trader
long_df, short_df, total = load_ranking_cached(max_price, rank_n)
perf = calculate_performance(trader)

# WebSocket 订阅
pri = get_priority_symbols(long_df)
if not short_df.empty:
    for s in get_priority_symbols(short_df):
        if s not in pri: pri.append(s)
ws.update_symbols(pri[:50])

# ==================== 主界面 ====================
st.title("AlphaPilot AI v0.36 — 量化交易终端")
st.caption(f"自动交易 · 动态仓位(≤{max_pos}) · 手动平仓 · 做多做空均可")

# ========== 第1板块：多空排行榜 ==========
st.subheader("📊 多空排行榜")
highlight = st.session_state.custom_symbol.upper().replace("USDT","") if st.session_state.custom_symbol else None
cL, cR = st.columns(2)
with cL:
    st.write(f"**做多榜** (前{len(long_df)}/{total})")
    if not long_df.empty:
        if highlight:
            st.info(f"🔍 高亮币种: **{highlight}** — 做多分: {long_df[long_df['币种']==highlight]['做多分'].values[0] if highlight in long_df['币种'].values else '未在排名内'}")
        st.dataframe(long_df[["币种","价格","做多分","RSI","量比"]], width='stretch', hide_index=True)
with cR:
    st.write(f"**做空榜** (前{len(short_df)}/{total})")
    if not short_df.empty:
        if highlight:
            st.info(f"🔍 高亮币种: **{highlight}** — 做空分: {short_df[short_df['币种']==highlight]['做空分'].values[0] if highlight in short_df['币种'].values else '未在排名内'}")
        st.dataframe(short_df[["币种","价格","做空分","RSI","量比"]], width='stretch', hide_index=True)

# ========== 第2板块：K线分析 ==========
st.markdown("---"); st.subheader("📈 K线分析")
c1,c2,c3 = st.columns([2,1.5,1])
with c1:
    if not long_df.empty:
        opts = [f"{r['币种']} (多:{r['做多分']})" for _,r in long_df.iterrows()]
        idx = 0
        if st.session_state.custom_symbol:
            cl = st.session_state.custom_symbol.replace("USDT","")
            idx = next((i for i,o in enumerate(opts) if o.startswith(cl)),0)
        st.session_state.selected_symbol = st.selectbox("排行榜币种", opts, index=idx, key="rank_sel").split(" (")[0]+"USDT"
    else:
        st.session_state.selected_symbol = "BTCUSDT"
with c2:
    inp = st.text_input("自定义币种", value=st.session_state.custom_input, placeholder="如 DOGEUSDT", key="custom_input").upper().strip()
    if inp:
        if not inp.endswith("USDT"): inp += "USDT"
        st.session_state.custom_symbol = inp
        st.session_state.selected_symbol = inp
with c3:
    st.selectbox("周期", ["15m","1h","4h","1d"], key="interval")

sym = st.session_state.selected_symbol
iv = st.session_state.interval
st.caption(f"当前: {sym} | {iv}")
df = get_klines_cached(sym, iv, 200)
if df is not None and len(df)>=20:
    cc, cs = st.columns([2.2,1])
    with cc:
        st.plotly_chart(create_pro_chart(df, sym, iv), width='stretch')
    with cs:
        st.subheader("AI 实时信号")
        if len(df)>=50:
            sig = calculate_directional_signal(df)
            act = sig["action"]
            if "做多" in act: st.success(f"### {act}")
            elif "做空" in act: st.error(f"### {act}")
            else: st.info(f"### {act}")
            a,b,c = st.columns(3)
            a.metric("净得分",sig["net_score"]); b.metric("做多分",sig["long_score"]); c.metric("做空分",sig["short_score"])
            st.caption(f"RSI:{sig['rsi']} | 量比:{sig['vol_ratio']}")
            with st.expander("理由",expanded=True): st.markdown(sig["analysis"])
else: st.warning("K线加载失败")

# ========== 第3板块：资产总览 ==========
st.markdown("---"); st.subheader("💰 资产总览")
render_asset_card(perf, trader)

# ========== 第4板块：持仓 + 交易 ==========
st.markdown("---")
st.subheader("📋 当前持仓")
if trader.holdings:
    rows = []
    del_list = []
    for s, p in trader.holdings.items():
        mark = ws.get_price(s) or p["avg_price"]
        side = "📈多" if p["side"]=="LONG" else "📉空"
        upnl = (mark - p["avg_price"]) * p["qty"] * (1 if p["side"]=="LONG" else -1)
        sl = p["sl"]
        tp = p["tp"]
        # 币安标准：止损止盈为绝对值
        sl_display = sl if sl > 0 else abs(sl)
        tp_display = tp if tp > 0 else abs(tp)
        rows.append({"币种":s.replace("USDT",""),"方向":side,"开仓均价":f"{p['avg_price']:.6f}",
                     "标记价":f"{mark:.6f}","数量":p["qty"],"未实现盈亏":f"{upnl:+.4f}",
                     "止损":f"{sl_display:.6f}","止盈":f"{tp_display:.6f}","杠杆":f"{p['lev']}x"})
        # 手动平仓列
        if st.button(f"平仓 {s.replace('USDT','')}", key=f"close_{s}"):
            pnl = trader.close_position(s, mark)
            st.toast(f"平仓 {s}，盈亏 {pnl:+.2f}")
            auto_open_after_close(trader, max_price, max_pos, long_weight, sl_pct, tp_pct)
            st.rerun()
    st.dataframe(pandas.DataFrame(rows), width='stretch', hide_index=True)
else:
    st.info("暂无持仓")

st.markdown("---")
st.subheader("📝 交易历史")
if trader.trades:
    st.dataframe(pandas.DataFrame(trader.trades[-20:]), width='stretch', hide_index=True)
else:
    st.info("暂无交易")

# ========== 第5板块：AI复盘 ==========
st.markdown("---"); st.subheader("🤖 AI 每日复盘")
if llm_on and st.button("生成复盘报告", width='stretch'):
    with st.spinner("AI分析中..."):
        st.session_state.daily_report = generate_daily_llm_report(trader, perf, st.session_state.regime_detector.get_regime_summary(), long_df)
if st.session_state.daily_report:
    st.markdown(st.session_state.daily_report)
else:
    st.caption("点击按钮生成")

# ========== 状态栏 ==========
st.markdown("---")
x1,x2,x3,x4 = st.columns(4)
x1.metric("市场", st.session_state.regime_detector.get_regime_summary())
x2.metric("熔断","🔴已触发" if st.session_state.circuit_breaker.is_triggered() else "🟢正常")
x3.metric("WS", ws.get_status())
x4.metric("内存", f"{get_memory_mb():.0f}MB")

# ========== 自动交易守护 ==========
if auto:
    now = datetime.datetime.now()
    if (now - st.session_state.auto_trade_last_time).total_seconds() >= auto_int:
        cb = st.session_state.circuit_breaker
        cb.reset_daily_if_new_day(now.date())
        cb.update(perf["总资产"] - getattr(st.session_state,'daily_start',perf["总资产"]), perf["总资产"])
        st.session_state.daily_start = perf["总资产"]
        if not cb.is_triggered():
            result = auto_trade(trader, max_price, max_pos, st.session_state.risk_pct, long_weight, 1-long_weight, sl_pct, tp_pct)
            st.toast(f"🤖 {result}")
        st.session_state.auto_trade_last_time = now
        time.sleep(1); st.rerun()
