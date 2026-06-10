from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from app.bot import (
    BotState,
    build_order_data,
    get_session,
    handle_message,
)
from app.config import settings
from app.database import create_order, get_or_create_customer, save_message
from app.whatsapp import send_text

router = APIRouter()


# ============================================================
# WEBHOOKS (Meta)
# ============================================================

@router.get("/webhook/whatsapp")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    expected = settings.whatsapp_verify_token
    if mode == "subscribe" and token == expected:
        return PlainTextResponse(challenge)
    return PlainTextResponse("Verification failed", status_code=403)


@router.post("/webhook/whatsapp")
async def receive_message(request: Request):
    try:
        body = await request.json()
    except Exception:
        return {"status": "error", "detail": "invalid json"}

    if "entry" in body:
        return await _handle_meta_webhook(body, request)

    if "phone" in body:
        return await _handle_incoming_webjs(body, request)

    return {"status": "ok"}


async def _handle_incoming_webjs(body: dict, request: Request) -> dict:
    phone = body.get("phone", "")
    text = body.get("text", "")
    profile_name = body.get("profile_name", "")
    msg_type = body.get("msg_type", "text")

    if not phone or not text:
        return {"status": "ok"}

    try:
        save_message(phone, profile_name, text, msg_type)
    except Exception as e:
        print(f"Error saving message: {e}")

    try:
        state, summary = await handle_message(phone, text)
    except Exception as e:
        print(f"Error handling message: {e}")
        return {"status": "ok"}

    if state == BotState.ORDER_PLACED and summary:
        try:
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
            from app.whatsapp import send_text
            await send_text(phone, order_summary)

            if settings.owner_phone:
                dashboard_url = f"{str(request.base_url).rstrip('/')}/dashboard"
                owner_msg = (
                    f"🛑 *NUEVO PEDIDO # {order.id}*\n\n"
                    + "\n".join(
                        f"• {i['quantity']}x {i['product_name']} (${i['subtotal']:.0f})"
                        for i in order_data["items"]
                    )
                    + f"\n\n*Total: ${order_data['total']:.0f}*"
                    + f"\n👤 Cliente: {profile_name} ({phone})"
                    + f"\n📱 Confirma desde el dashboard: {dashboard_url}"
                )
                await send_text(settings.owner_phone, owner_msg)
        except Exception as e:
            print(f"Error processing order: {e}")

    return {"status": "ok"}


async def _handle_meta_webhook(body: dict, request: Request) -> dict:
    """Maneja mensajes entrantes directo de WhatsApp/Meta (gratis)."""
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])

            for msg in messages:
                phone = msg.get("from", "")
                msg_type = msg.get("type", "")
                profile_name = (
                    value.get("contacts", [{}])[0]
                    .get("profile", {})
                    .get("name", "")
                )

                text = ""
                display_text = ""
                if msg_type == "text":
                    text = msg["text"].get("body", "")
                    display_text = text
                elif msg_type == "interactive":
                    interactive = msg.get("interactive", {})
                    if interactive.get("type") == "button_reply":
                        text = interactive["button_reply"].get("id", "")
                        display_text = interactive["button_reply"].get("title", text)
                    elif interactive.get("type") == "list_reply":
                        text = interactive["list_reply"].get("id", "")
                        display_text = interactive["list_reply"].get("title", text)

                if not text:
                    continue

                # Guardar mensaje en DB para el inbox del dashboard
                try:
                    save_message(phone, profile_name, display_text or text, msg_type)
                except Exception as e:
                    print(f"Error saving message: {e}")

                try:
                    state, summary = await handle_message(phone, text)
                except Exception as e:
                    print(f"Error handling message: {e}")
                    continue

                if state == BotState.ORDER_PLACED and summary:
                    try:
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
                            dashboard_url = f"{str(request.base_url).rstrip('/')}/dashboard"
                            owner_msg = (
                                f"🛑 *NUEVO PEDIDO # {order.id}*\n\n"
                                + "\n".join(
                                    f"• {i['quantity']}x {i['product_name']} (${i['subtotal']:.0f})"
                                    for i in order_data["items"]
                                )
                                + f"\n\n*Total: ${order_data['total']:.0f}*"
                                + f"\n👤 Cliente: {profile_name} ({phone})"
                                + f"\n📱 Confirma desde el dashboard: {dashboard_url}"
                            )
                            await send_text(settings.owner_phone, owner_msg)
                    except Exception as e:
                        print(f"Error processing order: {e}")

    return {"status": "ok"}
