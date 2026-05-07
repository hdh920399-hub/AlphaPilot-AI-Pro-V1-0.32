import datetime

class SimulatedTrader:
    def __init__(self, initial_balance=10000):
        self.initial = initial_balance
        self.balance = initial_balance
        self.holdings = {}    # {symbol: {side, avg_price, qty, sl, tp, lev}}
        self.trades = []      # [{symbol, side, action, pnl, timestamp}]
        self.daily_pnl = 0

    def open_position(self, symbol, side, price, sl_pct, tp_pct, lev=2):
        if symbol in self.holdings: return f"{symbol} 已有持仓"
        qty = 1  # 模拟每笔 1 个币
        if side == "LONG":
            sl = price * (1 - sl_pct)  # 做多止损在下方
            tp = price * (1 + tp_pct)  # 做多止盈在上方
        else:
            sl = price * (1 + sl_pct)  # 做空止损在上方
            tp = price * (1 - tp_pct)  # 做空止盈在下方
        self.holdings[symbol] = {"side": side, "avg_price": price, "qty": qty,
                                 "sl": sl, "tp": tp, "lev": lev}
        return f"开仓成功: {symbol} {side}"

    def close_position(self, symbol, price):
        if symbol not in self.holdings: return 0
        p = self.holdings.pop(symbol)
        pnl = (price - p["avg_price"]) * p["qty"] * (1 if p["side"]=="LONG" else -1)
        self.balance += pnl
        self.daily_pnl += pnl
        self.trades.append({
            "symbol": symbol, "side": p["side"], "action": "CLOSE",
            "entry": f"{p['avg_price']:.6f}", "exit": f"{price:.6f}",
            "pnl": round(pnl, 4), "timestamp": datetime.datetime.now().strftime("%m-%d %H:%M")
        })
        return pnl

    def performance(self):
        total = self.balance
        for s, p in self.holdings.items():
            total += p["avg_price"] * p["qty"]  # 简化：用开仓价估算
        closed = [t for t in self.trades if t.get("action")=="CLOSE"]
        wins = sum(1 for t in closed if t.get("pnl",0)>0)
        return {
            "总资产": total, "可用余额": self.balance,
            "已实现盈亏": sum(t.get("pnl",0) for t in closed),
            "胜率": f"{wins/len(closed)*100:.1f}%" if closed else "N/A",
            "持仓数": len(self.holdings), "交易数": len(closed)
        }

    def to_dict(self):
        return {"balance": self.balance, "holdings": self.holdings, "trades": self.trades}

    @classmethod
    def from_dict(cls, d):
        obj = cls(0)
        obj.balance = d["balance"]
        obj.holdings = d["holdings"]
        obj.trades = d["trades"]
        return obj
