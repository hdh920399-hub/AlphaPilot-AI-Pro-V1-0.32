"""
Binance WebSocket 实时行情源
"""
import json
import threading
import time
import logging
from typing import Dict, Optional, Set
import websocket

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BinanceWS")


class BinanceWebSocketFeed:
    MAX_CACHE_SIZE = 200
    PRICE_STALE_SECONDS = 10
    RECONNECT_DELAY = 5
    MAX_RECONNECT_ATTEMPTS = 10

    def __init__(self):
        self.prices: Dict[str, float] = {}
        self.price_changes: Dict[str, float] = {}
        self.volumes: Dict[str, float] = {}
        self.last_update: Dict[str, float] = {}
        self.subscribed_symbols: Set[str] = set()
        self.ws = None
        self.wst = None
        self.is_running = False
        self.reconnect_attempts = 0
        self._lock = threading.RLock()
        self._stop_event = threading.Event()

    def _on_open(self, ws):
        logger.info("✅ WebSocket 连接已建立")
        self.is_running = True
        self.reconnect_attempts = 0

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            if 'data' in data:
                ticker = data['data']
                symbol = ticker.get('s')
                if symbol:
                    price = float(ticker['c'])
                    change_pct = float(ticker.get('P', 0))
                    volume = float(ticker.get('v', 0))
                    with self._lock:
                        self.prices[symbol] = price
                        self.price_changes[symbol] = change_pct
                        self.volumes[symbol] = volume
                        self.last_update[symbol] = time.time()
                    self._trim_cache_if_needed()
        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.error(f"消息处理异常: {e}")

    def _trim_cache_if_needed(self):
        with self._lock:
            if len(self.prices) > self.MAX_CACHE_SIZE:
                stale = sorted(self.prices.keys(), key=lambda s: self.last_update.get(s, 0))
                for s in stale[:20]:
                    self.prices.pop(s, None)
                    self.price_changes.pop(s, None)
                    self.volumes.pop(s, None)
                    self.last_update.pop(s, None)

    def _on_error(self, ws, error):
        logger.error(f"WebSocket 错误: {error}")

    def _on_close(self, ws, close_code, close_msg):
        logger.warning(f"连接关闭: code={close_code} msg={close_msg}")
        self.is_running = False
        if not self._stop_event.is_set():
            self._schedule_reconnect()

    def _schedule_reconnect(self):
        if self.reconnect_attempts >= self.MAX_RECONNECT_ATTEMPTS:
            return
        delay = min(self.RECONNECT_DELAY * (2 ** self.reconnect_attempts), 60)
        time.sleep(delay)
        self.reconnect_attempts += 1
        if not self._stop_event.is_set():
            self._connect()

    def _connect(self):
        symbols = self._get_subscribe_list()
        if not symbols:
            return
        streams = [f"{s}@ticker" for s in symbols]
        url = "wss://fstream.binance.com/stream?streams=" + "/".join(streams)
        self.ws = websocket.WebSocketApp(
            url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        def run():
            try:
                self.ws.run_forever(ping_interval=30, ping_timeout=10)
            except Exception as e:
                logger.error(f"连接异常退出: {e}")
                self.is_running = False
        self.wst = threading.Thread(target=run, daemon=True)
        self.wst.start()

    def start(self, symbols=None):
        if self.is_running:
            return
        self._stop_event.clear()
        if symbols:
            self.subscribed_symbols = {
                s.lower() + "usdt" if not s.lower().endswith("usdt") else s.lower()
                for s in symbols
            }
        else:
            from config import WS_DEFAULT_SYMBOLS
            self.subscribed_symbols = set(WS_DEFAULT_SYMBOLS)
        self._connect()

    def update_symbols(self, new_symbols):
        new_set = {
            s.lower() + "usdt" if not s.lower().endswith("usdt") else s.lower()
            for s in new_symbols
        }
        if new_set != self.subscribed_symbols:
            self.subscribed_symbols = new_set
            if self.ws:
                self.ws.close()
            self._connect()

    def get_price(self, symbol: str) -> Optional[float]:
        if not symbol:
            return None
        symbol_lower = symbol.lower()
        with self._lock:
            price = self.prices.get(symbol_lower)
            if price is not None:
                last_ts = self.last_update.get(symbol_lower, 0)
                if time.time() - last_ts < self.PRICE_STALE_SECONDS:
                    return price
        return None

    def get_price_change(self, symbol: str) -> float:
        with self._lock:
            return self.price_changes.get(symbol.lower(), 0.0)

    def get_connection_status(self) -> str:
        if not self.is_running:
            return "🔴 未连接"
        with self._lock:
            if self.last_update and (time.time() - max(self.last_update.values())) < 20:
                return "🟢 实时数据"
        return "🟡 数据延迟"

    def _get_subscribe_list(self) -> list:
        base = list(self.subscribed_symbols)
        leaders = {"btcusdt", "ethusdt", "solusdt"}
        for leader in leaders:
            if leader not in self.subscribed_symbols:
                base.append(leader)
        return base[:self.MAX_CACHE_SIZE]
