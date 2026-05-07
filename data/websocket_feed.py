import json, threading, time, logging
from typing import Dict, Optional, Set
import websocket
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BinanceWS")

class BinanceWebSocketFeed:
    MAX_CACHE = 200; STALE_SEC = 10; DELAY = 8; MAX_RETRY = 10

    def __init__(self):
        self.prices: Dict[str,float] = {}
        self.changes: Dict[str,float] = {}
        self.last_ts: Dict[str,float] = {}
        self.subscribed: Set[str] = set()
        self.ws = None; self.thread = None; self.running = False
        self.retry_count = 0
        self._lock = threading.RLock()
        self._stop = threading.Event()

    def _on_open(self, ws):
        logger.info("WS 连接成功"); self.running = True; self.retry_count = 0

    def _on_msg(self, ws, msg):
        try:
            d = json.loads(msg)
            if 'data' in d:
                t = d['data']; s = t.get('s')
                if s:
                    with self._lock:
                        self.prices[s] = float(t['c'])
                        self.changes[s] = float(t.get('P',0))
                        self.last_ts[s] = time.time()
        except: pass

    def _on_err(self, ws, e): logger.error(f"WS err: {e}")
    def _on_close(self, ws, *a):
        self.running = False
        if not self._stop.is_set():
            time.sleep(self.DELAY + (time.time()%10))
            self._connect()

    def _connect(self):
        if not self.subscribed:
            from config import WS_DEFAULT_SYMBOLS
            self.subscribed = set(WS_DEFAULT_SYMBOLS[:5])
        streams = [f"{s}@ticker" for s in list(self.subscribed)[:50]]
        url = f"wss://fstream.binance.com/stream?streams={'/'.join(streams)}"
        self.ws = websocket.WebSocketApp(url, on_open=self._on_open, on_message=self._on_msg,
                                         on_error=self._on_err, on_close=self._on_close)
        self.thread = threading.Thread(target=self.ws.run_forever, kwargs={"ping_interval":30,"ping_timeout":10}, daemon=True)
        self.thread.start()

    def start(self, syms=None):
        if self.running: return
        self._stop.clear()
        if syms: self.subscribed = {s.lower().endswith("usdt") and s.lower() or s.lower()+"usdt" for s in syms}
        self._connect()

    def update_symbols(self, syms):
        ns = {s.lower().endswith("usdt") and s.lower() or s.lower()+"usdt" for s in syms}
        if ns != self.subscribed:
            self.subscribed = ns
            if self.ws: self.ws.close()
            self._connect()

    def get_price(self, sym):
        sl = sym.lower(); now = time.time()
        with self._lock:
            p = self.prices.get(sl)
            if p and now - self.last_ts.get(sl,0) < self.STALE_SEC: return p
        return None

    def get_status(self):
        return "🟢 实时" if self.running else "🔴 未连"
