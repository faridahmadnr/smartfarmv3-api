"""
Scheduler Service - Penjadwalan tugas otomatis (APScheduler)

Jobs:
  1. send_daily_log_reminder — 07:00 WIB setiap hari
     Peternak : pengingat personal sederhana
     Pemilik  : informasi bahwa peternak kandangnya diingatkan
     Admin    : ringkasan per kandang (pemilik + jumlah peternak)

  2. check_iot_offline — setiap 30 menit
     Admin saja: in-app + WA dengan detail pemilik & waktu terakhir data masuk
"""
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Asia/Jakarta")

APP_URL_NOTIF   = "https://broilabs.ukirbin.com/notifications"
APP_URL_LOG     = "https://broilabs.ukirbin.com/daily-logs"


async def send_daily_log_reminder():
    """
    Kirim notifikasi pengingat log harian pukul 07:00 WIB.
    Setiap role menerima isi notifikasi yang berbeda.
    Deduplication: skip jika sudah pernah dikirim hari ini untuk user+kandang tsb.
    """
    from app.database import async_session_maker as AsyncSessionLocal
    from app.models.kandang import Kandang
    from app.models.user import User, UserRole
    from app.models.notification import Notification, NotificationType
    from app.services.notification_service import NotificationService
    from app.services.fonnte_service import send_whatsapp
    from app.schemas.notification import NotificationCreate
    from sqlalchemy import select, func, text

    now      = datetime.now()
    today_str   = now.strftime("%d %b %Y")
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    async with AsyncSessionLocal() as db:
        # Advisory lock agar hanya satu proses (instance) yang menjalankan job ini
        lock_result = await db.execute(text("SELECT pg_try_advisory_lock(1001)"))
        if not lock_result.scalar():
            logger.info("Daily log reminder: instance lain sedang berjalan, dilewati")
            return
        try:
            kandangs_result = await db.execute(
                select(Kandang).where(Kandang.is_active == True)
            )
            kandangs = kandangs_result.scalars().all()

            # Ambil semua admin sekali
            admins_result = await db.execute(
                select(User).where(
                    (User.role == UserRole.ADMIN) & (User.is_active == True)
                )
            )
            admins = admins_result.scalars().all()

            for kandang in kandangs:
                try:
                    svc = NotificationService(db)

                    # ── Ambil pemilik & peternak kandang ──────────────────────
                    users_result = await db.execute(
                        select(User).where(
                            (User.id == kandang.pemilik_id)
                            | (
                                (User.pemilik_id == kandang.pemilik_id)
                                & (User.role == UserRole.PETERNAK)
                                & (User.is_active == True)
                            )
                        )
                    )
                    target_users = users_result.scalars().all()

                    pemilik_user  = next((u for u in target_users if u.role == UserRole.PEMILIK), None)
                    peternak_list = [u for u in target_users if u.role == UserRole.PETERNAK]
                    pemilik_name  = pemilik_user.full_name if pemilik_user else "Pemilik"
                    peternak_count = len(peternak_list)

                    # ── Pemilik + Peternak ────────────────────────────────────
                    for user in target_users:
                        already_sent = await db.execute(
                            select(func.count()).where(
                                (Notification.user_id == user.id)
                                & (Notification.kandang_id == kandang.id)
                                & (Notification.type == NotificationType.SYSTEM.value)
                                & (Notification.title == "📋 Pengingat Log Harian")
                                & (Notification.created_at >= today_start)
                            )
                        )
                        if already_sent.scalar() > 0:
                            continue

                        if user.role == UserRole.PEMILIK:
                            inapp_msg = (
                                f"Selamat pagi! Pengingat log harian kandang *{kandang.nama}* "
                                f"hari ini ({today_str}) telah dikirim ke {peternak_count} peternak Anda."
                            )
                            wa_msg = (
                                f"📋 *Pengingat Log Harian - Broilabs*\n\n"
                                f"Selamat pagi! 🌅\n"
                                f"Pengingat log harian kandang *{kandang.nama}* hari ini "
                                f"telah dikirim ke *{peternak_count} peternak* Anda.\n\n"
                                f"Pastikan log harian hari ini terisi dengan lengkap.\n"
                                f"🔗 {APP_URL_LOG}"
                            )
                        else:  # peternak
                            inapp_msg = (
                                f"Selamat pagi! Jangan lupa mengisi log harian kandang "
                                f"*{kandang.nama}* hari ini ({today_str}). "
                                f"Catat pakan, minum, bobot, dan populasi ayam."
                            )
                            wa_msg = (
                                f"📋 *Pengingat Log Harian - Broilabs*\n\n"
                                f"Selamat pagi! 🌅\n"
                                f"Jangan lupa mengisi log harian kandang *{kandang.nama}* hari ini.\n\n"
                                f"Catat:\n"
                                f"• Jumlah pakan (kg)\n"
                                f"• Jumlah minum (liter)\n"
                                f"• Bobot rata-rata (gram)\n"
                                f"• Populasi saat ini\n\n"
                                f"🔗 {APP_URL_LOG}"
                            )

                        await svc.create(
                            NotificationCreate(
                                user_id=user.id,
                                kandang_id=kandang.id,
                                type=NotificationType.SYSTEM.value,
                                title="📋 Pengingat Log Harian",
                                message=inapp_msg,
                            ),
                            broadcast=True,
                        )
                        if user.phone:
                            await send_whatsapp(user.phone, wa_msg)

                    # ── Admin — ringkasan per kandang ─────────────────────────
                    admin_title   = "📋 Pengingat Log Harian"
                    admin_inapp   = (
                        f"Pengingat log harian telah dikirim: kandang *{kandang.nama}* "
                        f"(Pemilik: {pemilik_name}) — {peternak_count} peternak diingatkan."
                    )
                    admin_wa = (
                        f"📋 *Pengingat Log Harian - Broilabs*\n\n"
                        f"Kandang: *{kandang.nama}*\nPemilik: {pemilik_name}\n"
                        f"Peternak yang diingatkan: *{peternak_count} orang*\n\n"
                        f"🔗 {APP_URL_LOG}"
                    )

                    for admin in admins:
                        already_sent = await db.execute(
                            select(func.count()).where(
                                (Notification.user_id == admin.id)
                                & (Notification.kandang_id == kandang.id)
                                & (Notification.type == NotificationType.SYSTEM.value)
                                & (Notification.title == admin_title)
                                & (Notification.created_at >= today_start)
                            )
                        )
                        if already_sent.scalar() > 0:
                            continue

                        await svc.create(
                            NotificationCreate(
                                user_id=admin.id,
                                kandang_id=kandang.id,
                                type=NotificationType.SYSTEM.value,
                                title=admin_title,
                                message=admin_inapp,
                            ),
                            broadcast=True,
                        )
                        if admin.phone:
                            await send_whatsapp(admin.phone, admin_wa)

                    logger.info(
                        f"Daily log reminder: kandang '{kandang.nama}' — "
                        f"{peternak_count} peternak + pemilik notified, admins informed"
                    )

                except Exception as e:
                    logger.warning(f"Failed to send reminder for kandang {kandang.id}: {e}")

        except Exception as e:
            logger.error(f"Daily log reminder job failed: {e}")
        finally:
            await db.execute(text("SELECT pg_advisory_unlock(1001)"))


async def check_iot_offline():
    """
    Cek setiap 30 menit apakah kandang aktif tidak mengirim data > 35 menit.
    Kirim notifikasi in-app + WA ke semua admin dengan detail pemilik kandang.
    Deduplication: cooldown 1 jam per kandang.
    """
    from app.database import async_session_maker as AsyncSessionLocal
    from app.models.kandang import Kandang
    from app.models.user import User, UserRole
    from app.models.notification import Notification, NotificationType
    from app.models.sensor_data import SensorData
    from app.services.notification_service import NotificationService
    from app.services.fonnte_service import send_whatsapp
    from app.schemas.notification import NotificationCreate
    from sqlalchemy import select, func, text
    from datetime import timedelta

    now               = datetime.utcnow()
    offline_threshold = now - timedelta(minutes=35)
    cooldown_threshold = now - timedelta(hours=1)

    async with AsyncSessionLocal() as db:
        # Advisory lock agar hanya satu proses (instance) yang menjalankan job ini
        lock_result = await db.execute(text("SELECT pg_try_advisory_lock(1002)"))
        if not lock_result.scalar():
            logger.info("IoT offline check: instance lain sedang berjalan, dilewati")
            return
        try:
            kandangs_result = await db.execute(
                select(Kandang).where(Kandang.is_active == True)
            )
            kandangs = kandangs_result.scalars().all()

            admins_result = await db.execute(
                select(User).where(
                    (User.role == UserRole.ADMIN) & (User.is_active == True)
                )
            )
            admins = admins_result.scalars().all()
            if not admins:
                return

            for kandang in kandangs:
                try:
                    last_data_result = await db.execute(
                        select(SensorData.timestamp)
                        .where(SensorData.kandang_id == kandang.id)
                        .order_by(SensorData.timestamp.desc())
                        .limit(1)
                    )
                    last_ts = last_data_result.scalar_one_or_none()

                    is_offline = (last_ts is None) or (
                        last_ts.replace(tzinfo=None) < offline_threshold
                    )
                    if not is_offline:
                        continue

                    # Hitung waktu terakhir data masuk
                    if last_ts is None:
                        last_seen_inapp = "Belum pernah ada data"
                        last_seen_wa    = "belum pernah ada data"
                    else:
                        minutes_ago = int(
                            (now - last_ts.replace(tzinfo=None)).total_seconds() // 60
                        )
                        last_seen_inapp = f"{minutes_ago} menit lalu"
                        last_seen_wa    = f"{minutes_ago} menit yang lalu"

                    # Ambil nama pemilik
                    pemilik_result = await db.execute(
                        select(User).where(User.id == kandang.pemilik_id)
                    )
                    pemilik = pemilik_result.scalar_one_or_none()
                    pemilik_name = pemilik.full_name if pemilik else "—"

                    notif_title = f"⚠️ IoT Offline: {kandang.nama}"
                    inapp_msg   = (
                        f"Kandang *{kandang.nama}* (Pemilik: {pemilik_name}) tidak mengirim "
                        f"data sensor. Data terakhir: {last_seen_inapp}. "
                        f"Cek koneksi perangkat IoT."
                    )
                    wa_msg = (
                        f"⚠️ *Broilabs - IoT Offline*\n\n"
                        f"Kandang: *{kandang.nama}*\nPemilik: {pemilik_name}\n\n"
                        f"Perangkat IoT tidak mengirim data sejak {last_seen_wa}.\n"
                        f"Segera periksa koneksi perangkat!\n\n"
                        f"🔗 {APP_URL_NOTIF}"
                    )

                    svc = NotificationService(db)
                    for admin in admins:
                        already_sent = await db.execute(
                            select(func.count()).where(
                                (Notification.user_id == admin.id)
                                & (Notification.kandang_id == kandang.id)
                                & (Notification.type == NotificationType.SYSTEM.value)
                                & (Notification.title == notif_title)
                                & (Notification.created_at >= cooldown_threshold)
                            )
                        )
                        if already_sent.scalar() > 0:
                            continue

                        await svc.create(
                            NotificationCreate(
                                user_id=admin.id,
                                kandang_id=kandang.id,
                                type=NotificationType.SYSTEM.value,
                                title=notif_title,
                                message=inapp_msg,
                            ),
                            broadcast=True,
                        )
                        if admin.phone:
                            await send_whatsapp(admin.phone, wa_msg)

                    logger.info(
                        f"IoT offline alert: kandang '{kandang.nama}' ({pemilik_name}) "
                        f"→ {len(admins)} admin(s) notified"
                    )

                except Exception as e:
                    logger.warning(f"IoT offline check failed for kandang {kandang.id}: {e}")

        except Exception as e:
            logger.error(f"IoT offline check job failed: {e}")
        finally:
            await db.execute(text("SELECT pg_advisory_unlock(1002)"))


def start_scheduler():
    scheduler.add_job(
        send_daily_log_reminder,
        trigger=CronTrigger(hour=7, minute=0, timezone="Asia/Jakarta"),
        id="daily_log_reminder",
        name="Daily Log Reminder 07:00 WIB",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=300,
    )
    scheduler.add_job(
        check_iot_offline,
        trigger=CronTrigger(minute="*/30", timezone="Asia/Jakarta"),
        id="iot_offline_check",
        name="IoT Offline Check (every 30 min)",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=120,
    )
    scheduler.start()
    logger.info("Scheduler started — daily log reminder 07:00 WIB, IoT offline check every 30 min")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
