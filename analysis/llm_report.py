import streamlit as st
from llm_analyzer import LLMAnalyzer


def generate_daily_llm_report(trader, perf, regime_info="", rankings_df=None):
    """
    v0.32 AI 每日复盘报告
    结构化 prompt，数据驱动分析
    """
    closed_trades = [t for t in trader.trades if t.get("action") in ("CLOSE", "PARTIAL_CLOSE")]
    recent = closed_trades[-10:] if closed_trades else []

    if not recent and not trader.holdings:
        return "今日无平仓且无持仓，无法生成 AI 复盘。"

    # 构建交易明细
    trade_details = []
    total_pnl = 0
    wins = 0
    for t in recent:
        pnl = t.get("pnl", 0)
        total_pnl += pnl
        if pnl > 0:
            wins += 1
        trade_details.append(
            f"{t.get('symbol','')} | 方向:{t.get('side','')} | 盈亏:{pnl:+.2f}U"
        )

    # 持仓信息
    holdings_info = []
    for sym, pos in trader.holdings.items():
        holdings_info.append(
            f"{sym}: {pos['side']} @ {pos['avg_price']:.4f} x{pos.get('leverage',1)}"
        )

    win_rate = (wins / len(recent) * 100) if recent else 0

    prompt = f"""你是一位专业加密货币量化分析师。请根据数据生成每日复盘报告。

## 账户概况
- 本金: {perf.get('初始本金', 0):.2f} USDT
- 总资产: {perf.get('总资产', 0):.2f} USDT
- 收益率: {perf.get('收益率', 0):+.2f}%
- 已实现盈亏: {perf.get('已实现盈亏', 0):+.2f} USDT
- 胜率: {win_rate:.1f}%
- 市场状态: {regime_info}

## 今日平仓记录
{chr(10).join(trade_details) if trade_details else '无平仓'}

## 当前持仓
{chr(10).join(holdings_info) if holdings_info else '无持仓'}

请输出以下格式（使用 Markdown）：

### ✅ 成功操作
分析今日盈利交易的成功原因（1-2笔）。

### ⚠️ 待改进
分析亏损或错失机会的原因，给出具体改进建议。

### 🔮 明日建议
结合当前持仓和市场状态，给出仓位管理、币种关注、止盈止损调整建议。

### ⚠️ 风险提示
指出需要警惕的风险因素。
"""

    analyzer = LLMAnalyzer()
    result = analyzer.get_completion(prompt, max_tokens=800)

    if "失败" in result or "未配置" in result:
        return (
            f"（AI复盘暂不可用: {result}）\n\n"
            f"### 📊 手动数据摘要\n"
            f"- 今日平仓: {len(recent)} 笔\n"
            f"- 总盈亏: {total_pnl:+.2f} USDT\n"
            f"- 胜率: {win_rate:.1f}%\n"
            f"- 当前持仓: {len(trader.holdings)} 个"
        )

    return result
