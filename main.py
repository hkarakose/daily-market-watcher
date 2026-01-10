import yfinance as yf
import requests
import os
import json
from datetime import datetime

HISTORY_FILE = "history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return {}

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=4)

def get_market_data():
    symbols = {
        "USD/TRY": "USDTRY=X",
        "Altın (Gram)": "GC=F",
        "Bitcoin": "BTC-USD"
    }
    
    history = load_history()
    new_history = {}
    message = f"📊 *Günlük Piyasa Özeti ({datetime.now().strftime('%d.%m.%Y')})*\n\n"
    
    for name, symbol in symbols.items():
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="2d") # Son 2 günü çekiyoruz ki değişim hesaplayalım
            
            if not data.empty:
                current_price = data['Close'].iloc[-1]
                
                # Altın gram hesaplama
                if name == "Altın (Gram)":
                    usdtry = yf.Ticker("USDTRY=X").history(period="1d")['Close'].iloc[-1]
                    current_price = (current_price / 31.1035) * usdtry
                
                # Değişim hesaplama
                prev_price = history.get(name)
                change_str = ""
                if prev_price:
                    change_pct = ((current_price - prev_price) / prev_price) * 100
                    emoji = "📈" if change_pct > 0 else "📉"
                    change_str = f" ({emoji} %{change_pct:+.2f})"
                
                new_history[name] = current_price
                
                currency = "TL" if "TRY" in symbol or name == "Altın (Gram)" else "$"
                message += f"🔸 *{name}:* {current_price:.2f} {currency}{change_str}\n"
            else:
                message += f"🔸 *{name}:* Veri alınamadı\n"
        except Exception as e:
            message += f"🔸 *{name}:* Hata: {str(e)}\n"
            
    save_history(new_history)
    return message

def send_telegram_message(text):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("Telegram bilgileri eksik!")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    
    requests.post(url, json=payload)

if __name__ == "__main__":
    market_summary = get_market_data()
    send_telegram_message(market_summary)
