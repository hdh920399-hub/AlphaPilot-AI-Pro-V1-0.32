class StrategyEngine:
    def __init__(self, long_weight=0.6):
        self.long_weight = long_weight
        self.short_weight = 1 - long_weight

    def allocate(self, signals, budget):
        pass
