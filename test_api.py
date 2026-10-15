import os
import sys
from dotenv import load_dotenv
from google import genai
from google.genai import errors

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 1. .env dosyasındaki gizli bilgileri oku
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
model_name = os.getenv("GEMINI_MODEL")

# 2. Eksik bilgi kontrolü
if not api_key or not model_name:
    print("❌ HATA: .env dosyasında API anahtarı veya model adı eksik!")
    exit()

# 3. Gemini API'ye bağlan ve test mesajı gönder
try:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model_name,
        contents="YTÜ'lü bir yazılımcı adayına tek cümlelik motivasyon ver."
    )
    print("✅ BAĞLANTI BAŞARILI!")
    print("Yanıt:", response.text.strip())
    print("📊 Harcanan Token:", response.usage_metadata.total_token_count)

except errors.APIError as e:
    print("❌ API Hatası (Model adını veya anahtarı kontrol et):", e)