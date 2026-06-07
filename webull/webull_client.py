import requests

WEBULL_API = "https://quotes-gw.webullfintech.com/api/bgw/market/pcIndex?regionId=6&pageSize=50"
API_HEADERS = {
    "Referer": "https://www.webull.com/",
    "appid": "wb_web_us",
    "platform": "web",
    "app": "global",
    "device-type": "Web",
    "Origin": "https://www.webull.com",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15",
}

def fetch_premarket():
    try:
        r = requests.get(WEBULL_API, headers=API_HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        for group in data.get("groups", []):
            if group.get("id") == "gainers":
                return group.get("data", [])
        return []
    except Exception as e:
        print(f"API fetch error: {e}")
        return None