import json
import re

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from app.bot import (
    BotState,
    build_order_data,
    get_session,
    reset_session,
    handle_message,
)
from app.config import settings
from app.database import create_order, get_or_create_customer
from app.whatsapp import send_text

router = APIRouter()


# Text bot fallback removed, using bot.py interactive state machine.


# ============================================================
# WEBHOOKS (ManyChat y Meta)
# ============================================================

@router.get("/webhook/whatsapp")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    expected = settings.manychat_verify_token or settings.whatsapp_verify_token
    if mode == "subscribe" and token == expected:
        return PlainTextResponse(challenge)
    return PlainTextResponse("Verification failed", status_code=403)


@router.post("/webhook/whatsapp")
async def receive_message(request: Request):
    try:
        body = await request.json()
    except Exception:
        return {"status": "error", "detail": "invalid json"}

    if "event" in body:
        return await _handle_manychat_event(body)

    if "entry" in body:
        return await _handle_meta_webhook(body)

    return {"status": "ok"}


@router.post("/webhook/n8n")
async def receive_n8n_webhook(request: Request):
    try:
        body = await request.json()
    except Exception:
        return {"status": "error", "detail": "invalid json"}

    if isinstance(body, dict) and body.get("entry"):
        return await _handle_meta_webhook(body)

    if isinstance(body, dict) and body.get("order_confirmed"):
        await _process_order_confirmed(body.get("data", {}))
        return {"status": "ok", "order_created": True}

    return {"status": "ok"}


async def _process_order_confirmed(data: dict):
    phone = data.get("phone", "")
    name = data.get("customer_name", "Cliente")
    items = data.get("items", [])
    total = data.get("total", 0)

    if not phone or not items:
        return

    customer = get_or_create_customer(phone, name)
    clean_items = []
    for item in items:
        clean_items.append({
            "product_name": item.get("product_name", ""),
            "category": item.get("category", ""),
            "quantity": item.get("quantity", 1),
            "unit_price": item.get("unit_price", 0),
            "notes": item.get("notes", ""),
            "subtotal": item.get("subtotal", 0),
        })

    order = create_order(
        customer_id=customer.id,
        items=clean_items,
        total=total,
    )

    order_summary = (
        f"📋 *PEDIDO # {order.id}*\n\n"
        + "\n".join(
            f"   • {i['quantity']}x {i['product_name']} = ${i['subtotal']:.0f}"
            for i in clean_items
        )
        + f"\n\n*Total: ${total:.0f}*"
        + "\n\n⏳ *Pendiente de confirmación*"
        + "\n\nTe notificaremos cuando el local confirme tu pedido."
    )
    await send_text(phone, order_summary)

    if settings.owner_phone:
        owner_msg = (
            f"🛑 *NUEVO PEDIDO # {order.id}*\n\n"
            + "\n".join(
                f"• {i['quantity']}x {i['product_name']} (${i['subtotal']:.0f})"
                for i in items
            )
            + f"\n\n*Total: ${total:.0f}*"
            + f"\n👤 Cliente: {name} ({phone})"
            + f"\n📱 Confirma desde el dashboard"
        )
        await send_text(settings.owner_phone, owner_msg)


async def _handle_manychat_event(body: dict):
    """Maneja eventos entrantes de ManyChat (gratis - inbound only)."""
    event = body.get("event", "")
    data = body.get("data", {})

    if event == "lead_property_updated":
        subscriber_id = data.get("subscriber_id")
        field_name = data.get("field_name", "")
        new_value = data.get("new_value", "")

        if field_name == "order_data":
            await _process_manychat_order(subscriber_id, new_value)
        elif field_name == "subscriber_phone":
            await _link_subscriber_phone(subscriber_id, new_value)

    elif event == "message_received":
        subscriber_id = data.get("subscriber_id")
        _maybe_capture_subscriber(subscriber_id)

    return {"status": "ok"}


async def _process_manychat_order(subscriber_id: str | int, order_json: str):
    """Procesa pedido enviado desde ManyChat flow (requiere ManyChat Pro)."""
    try:
        order_data = json.loads(order_json) if isinstance(order_json, str) else order_json
    except json.JSONDecodeError:
        return

    phone = order_data.get("phone", "")
    name = order_data.get("customer_name", "Cliente")
    items = order_data.get("items", [])
    total = order_data.get("total", 0)

    if not phone:
        return

    customer = get_or_create_customer(phone, name)
    if not customer.manychat_id:
        from app.database import _get_db
        db = _get_db()
        try:
            customer.manychat_id = str(subscriber_id)
            db.commit()
        finally:
            db.close()

    order = create_order(
        customer_id=customer.id,
        items=items,
        total=total,
    )

    order_summary = (
        f"📋 *PEDIDO # {order.id}*\n\n"
        + "\n".join(
            f"   • {i['quantity']}x {i['product_name']} = ${i['subtotal']:.0f}"
            for i in items
        )
        + f"\n\n*Total: ${total:.0f}*"
        + "\n\n⏳ *Pendiente de confirmación*"
        + "\n\nTe notificaremos cuando el local confirme tu pedido."
    )
    await send_text(phone, order_summary)

    if settings.owner_phone:
        owner_msg = (
            f"🛑 *NUEVO PEDIDO # {order.id}*\n\n"
            + "\n".join(
                f"• {i['quantity']}x {i['product_name']} (${i['subtotal']:.0f})"
                for i in items
            )
            + f"\n\n*Total: ${total:.0f}*"
            + f"\n👤 Cliente: {name} ({phone})"
            + f"\n📱 Confirma desde el dashboard"
        )
        await send_text(settings.owner_phone, owner_msg)


async def _link_subscriber_phone(subscriber_id: str | int, phone: str):
    """Vincula subscriber_id de ManyChat a un cliente."""
    from app.database import _get_db
    from app.models import Customer
    db = _get_db()
    try:
        customer = db.query(Customer).filter(Customer.phone == phone).first()
        if customer:
            customer.manychat_id = str(subscriber_id)
            db.commit()
    finally:
        db.close()


def _maybe_capture_subscriber(subscriber_id: str | int):
    """Guarda el subscriber_id de ManyChat cuando el cliente envía un mensaje."""
    if not subscriber_id:
        return
    from app.database import _get_db
    from app.models import Customer
    db = _get_db()
    try:
        customer = db.query(Customer).filter(
            Customer.manychat_id == None
        ).first()
        if customer:
            customer.manychat_id = str(subscriber_id)
            db.commit()
    except Exception as e:
        print(f"[_maybe_capture_subscriber] error: {e}")
    finally:
        db.close()


async def _handle_meta_webhook(body: dict) -> dict:
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
                    except Exception as e:
                        print(f"Error processing order: {e}")

    return {"status": "ok"}
