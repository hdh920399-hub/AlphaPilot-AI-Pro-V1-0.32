def preload():
    """冷启动预热：ping 币安 API 以减少首次请求延迟"""
    import requests
    try:
        requests.get("https://fapi.binance.com/fapi/v1/ping", timeout=5)
    except Exception:
        pass
