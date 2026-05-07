import numpy as np
import pandas as pd


def calculate_directional_signal(df):
    """多空信号评分 + 详细操作建议"""
    close = df["close"].values
    if len(close) < 50:
        return {
            "long_score": 0, "short_score": 0, "net_score": 0,
            "rsi": 50, "vol_ratio": 1.0,
            "action": "数据不足", "action_detail": "",
            "analysis": "K线不足50根，无法计算。"
        }

    # RSI 14
    delta = np.diff(close)
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = pd.Series(gain).rolling(14).mean().values[13:]
    avg_loss = pd.Series(loss).rolling(14).mean().values[13:]
    rs = avg_gain / (avg_loss + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    rsi_val = rsi[-1]

    # 均线
    ma7 = pd.Series(close).rolling(7).mean().iloc[-1]
    ma25 = pd.Series(close).rolling(25).mean().iloc[-1]
    ma99 = pd.Series(close).rolling(99).mean().iloc[-1] if len(close) >= 99 else ma25

    # 量比
    volume = df["volume"].values
    avg_vol_20 = np.mean(volume[-25:-5]) if len(volume) >= 25 else np.mean(volume)
    vol_ratio_val = volume[-1] / avg_vol_20 if avg_vol_20 > 0 else 1.0

    # MACD
    ema12 = pd.Series(close).ewm(span=12).mean().values[-1]
    ema26 = pd.Series(close).ewm(span=26).mean().values[-1]
    macd_val = ema12 - ema26
    signal_line = pd.Series(macd_val).ewm(span=9).mean().values[-1]

    # 布林带位置
    bb_mid = pd.Series(close).rolling(20).mean().iloc[-1]
    bb_std = pd.Series(close).rolling(20).std().iloc[-1]
    bb_pos = (close[-1] - bb_mid) / (bb_std * 2) if bb_std > 0 else 0

    # 评分
    long_score = 50
    short_score = 50

    if rsi_val > 60:
        long_score += 10; short_score -= 5
    elif rsi_val < 40:
        short_score += 10; long_score -= 5
    elif rsi_val > 50:
        long_score += 5
    else:
        short_score += 5

    if close[-1] > ma7 > ma25:
        long_score += 15; short_score -= 10
    elif close[-1] < ma7 < ma25:
        short_score += 15; long_score -= 10

    if vol_ratio_val > 1.5:
        if close[-1] > close[-2]:
            long_score += 8
        else:
            short_score += 8
    elif vol_ratio_val < 0.5:
        long_score -= 5; short_score -= 5

    if macd_val > signal_line and macd_val > 0:
        long_score += 10
    elif macd_val < signal_line and macd_val < 0:
        short_score += 10
    elif macd_val > signal_line:
        long_score += 5
    else:
        short_score += 5

    if bb_pos > 0.8:
        short_score += 8
    elif bb_pos < -0.8:
        long_score += 8

    long_score = max(0, min(100, long_score))
    short_score = max(0, min(100, short_score))
    net_score = long_score - short_score

    # 理由
    reasons = []
    if rsi_val > 70:
        reasons.append(f"RSI超买({rsi_val:.1f})，回调风险增大")
    elif rsi_val < 30:
        reasons.append(f"RSI超卖({rsi_val:.1f})，反弹概率增大")
    elif rsi_val > 50:
        reasons.append(f"RSI偏强({rsi_val:.1f})，多头占优")
    else:
        reasons.append(f"RSI偏弱({rsi_val:.1f})，空头占优")

    if close[-1] > ma7 > ma25:
        reasons.append("均线多头排列，趋势向上")
    elif close[-1] < ma7 < ma25:
        reasons.append("均线空头排列，趋势向下")
    else:
        reasons.append("均线交织，方向不明")

    if vol_ratio_val > 1.5:
        reasons.append(f"放量({vol_ratio_val:.1f}x)，趋势确认")
    elif vol_ratio_val < 0.5:
        reasons.append(f"缩量({vol_ratio_val:.1f}x)，观望为主")

    if macd_val > signal_line and macd_val > 0:
        reasons.append("MACD金叉且零轴上方，多头强势")
    elif macd_val < signal_line and macd_val < 0:
        reasons.append("MACD死叉且零轴下方，空头强势")

    if bb_pos > 0.8:
        reasons.append("价格位于布林上轨附近，短期或有回调")
    elif bb_pos < -0.8:
        reasons.append("价格位于布林下轨附近，短期或有反弹")

    # 操作建议
    if net_score >= 15 and long_score >= 60:
        action = "📈 做多"
        action_detail = (
            f"信号较强，建议在 {close[-1]*0.995:.4f}（-0.5%）附近挂单做多，"
            f"止损设在 {close[-1]*0.97:.4f}（-3%），"
            f"目标1: {close[-1]*1.05:.4f}（+5%）"
        )
    elif net_score <= -15 and short_score >= 60:
        action = "📉 做空"
        action_detail = (
            f"信号较强，建议在 {close[-1]*1.005:.4f}（+0.5%）附近挂单做空，"
            f"止损设在 {close[-1]*1.03:.4f}（+3%），"
            f"目标1: {close[-1]*0.95:.4f}（-5%）"
        )
    elif net_score >= 5:
        action = "🟢 偏多（信号中等）"
        action_detail = "可轻仓试多，等待更强确认信号。"
    elif net_score <= -5:
        action = "🔴 偏空（信号中等）"
        action_detail = "可轻仓试空，等待更强确认信号。"
    else:
        action = "⏸️ 观望"
        action_detail = "当前无明显方向，建议观望。"

    return {
        "long_score": long_score,
        "short_score": short_score,
        "net_score": net_score,
        "rsi": round(rsi_val, 1),
        "vol_ratio": round(vol_ratio_val, 2),
        "action": action,
        "action_detail": action_detail,
        "analysis": "\n\n".join([f"• {r}" for r in reasons]) + f"\n\n### ✍️ 操作建议\n{action_detail}",
    }
