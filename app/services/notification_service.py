"""
Notification Service - Business logic for notifications with WebSocket broadcast
and optional WhatsApp via Fonnte (fonnte.com).

Notifikasi dikirim dengan isi yang berbeda per role:
  - Peternak : pesan sederhana, personal
  - Pemilik  : kontekstual (siapa peternak, kandang mana)
  - Admin    : detail penuh (pemilik + peternak + kandang)
"""
import uuid
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from sqlalchemy import select, func, and_, desc, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import WebSocket

from app.models.notification import Notification, NotificationType
from app.models.user import User, UserRole
from app.schemas.notification import NotificationCreate
from app.services.fonnte_service import send_whatsapp


APP_URL = "https://broilabs.ukirbin.com/notifications"


class ConnectionManager:
    """WebSocket connection manager for real-time notifications."""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        # Close any stale connections for this user before registering new one
        if user_id in self.active_connections:
            stale = list(self.active_connections[user_id])
            self.active_connections[user_id] = []
            for old_ws in stale:
                try:
                    await old_ws.close(code=1000)
                except Exception:
                    pass
        self.active_connections[user_id] = [websocket]
        print(f"🔗 WebSocket connected for user {user_id}")

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        print(f"🔌 WebSocket disconnected for user {user_id}")

    async def send_to_user(self, user_id: str, message: dict):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    print(f"Error sending to user {user_id}: {e}")

    async def broadcast_to_users(self, user_ids: List[str], message: dict):
        for user_id in user_ids:
            await self.send_to_user(user_id, message)

    async def broadcast_all(self, message: dict):
        for user_id in list(self.active_connections.keys()):
            await self.send_to_user(user_id, message)


manager = ConnectionManager()


class NotificationService:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Core CRUD ────────────────────────────────────────────────────────────

    async def create(self, data: NotificationCreate, broadcast: bool = True) -> Notification:
        notification = Notification(
            user_id=data.user_id,
            kandang_id=data.kandang_id,
            type=data.type,
            title=data.title,
            message=data.message,
            data=data.data,
        )
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)
        if broadcast:
            await self._broadcast_notification(notification)
        return notification

    async def _broadcast_notification(self, notification: Notification):
        message = {
            "type": "notification",
            "data": {
                "id": str(notification.id),
                "notification_type": notification.type,
                "title": notification.title,
                "message": notification.message,
                "kandang_id": str(notification.kandang_id) if notification.kandang_id else None,
                "created_at": notification.created_at.isoformat(),
            },
        }
        await manager.send_to_user(str(notification.user_id), message)

    async def get_by_user(
        self,
        user_id: uuid.UUID,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Notification], int, int]:
        query = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            query = query.where(Notification.is_read == False)

        count_query = select(func.count()).select_from(
            select(Notification).where(Notification.user_id == user_id).subquery()
        )
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        unread_query = select(func.count()).where(
            and_(Notification.user_id == user_id, Notification.is_read == False)
        )
        unread_result = await self.db.execute(unread_query)
        unread_count = unread_result.scalar()

        query = query.order_by(desc(Notification.created_at)).offset(offset).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())
        return items, total, unread_count

    async def get_unread_count(self, user_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count()).where(
                and_(Notification.user_id == user_id, Notification.is_read == False)
            )
        )
        return result.scalar()

    async def mark_as_read(
        self, notification_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[Notification]:
        result = await self.db.execute(
            select(Notification).where(
                and_(
                    Notification.id == notification_id,
                    Notification.user_id == user_id,
                )
            )
        )
        notification = result.scalar_one_or_none()
        if not notification:
            return None
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(notification)
        return notification

    async def mark_all_as_read(self, user_id: uuid.UUID) -> int:
        result = await self.db.execute(
            update(Notification)
            .where(and_(Notification.user_id == user_id, Notification.is_read == False))
            .values(is_read=True, read_at=datetime.utcnow())
        )
        await self.db.commit()
        return result.rowcount

    # ── Internal helpers ─────────────────────────────────────────────────────

    async def _get_kandang_name(self, kandang_id: uuid.UUID) -> str:
        from app.models.kandang import Kandang
        result = await self.db.execute(select(Kandang).where(Kandang.id == kandang_id))
        kandang = result.scalar_one_or_none()
        return kandang.nama if kandang else "Kandang"

    async def _get_kandang_users(self, kandang_id: uuid.UUID) -> List[User]:
        """Ambil pemilik + semua peternak aktif untuk kandang ini."""
        from app.models.kandang import Kandang
        kandang_result = await self.db.execute(
            select(Kandang).where(Kandang.id == kandang_id)
        )
        kandang = kandang_result.scalar_one_or_none()
        if not kandang:
            return []
        users_result = await self.db.execute(
            select(User).where(
                (User.id == kandang.pemilik_id)
                | (
                    (User.pemilik_id == kandang.pemilik_id)
                    & (User.role == UserRole.PETERNAK)
                    & (User.is_active == True)
                )
            )
        )
        return list(users_result.scalars().all())

    async def _get_all_admins(self) -> List[User]:
        result = await self.db.execute(
            select(User).where(
                (User.role == UserRole.ADMIN) & (User.is_active == True)
            )
        )
        return list(result.scalars().all())

    async def _get_pemilik_for_kandang(self, kandang_id: uuid.UUID) -> Optional[User]:
        from app.models.kandang import Kandang
        result = await self.db.execute(
            select(Kandang).where(Kandang.id == kandang_id)
        )
        kandang = result.scalar_one_or_none()
        if not kandang:
            return None
        pemilik_result = await self.db.execute(
            select(User).where(User.id == kandang.pemilik_id)
        )
        return pemilik_result.scalar_one_or_none()

    def _make_notif(
        self,
        user_id: uuid.UUID,
        kandang_id: uuid.UUID,
        notif_type: str,
        title: str,
        message: str,
        data: Optional[str] = None,
    ) -> NotificationCreate:
        return NotificationCreate(
            user_id=user_id,
            kandang_id=kandang_id,
            type=notif_type,
            title=title,
            message=message,
            data=data,
        )

    async def _is_on_cooldown(
        self,
        kandang_id: uuid.UUID,
        notif_type: str,
        minutes: int,
    ) -> bool:
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        result = await self.db.execute(
            select(Notification).where(
                and_(
                    Notification.kandang_id == kandang_id,
                    Notification.type == notif_type,
                    Notification.created_at >= cutoff,
                )
            ).limit(1)
        )
        return result.scalar_one_or_none() is not None

    # ── Alert: Kondisi Abnormal ───────────────────────────────────────────────

    async def create_classification_alert(
        self,
        kandang_id: uuid.UUID,
        prediction: str,
        sensor_data: dict,
    ):
        """
        In-app + WA ke pemilik, peternak, dan admin dengan isi berbeda per role.
        Hanya dikirim jika prediksi Abnormal.
        """
        if prediction != "Abnormal":
            return None
        if await self._is_on_cooldown(kandang_id, NotificationType.ABNORMAL_CLASSIFICATION.value, minutes=10):
            return None

        kandang_name = await self._get_kandang_name(kandang_id)
        pemilik = await self._get_pemilik_for_kandang(kandang_id)
        pemilik_name = pemilik.full_name if pemilik else "Pemilik"
        target_users = await self._get_kandang_users(kandang_id)
        admins = await self._get_all_admins()

        suhu = sensor_data.get("Suhu") or sensor_data.get("suhu", "N/A")
        hum  = sensor_data.get("Kelembaban") or sensor_data.get("kelembaban", "N/A")
        amm  = sensor_data.get("Amoniak") or sensor_data.get("amoniak", "N/A")
        if isinstance(amm, (int, float)):
            amm = f"{float(amm):.3f}"
        sensor_str = f"Suhu: {suhu}°C, Kelembaban: {hum}%, Amoniak: {amm} ppm"
        now_str = datetime.now().strftime("%d %b %Y %H:%M")
        notif_data_json = json.dumps(sensor_data)

        first_notification = None

        # Pemilik + Peternak
        for user in target_users:
            if user.role == UserRole.PEMILIK:
                title   = "⚠️ Kondisi Abnormal Terdeteksi"
                inapp   = (
                    f"Kondisi kandang *{kandang_name}* tidak normal. {sensor_str}. "
                    f"Peternak Anda telah dinotifikasi."
                )
                wa_msg  = (
                    f"⚠️ *Broilabs - Kondisi Abnormal*\n\n"
                    f"Kandang: *{kandang_name}*\nWaktu: {now_str}\n\n"
                    f"Data sensor: {sensor_str}\n\n"
                    f"Peternak Anda telah dinotifikasi. Pantau kondisi kandang!\n"
                    f"🔗 {APP_URL}"
                )
            else:  # peternak
                title   = "⚠️ Kondisi Abnormal Terdeteksi"
                inapp   = (
                    f"Sistem mendeteksi kondisi kandang tidak normal. {sensor_str}. "
                    f"Segera periksa kondisi kandang!"
                )
                wa_msg  = (
                    f"⚠️ *Broilabs - Kondisi Abnormal*\n\n"
                    f"Kandang: *{kandang_name}*\nWaktu: {now_str}\n\n"
                    f"Data sensor: {sensor_str}\n\n"
                    f"Segera periksa kondisi kandang!\n"
                    f"🔗 {APP_URL}"
                )

            notif = await self.create(
                self._make_notif(user.id, kandang_id, NotificationType.ABNORMAL_CLASSIFICATION.value, title, inapp, notif_data_json)
            )
            if first_notification is None:
                first_notification = notif
            if user.phone:
                await send_whatsapp(user.phone, wa_msg)

        # Admin — detail penuh
        admin_title = f"⚠️ Abnormal — {kandang_name}"
        admin_inapp = (
            f"Kandang {kandang_name} (Pemilik: {pemilik_name}): kondisi tidak normal. "
            f"{sensor_str}. Pemilik dan peternak telah dinotifikasi."
        )
        admin_wa = (
            f"⚠️ *Broilabs - Kondisi Abnormal*\n\n"
            f"Kandang: *{kandang_name}*\nPemilik: {pemilik_name}\nWaktu: {now_str}\n\n"
            f"Data sensor: {sensor_str}\n\n"
            f"Pemilik dan peternak telah dinotifikasi.\n"
            f"🔗 {APP_URL}"
        )
        for admin in admins:
            notif = await self.create(
                self._make_notif(admin.id, kandang_id, NotificationType.ABNORMAL_CLASSIFICATION.value, admin_title, admin_inapp, notif_data_json)
            )
            if first_notification is None:
                first_notification = notif
            if admin.phone:
                await send_whatsapp(admin.phone, admin_wa)

        return first_notification

    # ── Alert: Prediksi Kematian ──────────────────────────────────────────────

    async def create_death_forecast_alert(
        self,
        kandang_id: uuid.UUID,
        predicted_death: int,
        raw_prediction: float,
    ):
        """
        In-app + WA ke pemilik, peternak, dan admin dengan isi berbeda per role.
        Hanya dikirim jika prediksi kematian > 1 ekor.
        """
        if predicted_death <= 1:
            return None
        if await self._is_on_cooldown(kandang_id, NotificationType.DEATH_FORECAST.value, minutes=30):
            return None

        kandang_name = await self._get_kandang_name(kandang_id)
        pemilik = await self._get_pemilik_for_kandang(kandang_id)
        pemilik_name = pemilik.full_name if pemilik else "Pemilik"
        target_users = await self._get_kandang_users(kandang_id)
        admins = await self._get_all_admins()

        now_str = datetime.now().strftime("%d %b %Y %H:%M")
        notif_data_json = json.dumps({"predicted_death": predicted_death, "raw_prediction": raw_prediction})

        first_notification = None

        for user in target_users:
            if user.role == UserRole.PEMILIK:
                title   = f"🚨 Prediksi {predicted_death} Kematian"
                inapp   = (
                    f"Sistem memprediksi {predicted_death} ekor ayam di kandang "
                    f"*{kandang_name}* berisiko mati dalam 30 menit. "
                    f"Peternak Anda telah dinotifikasi."
                )
                wa_msg  = (
                    f"🚨 *Broilabs - Prediksi Kematian*\n\n"
                    f"Kandang: *{kandang_name}*\nWaktu: {now_str}\n\n"
                    f"Sistem memprediksi *{predicted_death} ekor ayam* berisiko mati "
                    f"dalam 30 menit ke depan.\n\n"
                    f"Peternak Anda telah dinotifikasi. Segera pantau kondisi kandang!\n"
                    f"🔗 {APP_URL}"
                )
            else:  # peternak
                title   = f"🚨 Prediksi {predicted_death} Kematian"
                inapp   = (
                    f"Sistem memprediksi {predicted_death} ekor ayam berisiko mati "
                    f"dalam 30 menit ke depan. Segera periksa kondisi kandang!"
                )
                wa_msg  = (
                    f"🚨 *Broilabs - Prediksi Kematian*\n\n"
                    f"Kandang: *{kandang_name}*\nWaktu: {now_str}\n\n"
                    f"Sistem memprediksi *{predicted_death} ekor ayam* berisiko mati "
                    f"dalam 30 menit ke depan.\n\n"
                    f"Segera periksa kondisi ayam!\n"
                    f"🔗 {APP_URL}"
                )

            notif = await self.create(
                self._make_notif(user.id, kandang_id, NotificationType.DEATH_FORECAST.value, title, inapp, notif_data_json)
            )
            if first_notification is None:
                first_notification = notif
            if user.phone:
                await send_whatsapp(user.phone, wa_msg)

        # Admin — detail penuh
        admin_title = f"🚨 Prediksi Kematian — {kandang_name}"
        admin_inapp = (
            f"Kandang {kandang_name} (Pemilik: {pemilik_name}): prediksi "
            f"{predicted_death} ekor kematian dalam 30 menit. "
            f"Pemilik dan peternak telah dinotifikasi."
        )
        admin_wa = (
            f"🚨 *Broilabs - Prediksi Kematian*\n\n"
            f"Kandang: *{kandang_name}*\nPemilik: {pemilik_name}\nWaktu: {now_str}\n\n"
            f"Sistem memprediksi *{predicted_death} ekor ayam* berisiko mati "
            f"dalam 30 menit ke depan.\n\n"
            f"Pemilik dan peternak telah dinotifikasi.\n"
            f"🔗 {APP_URL}"
        )
        for admin in admins:
            notif = await self.create(
                self._make_notif(admin.id, kandang_id, NotificationType.DEATH_FORECAST.value, admin_title, admin_inapp, notif_data_json)
            )
            if first_notification is None:
                first_notification = notif
            if admin.phone:
                await send_whatsapp(admin.phone, admin_wa)

        return first_notification
