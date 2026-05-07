def calculate_performance(trader):
    total_assets = trader.balance
    for pos in trader.holdings.values():
        total_assets += pos["avg_price"] * pos["qty"]
    closed = [t for t in trader.trades if t.get("action") == "CLOSE"]
    return {
        "总资产": total_assets,
        "可用余额": trader.balance,
        "已实现盈亏": sum(t.get("pnl", 0) for t in closed),
        "胜率": f"{sum(1 for t in closed if t.get('pnl',0)>0)/len(closed)*100:.1f}%" if closed else "N/A",
        "持仓数": len(trader.holdings),
        "交易数": len(closed),
    }
