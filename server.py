from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
import importlib
import sys
import os
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
bot_remote = importlib.import_module("bot-remote")
from app.models import init_engine, init_db
from app.config import settings
from app.database import create_order, get_or_create_customer, save_message
from app.whatsapp import send_text, send_image
from app.printer import send_ticket_to_printer
from app.dashboard import router as dashboard_router
from app.api_menu import router as api_menu_router

app = FastAPI(title="Restaurante Viky Bot & Orders")

# Mount dashboard and API routers
app.include_router(dashboard_router)
app.include_router(api_menu_router)

static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

recent_requests = {}

# Deduplicación por ID único del mensaje de OpenWA (el texto puede repetirse)
processed_message_ids = {}

def is_duplicate_request(phone: str, text: str) -> bool:
    now = time.time()
    key = (phone, text.strip().lower())
    last_time = recent_requests.get(key, 0)
    if len(recent_requests) > 200:
        recent_requests.clear()
    if now - last_time < 2.0:
        return True
    recent_requests[key] = now
    return False

@app.on_event("startup")
async def startup_event():
    init_engine(settings.database_url)
    init_db()
    bot_remote.init_sessions()

@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard", status_code=302)

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    phone = data.get("phone", "")
    text = data.get("text", "")
    profile_name = data.get("profile_name", "") or phone

    if not phone or text is None:
        return {"status": "error", "message": "Missing phone or text"}

    if is_duplicate_request(phone, text):
        print(f"[Server] Ignoring duplicate request from {phone}: {text}")
        return {"status": "ok", "message": "duplicate ignored"}
    
    # Save message in DB for inbox/history
    try:
        save_message(phone, profile_name, text)
    except Exception as e:
        print(f"[Server] Error saving message: {e}")

    # Process message logic
    state, summary = await bot_remote.handle_message(phone, text)

    # If the user confirmed the order, create order in DB and notify customer + owner
    if state == bot_remote.BotState.ORDER_PLACED and summary:
        try:
            session = bot_remote.get_session(phone)
            order_data = bot_remote.build_order_data(phone, profile_name)
            
            if order_data["items"]:
                customer = get_or_create_customer(phone, profile_name)
                order = create_order(
                    customer_id=customer.id,
                    items=order_data["items"],
                    total=order_data["total"],
                )

                item_lines = []
                for i in order_data["items"]:
                    line = f"   • {i['quantity']}x *{i['product_name'].upper()}* = *${i['subtotal']:.0f}*"
                    if i.get("notes"):
                        line += f"\n     └ 📝 _Nota: {i['notes']}_"
                    item_lines.append(line)

                order_summary = (
                    f"📋 *PEDIDO #{order.id} CONFIRMADO Y ENVIADO*\n\n"
                    + "\n".join(item_lines)
                    + f"\n\n💰 *TOTAL: ${order_data['total']:.0f}*"
                    + "\n\n⏳ *ESTADO: PENDIENTE DE CONFIRMACIÓN DEL LOCAL*"
                    + "\n\nTe notificaremos cuando el local confirme tu pedido con la hora de recogida."
                )

                # Send thank you flyer image to customer
                try:
                    img_url = "http://204.168.235.137:8000/static/gracias.png"
                    await send_image(phone, img_url)
                except Exception as img_err:
                    print(f"[Server] Error sending thank you image: {img_err}")

                # Send order summary to customer
                await send_text(phone, order_summary)

                # Send notification to owner
                owner_target = settings.owner_phone or "5214446506790@c.us"
                if owner_target:
                    owner_item_lines = []
                    for i in order_data["items"]:
                        line = f"• {i['quantity']}x *{i['product_name'].upper()}* (${i['subtotal']:.0f})"
                        if i.get("notes"):
                            line += f"\n  └ 📝 _Nota: {i['notes']}_"
                        owner_item_lines.append(line)

                    owner_msg = (
                        f"🛑 *NUEVO PEDIDO #{order.id}*\n\n"
                        + "\n".join(owner_item_lines)
                        + f"\n\n💰 *TOTAL: ${order_data['total']:.0f}*"
                        + f"\n👤 *Cliente:* {profile_name} ({phone})"
                    )
                    await send_text(owner_target, owner_msg)

                # Send ticket to thermal printer via MQTT
                try:
                    send_ticket_to_printer(
                        order_id=order.id,
                        customer_name=profile_name,
                        phone=phone,
                        items=order_data["items"],
                        total=order_data["total"],
                    )
                except Exception as e:
                    print(f"[Server] Error sending ticket to printer: {e}")

                # Clear cart after successfully creating order
                session.cart = []
                bot_remote.save_session(session)
        except Exception as e:
            print(f"[Server] Error processing order: {e}")

    return {"status": "ok", "state": state, "summary": summary}


def _normalize_openwa_phone(chat_id: str, data: dict = None) -> str:
    """Converts OpenWA chatId (e.g. 5214446506790@s.whatsapp.net or ...@lid) to plain identifier."""
    cid = str(chat_id or "").strip()
    if "@lid" in cid:
        if data and data.get("from") and "@c.us" in str(data.get("from")):
            return str(data["from"]).replace("@c.us", "").strip()
        return cid
    digits = "".join(ch for ch in cid.split("@")[0] if ch.isdigit())
    return digits


@app.post("/webhook/openwa")
async def openwa_webhook(request: Request):
    """Receives OpenWA 'message.received' events and feeds them to the bot."""
    try:
        body = await request.json()
    except Exception:
        return {"status": "ok"}

    event = body.get("event", "")
    if event != "message.received":
        return {"status": "ok"}

    data = body.get("data") or {}
    print(f"[OpenWA] DEBUG event={event} data_keys={list(data.keys())} chatId={data.get('chatId')} body={data.get('body')!r} pushName={data.get('pushName')} fromMe={data.get('fromMe')}")
    if data.get("fromMe"):
        return {"status": "ok"}

    chat_id = data.get("chatId", "")
    text = data.get("body") or data.get("text") or ""
    push_name = data.get("pushName") or ""
    msg_id = data.get("id", "") or ""

    phone = _normalize_openwa_phone(chat_id, data)
    if not phone or text is None:
        return {"status": "ok"}

    global processed_message_ids
    # Deduplicar por ID único del mensaje (OpenWA/Baileys reenvía el mismo evento varias veces)
    if msg_id:
        last_seen = processed_message_ids.get(msg_id, 0)
        now_ts = time.time()
        if now_ts - last_seen < 30.0:
            print(f"[Server] Ignoring duplicate message id {msg_id} from {phone}: {text}")
            return {"status": "ok", "message": "duplicate msg_id ignored"}
        processed_message_ids[msg_id] = now_ts
        if len(processed_message_ids) > 500:
            # limpiar entradas viejas (>5 min)
            cutoff = time.time() - 300
            processed_message_ids = {k: v for k, v in processed_message_ids.items() if v > cutoff}

    # Reuse the exact /chat processing logic
    profile_name = push_name or phone

    if is_duplicate_request(phone, text):
        print(f"[Server] Ignoring duplicate request from {phone}: {text}")
        return {"status": "ok", "message": "duplicate ignored"}

    try:
        save_message(phone, profile_name, text)
    except Exception as e:
        print(f"[Server] Error saving message: {e}")

    state, summary = await bot_remote.handle_message(phone, text)

    if state == bot_remote.BotState.ORDER_PLACED and summary:
        try:
            session = bot_remote.get_session(phone)
            order_data = bot_remote.build_order_data(phone, profile_name)

            if order_data["items"]:
                customer = get_or_create_customer(phone, profile_name)
                order = create_order(
                    customer_id=customer.id,
                    items=order_data["items"],
                    total=order_data["total"],
                )

                item_lines = []
                for i in order_data["items"]:
                    line = f"   • {i['quantity']}x *{i['product_name'].upper()}* = *${i['subtotal']:.0f}*"
                    if i.get("notes"):
                        line += f"\n     └ 📝 _Nota: {i['notes']}_"
                    item_lines.append(line)

                order_summary = (
                    f"📋 *PEDIDO #{order.id} CONFIRMADO Y ENVIADO*\n\n"
                    + "\n".join(item_lines)
                    + f"\n\n💰 *TOTAL: ${order_data['total']:.0f}*"
                    + "\n\n⏳ *ESTADO: PENDIENTE DE CONFIRMACIÓN DEL LOCAL*"
                    + "\n\nTe notificaremos cuando el local confirme tu pedido con la hora de recogida."
                )

                try:
                    img_url = "http://204.168.235.137:8000/static/gracias.png"
                    await send_image(phone, img_url)
                except Exception as img_err:
                    print(f"[Server] Error sending thank you image: {img_err}")

                await send_text(phone, order_summary)

                owner_target = settings.owner_phone or "5214446506790@c.us"
                if owner_target:
                    owner_item_lines = []
                    for i in order_data["items"]:
                        line = f"• {i['quantity']}x *{i['product_name'].upper()}* (${i['subtotal']:.0f})"
                        if i.get("notes"):
                            line += f"\n  └ 📝 _Nota: {i['notes']}_"
                        owner_item_lines.append(line)

                    owner_msg = (
                        f"🛑 *NUEVO PEDIDO #{order.id}*\n\n"
                        + "\n".join(owner_item_lines)
                        + f"\n\n💰 *TOTAL: ${order_data['total']:.0f}*"
                        + f"\n👤 *Cliente:* {profile_name} ({phone})"
                    )
                    await send_text(owner_target, owner_msg)

                try:
                    send_ticket_to_printer(
                        order_id=order.id,
                        customer_name=profile_name,
                        phone=phone,
                        items=order_data["items"],
                        total=order_data["total"],
                    )
                except Exception as e:
                    print(f"[Server] Error sending ticket to printer: {e}")

                session.cart = []
                bot_remote.save_session(session)
        except Exception as e:
            print(f"[Server] Error processing order: {e}")

    return {"status": "ok", "state": state, "summary": summary}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
