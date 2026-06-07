import yfinance as yf
import requests
import os
import json
from datetime import datetime

HISTORY_FILE = "history.json"
SYMBOLS = {
    "USD/TRY": "USDTRY=X",
    "Altin (Gram)": "GC=F",
    "Bitcoin": "BTC-USD"
}

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return {}

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=4)

def calculate_gold_gram_price(ounce_price, usd_try_rate):
    """Ons altin fiyatini ve USD/TRY kurunu kullanarak gram altin fiyatini hesaplar."""
    if ounce_price is None or usd_try_rate is None:
        return None
    return (ounce_price / 31.1035) * usd_try_rate

def fetch_prices():
    """Piyasa fiyatlarini ceker ve altin gram fiyatini hesaplar."""
    prices = {}
    
    # Altin hesaplamasi icin USD/TRY kuru gerekebilir
    usd_try_price = None
    try:
        usd_try_data = yf.Ticker("USDTRY=X").history(period="1d")
        if not usd_try_data.empty:
            usd_try_price = usd_try_data['Close'].iloc[-1]
    except Exception as e:
        print(f"USD/TRY cekilirken hata: {e}")

    for name, symbol in SYMBOLS.items():
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="1d")
            
            if not data.empty:
                current_price = data['Close'].iloc[-1]
                
                prices[name] = current_price
            else:
                prices[name] = None
        except Exception as e:
            print(f"{name} cekilirken hata: {e}")
            prices[name] = None
            
    return prices

def compile_message(market_data):
    """Fiyat verilerini Telegram icin mesaj formatina getirir."""
    date_str = datetime.now().strftime('%d.%m.%Y')
    message = f"📊 *Gunluk Piyasa Ozeti ({date_str})*\n\n"
    
    for name, data in market_data.items():
        price = data.get("price")
        change = data.get("change")
        
        if price is None:
            message += f"🔸 *{name}:* Veri alinamadi\n"
            continue
            
        # Para birimi belirleme
        currency = "$"
        display_price = price
        
        if "TRY" in name or "Altin" in name:
            currency = "TL"
            if name == "Altin (Gram)":
                usd_try = market_data.get("USD/TRY", {}).get("price")
                display_price = calculate_gold_gram_price(price, usd_try)
            
        # Değişim ve emoji belirleme
        change_str = ""
        if change is not None:
            if change > 0:
                emoji = "📈"
            elif change < 0:
                emoji = "📉"
            else:
                emoji = "➖"
            change_str = f" ({emoji} %{change:+.2f})"
            
        if display_price is None:
            message += f"🔸 *{name}:* Hesaplama hatasi\n"
            continue

        message += f"🔸 *{name}:* {display_price:.2f} {currency}{change_str}\n"
    
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
    
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram mesaji gonderilirken hata: {e}")

if __name__ == "__main__":
    history = load_history()
    current_prices = fetch_prices()
    
    market_summary_data = {}
    new_history = {}
    
    for name, current_price in current_prices.items():
        if current_price is not None:
            prev_price = history.get(name)
            change_pct = None
            if prev_price:
                change_pct = ((current_price - prev_price) / prev_price) * 100
            
            market_summary_data[name] = {
                "price": current_price,
                "change": change_pct
            }
            new_history[name] = current_price
        else:
            market_summary_data[name] = {"price": None, "change": None}
            
    market_summary = compile_message(market_summary_data)
    save_history(new_history)

    send_telegram_message(market_summary)
