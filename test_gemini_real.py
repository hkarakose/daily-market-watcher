import os
import unittest
from dotenv import load_dotenv
from analyzer_scheduler import get_gemini_analysis

# Load variables from .env
load_dotenv()

class TestGeminiAnalysisReal(unittest.TestCase):

    def setUp(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            self.skipTest("GEMINI_API_KEY bulunamadı. Lütfen .env dosyasını kontrol edin.")

    def test_get_gemini_analysis_real_call(self):
        """Gemini SDK (google-genai) ile gerçek bir istek atar ve sonucu kontrol eder."""
        print("\n[INFO] Gemini (google-genai) API'sine gerçek istek gönderiliyor...")
        
        result = get_gemini_analysis()
        
        # Sonucun bir hata mesajı olmadığını kontrol et
        self.assertNotIn("Gemini API hatası", result, f"API çağrısı başarısız oldu: {result}")
        
        # Sonucun dolu olduğunu kontrol et
        self.assertTrue(len(result) > 0, "Dönen analiz boş olmamalı.")
        
        print("\n--- Gemini Analiz Sonucu ---")
        print(result)
        print("----------------------------")

if __name__ == '__main__':
    unittest.main()
