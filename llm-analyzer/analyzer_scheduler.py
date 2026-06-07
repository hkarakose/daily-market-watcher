import os
import requests
import json
from datetime import datetime
import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv
from google import genai

# Load environment variables
load_dotenv()

# Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

PROMPT = """
Bugün ABD borsasında, MAG7 hariç, göreceli olarak daha düşük riskli ve kısa vadede hareket potansiyeli ("spike") yüksek olabilecek hisseleri filtrele.
Bunu yaparken çeyrek raporları, piyasa dinamikleri, sektor haberleri ve teknik göstergeleri dikkate al.
"""

def get_gemini_analysis():
    print(f"[{datetime.now()}] Gemini analizi başlatılıyor...")
    
    if not GEMINI_API_KEY:
        error_msg = "Gemini API anahtarı (GEMINI_API_KEY) bulunamadı!"
        print(error_msg)
        return error_msg

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        # Kullanıcının gemini-2.5-flash tercihini koruyoruz
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"Sen bir finansal analistsin.\n\n{PROMPT}"
        )
        
        if response and response.text:
            return response.text
        else:
            return "Gemini'den boş bir yanıt döndü."
            
    except Exception as e:
        error_msg = f"Gemini API hatası: {e}"
        print(error_msg)
        return error_msg

def send_telegram_message(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram bilgileri eksik!")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    # Telegram sends message with max 4096 characters. 
    if len(text) > 4000:
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    else:
        chunks = [text]

    for chunk in chunks:
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "parse_mode": "Markdown"
        }
        try:
            requests.post(url, json=payload)
        except Exception as e:
            print(f"Telegram mesajı gönderilirken hata: {e}")

def daily_job():
    analysis = get_gemini_analysis()
    formatted_message = f"🚀 *Günlük Borsa Analizi (Gemini)*\n\n{analysis}"
    send_telegram_message(formatted_message)

def run_scheduler():
    scheduler = BlockingScheduler(timezone=pytz.timezone('Europe/Istanbul'))
    
    # Pazartesiden Cumaya her gün saat 16:00'da çalışır
    scheduler.add_job(daily_job, 'cron', day_of_week='mon-fri', hour=16, minute=0)
    
    print("Program başlatıldı. Hafta içi her gün saat 16:00 (TSİ) için bekleniyor...")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass

if __name__ == "__main__":
    if not GEMINI_API_KEY:
        print("UYARI: GEMINI_API_KEY bulunamadı. Lütfen .env dosyasını veya ortam değişkenlerini kontrol edin.")
    
    # Hemen bir kez test etmek isterseniz daily_job() fonksiyonunu burada çağırabilirsiniz.
    # daily_job()
    
    run_scheduler()
