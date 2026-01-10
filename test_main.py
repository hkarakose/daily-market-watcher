import unittest
from main import compile_message
from datetime import datetime

class TestMarketWatcher(unittest.TestCase):

    def test_compile_message_formatting(self):
        """Mesajın doğru formatta ve doğru emojilerle oluşturulduğunu test eder."""
        mock_data = {
            "USD/TRY": {"price": 31.1035, "change": 0.50},  # Kolay hesaplama icin 31.1035
            "Bitcoin": {"price": 65000.0, "change": -1.20}, 
            "Altin (Gram)": {"price": 2500.0, "change": 0.0} # Ons fiyati 2500. Gram = (2500/31.1035)*31.1035 = 2500
        }
        
        message = compile_message(mock_data)
        print(message)
        date_str = datetime.now().strftime('%d.%m.%Y')
        
        # 1. Baslik kontrolu
        self.assertIn(f"Gunluk Piyasa Ozeti ({date_str})", message)
        
        # 2. Artis emojisi ve birim kontrolu (USD/TRY -> TL)
        self.assertIn("USD/TRY:* 31.10 TL (📈 %+0.50)", message)
        
        # 3. Azalis emojisi ve birim kontrolu (Bitcoin -> $)
        self.assertIn("Bitcoin:* 65000.00 $ (📉 %-1.20)", message)
        
        # 4. Sabit emojisi kontrolu
        self.assertIn("Altin (Gram):* 2500.00 TL (➖ %+0.00)", message)

    def test_compile_message_empty(self):
        """Veri bos oldugunda sadece basligin geldigini test eder."""
        message = compile_message({})
        self.assertTrue(message.startswith("📊 *Gunluk Piyasa Ozeti"))

if __name__ == '__main__':
    unittest.main()
