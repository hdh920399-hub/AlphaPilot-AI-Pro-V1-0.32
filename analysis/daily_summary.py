def calculate_performance(trader):
    total_assets = trader.balance
    for pos in trader.holdings.values():
        total_assets += pos["avg_price"] * pos["quantity"]
    return {
        "初始本金": trader.initial_balance,
        "总资产": total_assets,
        "收益率": (total_assets - trader.initial_balance) /
