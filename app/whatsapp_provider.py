from abc import ABC, abstractmethod

import httpx

from app.config import settings

active_websockets = []

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

    @abstractmethod
    async def send_buttons(self, to: str, header: str, body: str, buttons: list[dict]) -> dict:
        ...

    @abstractmethod
    async def send_list(self, to: str, header: str, body: str, button_text: str, sections: list[dict]) -> dict:
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

    async def send_buttons(self, to: str, header: str, body: str, buttons: list[dict]) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "header": {"type": "text", "text": header},
                "body": {"text": body},
                "action": {"buttons": buttons},
            },
        }
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
            return resp.json()

    async def send_list(self, to: str, header: str, body: str, button_text: str, sections: list[dict]) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {"type": "text", "text": header},
                "body": {"text": body},
                "action": {
                    "button": button_text,
                    "sections": sections,
                },
            },
        }
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
            return resp.json()


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
            "recipient_type": "individual",
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
            "recipient_type": "individual",
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
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": body, "preview_url": False},
        })

    async def send_buttons(self, to: str, header: str, body: str, buttons: list[dict]) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "header": {"type": "text", "text": header},
                "body": {"text": body},
                "action": {"buttons": buttons},
            },
        }
        res = await self._graph_post(payload)
        if "error" in res or res.get("error"):
            print(f"[Direct] send_buttons failed, falling back to text. Error: {res}")
            text_lines = [f"*{header}*", body, ""]
            for i, btn in enumerate(buttons, 1):
                title = btn.get("reply", {}).get("title", "")
                text_lines.append(f"{i}️⃣ {title}")
            text_lines.append("\nResponde con el número o texto de tu opción.")
            return await self.send_text(to, "\n".join(text_lines))
        return res

    async def send_list(self, to: str, header: str, body: str, button_text: str, sections: list[dict]) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {"type": "text", "text": header},
                "body": {"text": body},
                "action": {
                    "button": button_text,
                    "sections": sections,
                },
            },
        }
        res = await self._graph_post(payload)
        if "error" in res or res.get("error"):
            print(f"[Direct] send_list failed, falling back to text. Error: {res}")
            text_lines = [f"*{header}*", body, ""]
            row_index = 1
            for sec in sections:
                for row in sec.get("rows", []):
                    title = row.get("title", "")
                    text_lines.append(f"{row_index}️⃣ {title}")
                    row_index += 1
            text_lines.append("\nResponde con el número o nombre de la categoría.")
            return await self.send_text(to, "\n".join(text_lines))
        return res


class SimulatorProvider(BaseProvider):
    async def _send_ws(self, payload: dict):
        for ws in active_websockets:
            try:
                await ws.send_json(payload)
            except Exception:
                pass

    async def send_text(self, to: str, text: str) -> dict:
        await self._send_ws({"type": "text", "text": text})
        return {"status": "ok"}

    async def send_order_confirmation(self, to: str, order_id: int, items_text: str, total: float, pickup_time: str) -> dict:
        text = f"✅ *PEDIDO #{order_id} CONFIRMADO*\\n\\nResumen:\\n{items_text}\\nTotal: ${total}\\n\\nTiempo estimado de recolección: {pickup_time}"
        await self._send_ws({"type": "text", "text": text})
        return {"status": "ok"}

    async def send_order_cancellation(self, to: str, order_id: int) -> dict:
        text = f"❌ *PEDIDO #{order_id} CANCELADO*\\n\\nTu pedido ha sido cancelado exitosamente. Si fue un error, puedes volver a intentarlo enviando 'Menu'."
        await self._send_ws({"type": "text", "text": text})
        return {"status": "ok"}

    async def send_buttons(self, to: str, header: str, body: str, buttons: list[dict]) -> dict:
        await self._send_ws({"type": "buttons", "header": header, "body": body, "buttons": buttons})
        return {"status": "ok"}

    async def send_list(self, to: str, header: str, body: str, button_text: str, sections: list[dict]) -> dict:
        await self._send_ws({"type": "list", "header": header, "body": body, "button_text": button_text, "sections": sections})
        return {"status": "ok"}

class WhatsAppWebProvider(BaseProvider):
    def __init__(self, base_url: str = "http://localhost:3001"):
        self.base_url = base_url

    async def _call(self, endpoint: str, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                resp = await client.post(f"{self.base_url}/{endpoint}", json=payload)
                return resp.json()
            except Exception as e:
                print(f"[WhatsAppWeb] Error calling {endpoint}: {e}")
                return {"error": str(e)}

    async def send_text(self, to: str, text: str) -> dict:
        return await self._call("send-text", {"to": to, "text": text})

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
        return await self._call("send-text", {"to": to, "text": body})

    async def send_order_cancellation(self, to: str, order_id: int) -> dict:
        body = (
            f"❌ *PEDIDO # {order_id} CANCELADO*\n\n"
            "Lo sentimos, tu pedido ha sido cancelado. "
            "Puedes hacer un nuevo pedido cuando quieras."
        )
        return await self._call("send-text", {"to": to, "text": body})

    async def send_buttons(self, to: str, header: str, body: str, buttons: list[dict]) -> dict:
        return await self._call("send-buttons", {
            "to": to, "header": header, "body": body, "buttons": buttons,
        })

    async def send_list(self, to: str, header: str, body: str, button_text: str, sections: list[dict]) -> dict:
        return await self._call("send-list", {
            "to": to, "header": header, "body": body,
            "buttonText": button_text, "sections": sections,
        })


_whatsapp_web_process = None

def start_whatsapp_web():
    global _whatsapp_web_process
    if _whatsapp_web_process is not None:
        return
    import subprocess
    import os
    webjs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "whatsapp-web")
    _whatsapp_web_process = subprocess.Popen(
        ["node", "server.js"],
        cwd=webjs_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    print(f"[WhatsAppWeb] Servicio iniciado (PID: {_whatsapp_web_process.pid})")


def stop_whatsapp_web():
    global _whatsapp_web_process
    if _whatsapp_web_process is not None:
        _whatsapp_web_process.terminate()
        _whatsapp_web_process = None
        print("[WhatsAppWeb] Servicio detenido")


_provider_instance = None

def get_provider() -> BaseProvider:
    global _provider_instance
    if _provider_instance is None:
        if settings.whatsapp_provider == "manychat":
            _provider_instance = ManyChatProvider(settings.manychat_api_key)
        elif settings.whatsapp_provider == "simulator":
            _provider_instance = SimulatorProvider()
        elif settings.whatsapp_provider == "webjs":
            start_whatsapp_web()
            _provider_instance = WhatsAppWebProvider()
        else:
            _provider_instance = DirectProvider()
    return _provider_instance


def _get_db():
    from app import models
    return models.SessionLocal()
