class CircuitBreaker:
    def __init__(self, max_daily_loss=10, max_consecutive_losses=3, max_drawdown=0.2):
        self.max_daily_loss = max_daily_loss
        self.max_consecutive_losses = max_consecutive_losses
        self.max_drawdown = max_drawdown
        self.daily_loss = 0.0
        self.consecutive_losses = 0
        self.triggered = False
        self._last_date = None

    def reset_daily_if_new_day(self, current_date):
        if self._last_date is None:
            self._last_date = current_date
        if current_date != self._last_date:
            self.daily_loss = 0.0
            self.consecutive_losses = 0
            self.triggered = False
            self._last_date = current_date

    def update(self, today_pnl, current_equity):
        self.daily_loss = abs(min(0, today_pnl))
        if today_pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        if self.daily_loss >= self.max_daily_loss:
            self.triggered = True
        elif self.consecutive_losses >= self.max_consecutive_losses:
            self.triggered = True
        else:
            self.triggered = False

    def is_triggered(self):
        return self.triggered


class BudgetManager:
    def __init__(self, total_capital, long_ratio=0.6, short_ratio=0.4):
        self.total_capital = total_capital
        self.long_budget = total_capital * long_ratio
        self.short_budget = total_capital * short_ratio

    def get_long_budget(self):
        return self.long_budget

    def get_short_budget(self):
        return self.short_budget
