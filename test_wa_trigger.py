"""
Quick script to trigger WhatsApp notification to a specific number via Fonnte.
"""
import asyncio
import httpx
from datetime import datetime

FONNTE_API_URL = "https://api.fonnte.com/send"
FONNTE_TOKEN = "e2vSVYfvepve1Han2aEZ"
TARGET_PHONE = "6285159593699"  # 085159593699 → 628...

now = datetime.now().strftime("%d %b %Y %H:%M")

# --- 1) Abnormal Classification Alert ---
msg_abnormal = (
    f"🚨 *Broilabs - Kondisi Abnormal*\n\n"
    f"Kandang: *Kandang Utama*\n"
    f"Waktu: {now}\n\n"
    f"Model Machine Learning mendeteksi kondisi *ABNORMAL*\n"
    f"Confidence: *92.3%*\n\n"
    f"Detail sensor:\n"
    f"• Suhu: 34.5°C\n"
    f"• Kelembaban: 82.1%\n"
    f"• NH₃ (Amoniak): 0.047 ppm\n\n"
    f"Segera periksa kondisi kandang!\n"
    f"🔗 https://broilabs.ukirbin.com/notifications"
)

# --- 2) Death Forecast Alert ---
msg_forecast = (
    f"⚠️ *Broilabs - Prediksi Kematian*\n\n"
    f"Kandang: *Kandang Utama*\n"
    f"Waktu: {now}\n\n"
    f"Model Forecasting Machine Learning memprediksi\n"
    f"*5 kematian* pada interval berikutnya.\n"
    f"(raw score: 4.8700)\n\n"
    f"Segera periksa kondisi ayam!\n"
    f"🔗 https://broilabs.ukirbin.com/notifications"
)


async def send(message: str, label: str):
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            FONNTE_API_URL,
            headers={"Authorization": FONNTE_TOKEN},
            data={"target": TARGET_PHONE, "message": message},
        )
        data = resp.json()
        print(f"[{label}] status={resp.status_code}  response={data}")


async def main():
    print(f"📤 Mengirim notifikasi WhatsApp ke {TARGET_PHONE} ...")
    await send(msg_abnormal, "Abnormal Alert")
    await send(msg_forecast, "Death Forecast")
    print("✅ Selesai!")


if __name__ == "__main__":
    asyncio.run(main())
