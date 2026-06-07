from abc import ABC, abstractmethod

import httpx

from app.config import settings


class BaseProvider(ABC):

    @abstractmethod
    async def send_text(self, to: str, text: str) -> dict:
        ...

    @abstractmethod
    async def send_order_confirmation(
        self, to: str, order_id: int, items_text: str, total: float, pickup_time: str
    ) -> dict:
        ...

    @abstractmethod
    async def send_order_cancellation(self, to: str, order_id: int) -> dict:
        ...


MANYCHAT_FIND_BY_PHONE = "https://api.manychat.com/fb/subscriber/findByPhone"


class ManyChatProvider(BaseProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _resolve_subscriber_id(self, to: str) -> str | None:
        db = _get_db()
        try:
            from app.models import Customer
            customer = db.query(Customer).filter(Customer.phone == to).first()
            if customer and customer.manychat_id:
                return customer.manychat_id
        except Exception:
            pass
        finally:
            db.close()

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    MANYCHAT_FIND_BY_PHONE,
                    headers=self._headers(),
                    json={"phone": to},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    subscriber = data.get("data", {})
                    subscriber_id = subscriber.get("subscriber_id")
                    if subscriber_id:
                        try:
                            db = _get_db()
                            customer = db.query(Customer).filter(Customer.phone == to).first()
                            if customer:
                                customer.manychat_id = str(subscriber_id)
                                db.commit()
                        except Exception:
                            pass
                        finally:
                            db.close()
                        return str(subscriber_id)
            except Exception as e:
                print(f"[ManyChat] resolve_subscriber error: {e}")
        return None

    async def _meta_send(self, to: str, text: str) -> dict:
        base = f"https://graph.facebook.com/v22.0/{settings.whatsapp_phone_number_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{base}/messages",
                headers={
                    "Authorization": f"Bearer {settings.whatsapp_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "text",
                    "text": {"body": text, "preview_url": False},
                },
            )
            data = resp.json()
            if resp.status_code != 200:
                print(f"[ManyChat/Meta] Error: {data}")
            return data

    async def send_text(self, to: str, text: str) -> dict:
        return await self._meta_send(to, text)

    async def send_order_confirmation(
        self, to: str, order_id: int, items_text: str, total: float, pickup_time: str
    ) -> dict:
        body = (
            f"✅ *PEDIDO # {order_id} CONFIRMADO*\n\n"
            f"{items_text}\n\n"
            f"*Total: ${total:.0f}*\n\n"
            f"🕐 *Recoge a las: {pickup_time}*\n\n"
            f"📍 Pasa al local y paga en efectivo. ¡Te esperamos! 🎉"
        )
        return await self._meta_send(to, body)

    async def send_order_cancellation(self, to: str, order_id: int) -> dict:
        body = (
            f"❌ *PEDIDO # {order_id} CANCELADO*\n\n"
            "Lo sentimos, tu pedido ha sido cancelado. "
            "Puedes hacer un nuevo pedido cuando quieras."
        )
        return await self._meta_send(to, body)


class DirectProvider(BaseProvider):
    async def _graph_post(self, payload: dict) -> dict:
        base = f"https://graph.facebook.com/v22.0/{settings.whatsapp_phone_number_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{base}/messages",
                headers={
                    "Authorization": f"Bearer {settings.whatsapp_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            data = resp.json()
            if resp.status_code != 200:
                print(f"[Direct] Error: {data}")
            return data

    async def send_text(self, to: str, text: str) -> dict:
        return await self._graph_post({
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text, "preview_url": False},
        })

    async def send_order_confirmation(
        self, to: str, order_id: int, items_text: str, total: float, pickup_time: str
    ) -> dict:
        body = (
            f"✅ *PEDIDO # {order_id} CONFIRMADO*\n\n"
            f"{items_text}\n\n"
            f"*Total: ${total:.0f}*\n\n"
            f"🕐 *Recoge a las: {pickup_time}*\n\n"
            f"📍 Pasa al local y paga en efectivo. ¡Te esperamos! 🎉"
        )
        return await self._graph_post({
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body, "preview_url": False},
        })

    async def send_order_cancellation(self, to: str, order_id: int) -> dict:
        body = (
            f"❌ *PEDIDO # {order_id} CANCELADO*\n\n"
            "Lo sentimos, tu pedido ha sido cancelado. "
            "Puedes hacer un nuevo pedido cuando quieras."
        )
        return await self._graph_post({
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body, "preview_url": False},
        })


_provider_instance: BaseProvider | None = None


def get_provider() -> BaseProvider:
    global _provider_instance
    if _provider_instance is None:
        if settings.whatsapp_provider == "manychat":
            _provider_instance = ManyChatProvider(settings.manychat_api_key)
        else:
            _provider_instance = DirectProvider()
    return _provider_instance


def _get_db():
    from app import models
    return models.SessionLocal()
