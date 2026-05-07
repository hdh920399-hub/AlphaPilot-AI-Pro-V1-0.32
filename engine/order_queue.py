class OrderQueueManager:
    def __init__(self):
        self.queue = []

    def add_candidates(self, long_df, short_df, long_weight, short_weight):
        for _, row in long_df.iterrows():
            self.queue.append({"symbol": row["币种"] + "USDT", "side": "LONG", "score": row["做多分"]})
        for _, row in short_df.iterrows():
            self.queue.append({"symbol": row["币种"] + "USDT", "side": "SHORT", "score": row["做空分"]})
        self.queue.sort(key=lambda x: x["score"], reverse=True)

    def pop(self):
        return self.queue.pop(0) if self.queue else None

    def is_empty(self):
        return len(self.queue) == 0
