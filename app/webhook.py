import json
import re

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from app.bot import (
    CartItem,
    Session,
    build_order_data,
    get_session,
    reset_session,
    sessions,
)
from app.config import settings
from app.database import create_order, get_or_create_customer
from app.menu import (
    MENU,
    find_product,
    format_category_text,
    format_menu_text,
    format_product_detail,
    get_category_names,
    get_products_by_category,
)
from app.whatsapp import send_text

router = APIRouter()


def _parse_number(text: str) -> int | None:
    """Extrae número del mensaje."""
    nums = re.findall(r'\d+', text)
    return int(nums[0]) if nums else None


async def _handle_incoming_message(phone: str, text: str, profile_name: str = ""):
    """Procesa mensajes entrantes del cliente."""
    text = text.strip()
    session = get_session(phone)

    # ---- COMANDOS DE CONTROL ----
    if text.lower() in ("cancelar", "cancel", "salir"):
        reset_session(phone)
        await send_text(phone,
            "❌ Pedido cancelado.\n\nCuando quieras hacer un nuevo pedido, "
            "envía *Hola* o *Menu* 🍽️")
        return

    if text.lower() in ("carrito", "ver carrito", "mi pedido", "5"):
        await _show_cart(phone, session)
        return

    if text.lower() in ("confirmar", "confirmar pedido", "listo", "ya", "6"):
        await _confirm_order(phone, session, profile_name)
        return

    # ---- COMANDO HOLA / MENU ----
    if text.lower() in ("hola", "menu", "pedido", "pedidos", "1", "ver menu"):
        session.state = "main"
        session.cart = []
        menu_text = format_menu_text()
        menu_text += (
            "\n\n📌 *Cómo ordenar:*\n"
            "1️⃣ Envía el *número* de categoría (1-6)\n"
            "2️⃣ Envía el *número* del producto\n"
            "3️⃣ Repite para agregar más\n"
            "4️⃣ Escribe *Carrito* para ver tu pedido\n"
            "5️⃣ Escribe *Confirmar* para enviar tu pedido"
        )
        await send_text(phone, menu_text)
        return

    # ---- SELECCIÓN DE CATEGORÍA ----
    if session.state == "main":
        cat_names = get_category_names()
        num = _parse_number(text)

        if num and 1 <= num <= len(cat_names):
            cat_name = cat_names[num - 1]
            session.state = f"category_{cat_name}"
            cat_text = format_category_text(cat_name)
            await send_text(phone, cat_text)
            return

        # Si no es número, buscar por nombre de categoría
        for cat in MENU:
            if text.lower() == cat.name.lower():
                session.state = f"category_{cat.name}"
                cat_text = format_category_text(cat.name)
                await send_text(phone, cat_text)
                return

        # Si no entendió, mostrar ayuda
        await send_text(phone,
            "📋 Envía *Hola* o *Menu* para ver el menú.\n"
            "O selecciona una categoría (1-6).")
        return

    # ---- SELECCIÓN DE PRODUCTO ----
    if session.state.startswith("category_"):
        cat_name = session.state.replace("category_", "")
        products = get_products_by_category(cat_name)
        num = _parse_number(text)

        if num and 1 <= num <= len(products):
            product = products[num - 1]
            # Agregar al carrito (por defecto 1)
            session.cart.append(CartItem(
                product_name=product.name,
                category=product.category,
                quantity=1,
                unit_price=product.price,
            ))
            total = sum(i.subtotal for i in session.cart)
            await send_text(phone,
                f"✅ *{product.name}* agregado ($/{product.price})\n"
                f"🛒 Carrito: {len(session.cart)} producto(s) — *${total:.0f}*\n\n"
                f"Para agregar más: selecciona otra categoría o producto.\n"
                f"Escribe *Carrito* para ver todo.\n"
                f"Escribe *Confirmar* cuando termines.")
            return

        # Manejo de cantidad: "3x Producto" o "Producto x3"
        match = re.match(r'^(\d+)\s*[xX]\s*(.+)$', text)
        if match:
            qty = int(match.group(1))
            pname = match.group(2).strip()
            product = find_product(pname)
            if product:
                session.cart.append(CartItem(
                    product_name=product.name,
                    category=product.category,
                    quantity=qty,
                    unit_price=product.price,
                ))
                total = sum(i.subtotal for i in session.cart)
                await send_text(phone,
                    f"✅ *{qty}x {product.name}* agregado ($/{product.price * qty})\n"
                    f"🛒 Carrito: {len(session.cart)} producto(s) — *${total:.0f}*")
                return

        await send_text(phone,
            f"❌ Número no válido.\n\n{format_category_text(cat_name)}")
        return

    # ---- COMANDO DESCONOCIDO ----
    await send_text(phone,
        "🤔 No entendí tu mensaje.\n\n"
        "Envía *Hola* para ver el menú.")


async def _show_cart(phone: str, session: Session):
    """Muestra el carrito actual."""
    if not session.cart:
        await send_text(phone,
            "🛒 Tu carrito está vacío.\n\n"
            "Envía *Hola* o *Menu* para ver el menú.")
        return

    lines = ["📋 *TU PEDIDO*\n"]
    for i, item in enumerate(session.cart, 1):
        lines.append(f"{i}️⃣ {item.quantity}x {item.product_name} = *${item.subtotal:.0f}*")

    total = sum(i.subtotal for i in session.cart)
    lines.append(f"\n*Total: ${total:.0f}*")
    lines.append("\n📌 *Confirmar* para enviar tu pedido.")
    lines.append("*Cancelar* para empezar de nuevo.")

    await send_text(phone, "\n".join(lines))


async def _confirm_order(phone: str, session: Session, profile_name: str):
    """Confirma el pedido y lo envía al restaurante."""
    if not session.cart:
        await send_text(phone,
            "🛒 Tu carrito está vacío.\n\n"
            "Envía *Hola* para ver el menú.")
        return

    name = profile_name or "Cliente"
    order_data = build_order_data(phone, name)

    # Guardar cliente y pedido en BD
    customer = get_or_create_customer(phone, name)
    order = create_order(
        customer_id=customer.id,
        items=order_data["items"],
        total=order_data["total"],
    )

    # Notificar al cliente
    items_text = "\n".join(
        f"• {i['quantity']}x {i['product_name']} = ${i['subtotal']:.0f}"
        for i in order_data["items"]
    )
    await send_text(phone,
        f"✅ *PEDIDO # {order.id} ENVIADO*\n\n"
        f"{items_text}\n\n"
        f"*Total: ${order_data['total']:.0f}*\n\n"
        f"⏳ Pendiente de confirmación.\n"
        f"Te notificaremos cuando esté listo. 🎉")

    # Notificar al dueño
    if settings.owner_phone:
        owner_msg = (
            f"🛑 *NUEVO PEDIDO # {order.id}*\n\n"
            + "\n".join(
                f"• {i['quantity']}x {i['product_name']} (${i['subtotal']:.0f})"
                for i in order_data["items"]
            )
            + f"\n\n*Total: ${order_data['total']:.0f}*"
            + f"\n👤 {name} ({phone})"
            + f"\n📱 Confirma desde el dashboard"
        )
        await send_text(settings.owner_phone, owner_msg)

    # Limpiar sesión
    reset_session(phone)


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

                await _handle_incoming_message(phone, text, profile_name)

    return {"status": "ok"}
