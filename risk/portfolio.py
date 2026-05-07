class SimulatedTrader:
    def __init__(self, initial_balance=10000):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.holdings = {}
        self.trades = []

    def open_position(self, symbol, side, price, stop_loss_pct, take_profit_pct, leverage=2):
        if symbol in self.holdings:
            return "已有持仓"
        quantity = 1
        stop_loss = price * (1 - stop_loss_pct) if side == "LONG" else price * (1 + stop_loss_pct)
        take_profit = price * (1 + take_profit_pct) if side == "LONG" else price * (1 - take_profit_pct)
        self.holdings[symbol] = {
            "side": side,
            "quantity": quantity,
            "avg_price": price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "leverage": leverage
        }

    def close_position(self, symbol, price):
        if symbol in self.holdings:
            pos = self.holdings[symbol]
            pnl = (price - pos["avg_price"]) * pos["quantity"]
            if pos["side"] == "SHORT":
                pnl = -pnl
            self.balance += pnl
            self.trades.append({
                "symbol": symbol,
                "side": pos["side"],
                "action": "CLOSE",
                "pnl": pnl
            })
            del self.holdings[symbol]
            return pnl
        return 0
