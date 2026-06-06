import httpx

from app.config import settings


def api_base() -> str:
    return f"https://graph.facebook.com/v22.0/{settings.whatsapp_phone_number_id}"


async def send_text(to: str, text: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{api_base()}/messages",
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
        return resp.json()


async def send_buttons(to: str, header: str, body: str, buttons: list[dict]) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{api_base()}/messages",
            headers={
                "Authorization": f"Bearer {settings.whatsapp_token}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "header": {"type": "text", "text": header},
                    "body": {"text": body},
                    "action": {"buttons": buttons},
                },
            },
        )
        return resp.json()


async def send_list(
    to: str, header: str, body: str, button_text: str, sections: list[dict]
) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{api_base()}/messages",
            headers={
                "Authorization": f"Bearer {settings.whatsapp_token}",
                "Content-Type": "application/json",
            },
            json={
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
            },
        )
        return resp.json()
