from fastapi import APIRouter, Request, HTTPException

from app.bot import BotState, build_order_data, get_session, handle_message, reset_session
from app.config import settings
from app.database import confirm_order, create_order, get_or_create_customer
from app.whatsapp import send_text

router = APIRouter()


@router.get("/webhook/whatsapp")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == settings.whatsapp_verify_token:
        return int(challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook/whatsapp")
async def receive_message(request: Request):
    body = await request.json()

    if "entry" not in body:
        return {"status": "ok"}

    for entry in body["entry"]:
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])

            for msg in messages:
                phone = msg.get("from", "")
                msg_type = msg.get("type", "")
                profile_name = value.get("contacts", [{}])[0].get("profile", {}).get("name", "")

                text = ""
                if msg_type == "text":
                    text = msg["text"].get("body", "")
                elif msg_type == "interactive":
                    interactive = msg.get("interactive", {})
                    if interactive.get("type") == "button_reply":
                        text = interactive["button_reply"].get("id", "")
                    elif interactive.get("type") == "list_reply":
                        text = interactive["list_reply"].get("id", "")

                if not text:
                    continue

                state, summary = await handle_message(phone, text)

                if state == BotState.ORDER_PLACED and summary:
                    session = get_session(phone)
                    order_data = build_order_data(phone, profile_name)
                    customer = get_or_create_customer(phone, profile_name)
                    order = create_order(
                        customer_id=customer.id,
                        items=order_data["items"],
                        total=order_data["total"],
                    )

                    order_summary = (
                        f"📋 *PEDIDO # {order.id}*\n\n"
                        + "\n".join(
                            f"   • {i['quantity']}x {i['product_name']} = ${i['subtotal']:.0f}"
                            for i in order_data["items"]
                        )
                        + f"\n\n*Total: ${order_data['total']:.0f}*"
                        + "\n\n⏳ *Pendiente de confirmación*"
                        + "\n\nTe notificaremos cuando el local confirme tu pedido."
                    )
                    await send_text(phone, order_summary)

                    if settings.owner_phone:
                        owner_msg = (
                            f"🛑 *NUEVO PEDIDO # {order.id}*\n\n"
                            + "\n".join(
                                f"• {i['quantity']}x {i['product_name']} (${i['subtotal']:.0f})"
                                for i in order_data["items"]
                            )
                            + f"\n\n*Total: ${order_data['total']:.0f}*"
                            + f"\n👤 Cliente: {profile_name} ({phone})"
                            + f"\n📱 Confirma desde el dashboard: http://localhost:8000/dashboard"
                        )
                        await send_text(settings.owner_phone, owner_msg)

                elif state == BotState.ORDER_PLACED and not summary:
                    pass

    return {"status": "ok"}
