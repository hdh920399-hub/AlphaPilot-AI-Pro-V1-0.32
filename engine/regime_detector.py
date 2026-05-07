class RegimeDetector:
    def __init__(self):
        self.regime = "ranging"

    def detect(self, df):
        if len(df) < 50:
            return "unknown"
        ma20 = df["close"].rolling(20).mean().iloc[-1]
        ma50 = df["close"].rolling(50).mean().iloc[-1]
        if ma20 > ma50:
            self.regime = "uptrend"
        elif ma20 < ma50:
            self.regime = "downtrend"
        else:
            self.regime = "ranging"
        return self.regime

    def get_regime_summary(self):
        return self.regime
