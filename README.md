# Daily Market Watcher

Bu proje, günlük piyasa verilerini takip eder ve borsa analizi yapar.

## Kurulum

```bash
pip install -r requirements.txt
```

## Kullanım

### 1. Günlük Fiyat Takibi
Mevcut piyasa fiyatlarını çekip Telegram'a gönderir:
```bash
export TELEGRAM_TOKEN="bot_token"
export TELEGRAM_CHAT_ID="chat_id"
python main.py
```

### 2. Gemini Borsa Analizörü (Zamanlanmış Görev)
Hafta içi her gün saat 16:00'da (TSİ) Gemini kullanarak borsa analizi yapar ve Telegram'a gönderir:

```bash
export TELEGRAM_TOKEN="bot_token"
export TELEGRAM_CHAT_ID="chat_id"
export GEMINI_API_KEY="your_gemini_key"
python analyzer_scheduler.py
```

Değişkenleri `.env` dosyası içinde de tanımlayabilirsiniz.
