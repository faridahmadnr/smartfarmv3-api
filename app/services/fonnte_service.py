"""
Fonnte WhatsApp Service
Kirim pesan WhatsApp via Fonnte API (fonnte.com)

Docs: https://docs.fonnte.com/api-send-message/
"""
import logging
import re
from datetime import datetime
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

FONNTE_API_URL = "https://api.fonnte.com/send"


def _normalize_phone(phone: str) -> Optional[str]:
    """
    Normalisasi nomor HP ke format Fonnte (628xxx...).
    - 08xxxxxxxx  → 628xxxxxxxx
    - +628xxxxxxxx → 628xxxxxxxx
    - 628xxxxxxxx  → 628xxxxxxxx (keep)
    Returns None jika tidak valid.
    """
    if not phone:
        return None

    # Hapus spasi, dash, kurung
    cleaned = re.sub(r"[\s\-\(\)]", "", phone.strip())

    # Hapus leading +
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]

    # 08xxx → 628xxx
    if cleaned.startswith("0"):
        cleaned = "62" + cleaned[1:]

    # Pastikan angka semua dan panjang wajar
    if not cleaned.isdigit():
        return None
    if len(cleaned) < 10 or len(cleaned) > 15:
        return None

    return cleaned


async def send_whatsapp(phone: str, message: str) -> bool:
    """
    Kirim pesan WhatsApp ke nomor tujuan.
    Returns True jika berhasil, False jika gagal (non-blocking — error di-log saja).
    """
    settings = get_settings()
    token = getattr(settings, "fonnte_token", None)

    if not token:
        logger.debug("FONNTE_TOKEN tidak dikonfigurasi, skip WhatsApp notification")
        return False

    target = _normalize_phone(phone)
    if not target:
        logger.warning(f"Nomor HP tidak valid untuk Fonnte: {phone!r}")
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                FONNTE_API_URL,
                headers={"Authorization": token},
                data={"target": target, "message": message},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") is True:
                logger.info(f"WhatsApp terkirim ke {target}")
                return True
            else:
                logger.warning(f"Fonnte error response ke {target}: {data}")
                return False
    except httpx.HTTPStatusError as e:
        logger.error(f"Fonnte HTTP error {e.response.status_code}: {e.response.text}")
    except httpx.TimeoutException:
        logger.error(f"Fonnte timeout kirim ke {target}")
    except Exception as e:
        logger.error(f"Fonnte unexpected error: {e}")

    return False


def build_abnormal_message(
    kandang_name: str,
    sensor_data: dict,
) -> str:
    """Buat teks pesan WhatsApp untuk alert kondisi Abnormal."""
    now = datetime.now().strftime("%d %b %Y %H:%M")

    suhu = sensor_data.get("Suhu") or sensor_data.get("suhu", "N/A")
    kelembaban = sensor_data.get("Kelembaban") or sensor_data.get("kelembaban", "N/A")
    amoniak = sensor_data.get("Amoniak") or sensor_data.get("amoniak", "N/A")
    if isinstance(amoniak, (int, float)):
        amoniak = f"{float(amoniak):.3f}"

    return (
        f"🚨 *Broilabs - Kondisi Abnormal*\n\n"
        f"Kandang: *{kandang_name}*\n"
        f"Waktu: {now}\n\n"
        f"Sistem mendeteksi kondisi kandang *tidak normal*.\n\n"
        f"Data sensor saat ini:\n"
        f"• Suhu: {suhu}°C\n"
        f"• Kelembaban: {kelembaban}%\n"
        f"• Amoniak: {amoniak} ppm\n\n"
        f"Segera periksa kondisi kandang!\n"
        f"🔗 https://broilabs.ukirbin.com/notifications"
    )


def build_death_forecast_message(
    kandang_name: str,
    predicted_death: int,
) -> str:
    """Buat teks pesan WhatsApp untuk alert prediksi kematian."""
    now = datetime.now().strftime("%d %b %Y %H:%M")

    return (
        f"⚠️ *Broilabs - Prediksi Kematian*\n\n"
        f"Kandang: *{kandang_name}*\n"
        f"Waktu: {now}\n\n"
        f"Sistem memprediksi *{predicted_death} ekor ayam* berisiko mati\n"
        f"dalam 30 menit ke depan.\n\n"
        f"Segera periksa kondisi ayam!\n"
        f"🔗 https://broilabs.ukirbin.com/notifications"
    )
