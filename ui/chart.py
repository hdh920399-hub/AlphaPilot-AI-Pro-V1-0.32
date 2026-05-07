import plotly.graph_objects as go
from plotly.subplots import make_subplots


def create_pro_chart(df, symbol, interval="4h"):
    """专业K线图（币安合约风格）"""
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
        subplot_titles=(f"{symbol} — {interval}", "成交量")
    )

    # K线
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="K线",
            increasing=dict(line=dict(color="#26a69a"), fillcolor="#26a69a"),
            decreasing=dict(line=dict(color="#ef5350"), fillcolor="#ef5350"),
        ),
        row=1, col=1
    )

    # 均线
    for period, color in [(7, "#ffeb3b"), (25, "#ff9800"), (99, "#e91e63")]:
        if len(df) >= period:
            ma = df["close"].rolling(period).mean()
            fig.add_trace(
                go.Scatter(x=df.index, y=ma, name=f"MA{period}",
                          line=dict(color=color, width=1)),
                row=1, col=1
            )

    # 布林带
    if len(df) >= 20:
        bb_mid = df["close"].rolling(20).mean()
        bb_std = df["close"].rolling(20).std()
        bb_up = bb_mid + 2 * bb_std
        bb_low = bb_mid - 2 * bb_std
        fig.add_trace(
            go.Scatter(x=df.index, y=bb_up, name="布林上轨",
                      line=dict(color="gray", dash="dot", width=0.8)),
            row=1, col=1
        )
        fig.add_trace(
            go.Scatter(x=df.index, y=bb_low, name="布林下轨",
                      line=dict(color="gray", dash="dot", width=0.8)),
            row=1, col=1
        )
        fig.add_trace(
            go.Scatter(
                x=df.index.tolist() + df.index.tolist()[::-1],
                y=bb_up.tolist() + bb_low.tolist()[::-1],
                fill="toself",
                fillcolor="rgba(128,128,128,0.1)",
                line=dict(color="rgba(255,255,255,0)"),
                name="布林带"
            ),
            row=1, col=1
        )

    # 成交量
    colors = [
        "#26a69a" if c >= o else "#ef5350"
        for c, o in zip(df["close"], df["open"])
    ]
    fig.add_trace(
        go.Bar(x=df.index, y=df["volume"], name="成交量", marker=dict(color=colors)),
        row=2, col=1
    )

    # 布局
    fig.update_layout(
        template="plotly_dark",
        height=700,
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=10, r=10, t=40, b=10),
        font=dict(family="Arial, sans-serif", size=12),
    )
    fig.update_xaxes(title_text="", row=1, col=1)
    fig.update_xaxes(title_text="时间", row=2, col=1)
    fig.update_yaxes(title_text="价格 (USDT)", row=1, col=1)
    fig.update_yaxes(title_text="成交量", row=2, col=1)

    return fig
