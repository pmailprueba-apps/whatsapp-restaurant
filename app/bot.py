from dataclasses import dataclass, field

from app.menu import (
    MENU,
    format_category_text,
    format_menu_text,
    format_product_detail,
    get_category_emoji,
    get_category_names,
    get_products_by_category,
)
from app.session_storage import delete_session, load_session, save_session
from app.whatsapp import send_buttons, send_list, send_text


class BotState:
    INIT = "INIT"
    MAIN_MENU = "MAIN_MENU"
    VIEWING_MENU = "VIEWING_MENU"
    VIEWING_INFO = "VIEWING_INFO"
    BROWSING_CATEGORY = "BROWSING_CATEGORY"
    SELECTING_PRODUCT = "SELECTING_PRODUCT"
    SELECTING_QUANTITY = "SELECTING_QUANTITY"
    ADDING_NOTES = "ADDING_NOTES"
    CONFIRMING = "CONFIRMING"
    ADDING_MORE = "ADDING_MORE"
    ORDER_PLACED = "ORDER_PLACED"


@dataclass
class CartItem:
    product_name: str
    category: str
    quantity: int
    unit_price: float
    notes: str = ""
    
    @property
    def subtotal(self) -> float:
        return self.quantity * self.unit_price


@dataclass
class Session:
    phone: str
    state: str = BotState.INIT
    current_category: str = ""
    current_product_idx: int = 0
    cart: list[CartItem] = field(default_factory=list)
    pending_item: CartItem | None = None


sessions: dict[str, Session] = {}


def init_sessions():
    global sessions
    from app.session_storage import load_all_sessions
    sessions = load_all_sessions()


def get_session(phone: str) -> Session:
    if phone not in sessions:
        db_session = load_session(phone)
        if db_session:
            sessions[phone] = db_session
        else:
            sessions[phone] = Session(phone=phone)
    return sessions[phone]


def reset_session(phone: str):
    if phone in sessions:
        del sessions[phone]
    delete_session(phone)


last_closed_notified = {}


def is_restaurant_open() -> tuple[bool, str]:
    """
    Horario de atención oficial:
    - Jueves a Martes: 7:30 PM (19:30) a 2:00 AM (02:00) del día siguiente.
    - Miércoles: Cerrado todo el día / descanso.
    """
    try:
        from zoneinfo import ZoneInfo
        from datetime import datetime
        now = datetime.now(ZoneInfo("America/Mexico_City"))
    except Exception:
        from datetime import datetime
        now = datetime.now()

    hour = now.hour
    minute = now.minute
    weekday = now.weekday()  # 0=Lunes, 1=Martes, 2=Miércoles, 3=Jueves, 4=Viernes, 5=Sábado, 6=Domingo

    # 1. Turno de noche (19:30 a 23:59:59)
    if hour > 19 or (hour == 19 and minute >= 30):
        if weekday == 2:  # Miércoles en la noche
            return False, "Hoy miércoles descansamos."
        return True, "Abierto"

    # 2. Madrugada (00:00 a 01:59:59 - corresponde al turno de la noche anterior)
    elif hour < 2:
        if weekday == 3:  # Jueves en la madrugada (le corresponde el turno del miércoles noche que descansó)
            return False, "Hoy miércoles descansamos."
        return True, "Abierto"

    # 3. Fuera de servicio durante el día (02:00 a 19:29:59)
    else:
        if weekday == 2:
            return False, "Hoy miércoles descansamos. Te esperamos mañana jueves a partir de las 7:30 PM."
        return False, "Abrimos hoy a las 7:30 PM."


async def _send_closed_message(phone: str):
    import time
    now_ts = time.time()
    last_sent = last_closed_notified.get(phone, 0)
    # Cooldown de 5 minutos por número para no spamear
    if now_ts - last_sent < 300:
        return

    last_closed_notified[phone] = now_ts
    closed_msg = (
        "🍽️ *Cenaduría Viky — Hamburguesas y Tacos*\n\n"
        "¡Hola! 👋 En este momento nos encontramos fuera de horario de servicio.\n\n"
        "⏰ *Nuestro horario de atención:*\n"
        "• Jueves a Martes: *7:30 PM a 2:00 AM*\n"
        "• Miércoles: *Cerrado (Descanso)*\n\n"
        "📍 *Ubicación:* Prolongación Moctezuma 2140, Tercera Grande 2\n"
        "🗺️ *Google Maps:* https://maps.app.goo.gl/67C7AgADex3V8t8i9\n\n"
        "¡Te esperamos con gusto en nuestro horario de servicio para tomar tu pedido! 🍔🌮🎉"
    )
    await send_text(phone, closed_msg)


async def handle_message(phone: str, text: str) -> tuple[str, str | None]:
    raw_text = text.strip().lower()
    
    # Comprobar horario de atención (permite comando de prueba /test_open)
    is_open, _ = is_restaurant_open()
    if not is_open and raw_text != "/test_open":
        await _send_closed_message(phone)
        return BotState.INIT, None

    session = get_session(phone)
    text = raw_text
    
    def auto(new_state, summary):
        session.state = new_state
        save_session(session)
        return new_state, summary
    
    if text in ["/start", "hola", "buenas", "menu", "menú"]:
        session.cart = []
        return auto(*(await _show_main_menu(phone)))

    if session.state == BotState.INIT:
        return auto(*(await _show_main_menu(phone)))

    if session.state == BotState.MAIN_MENU:
        return auto(*(await _handle_main_menu(phone, text, session)))

    if session.state == BotState.VIEWING_MENU:
        return auto(*(await _handle_viewing_menu(phone, text, session)))

    if session.state == BotState.VIEWING_INFO:
        return auto(*(await _handle_viewing_info(phone, text, session)))

    if session.state == BotState.BROWSING_CATEGORY:
        return auto(*(await _handle_category_selection(phone, text, session)))

    if session.state == BotState.SELECTING_PRODUCT:
        return auto(*(await _handle_product_selection(phone, text, session)))

    if session.state == BotState.SELECTING_QUANTITY:
        return auto(*(await _handle_quantity(phone, text, session)))

    if session.state == BotState.ADDING_NOTES:
        return auto(*(await _handle_notes(phone, text, session)))

    if session.state == BotState.CONFIRMING:
        return auto(*(await _handle_confirmation(phone, text, session)))

    if session.state == BotState.ADDING_MORE:
        return auto(*(await _handle_adding_more(phone, text, session)))

    if session.state == BotState.ORDER_PLACED:
        return auto(*(await _handle_post_order(phone, text, session)))

    return auto(*(await _show_main_menu(phone)))


async def _show_main_menu(phone: str) -> tuple[str, str | None]:
    menu = (
        "🍽️ *Cenaduría Viky — Hamburguesas y Tacos*\n\n"
        "¡Bienvenido! 🎉 Elige una opción:\n\n"
        "1️⃣ *Ver Menú*\n"
        "2️⃣ *Hacer Pedido*\n"
        "3️⃣ *Información y Horario*\n\n"
        "Responde el *número* de tu opción:"
    )
    await send_text(phone, menu)
    return BotState.MAIN_MENU, None


async def _handle_main_menu(phone: str, text: str, session: Session) -> tuple[str, str | None]:
    if text in ["ver_menu", "ver menú", "menu", "menú", "1"]:
        menu_text = format_menu_text()
        menu_text += "\n\n━━━━━━━━━━━━━━━━━━━━\n¿Quieres hacer un pedido? Responde:\n1️⃣ Sí, hacer pedido\n2️⃣ Volver al menú"
        await send_text(phone, menu_text)
        return BotState.VIEWING_MENU, None

    if text in ["hacer_pedido", "hacer pedido", "pedido", "orden", "2"]:
        return await _show_category_list(phone)

    if text in ["informacion", "información", "info", "horario", "direccion", "dirección", "ubicacion", "ubicación", "maps", "3"]:
        info = (
            "📍 *Dirección:* Prolongación Moctezuma 2140, Tercera Grande 2, 78143 San Luis Potosí, S.L.P.\n"
            "🗺️ *Google Maps:* https://maps.app.goo.gl/67C7AgADex3V8t8i9\n"
            "🕐 *Horario de Atención:*\n"
            "   • Jueves a Martes: *7:30 PM a 2:00 AM*\n"
            "   • *Miércoles:* CERRADO (Descanso)\n"
            "📱 *WhatsApp de Pedidos:* +52 1 444 650 6790\n"
            "💵 *Forma de pago:* Efectivo al recoger en local\n\n"
            "¿En qué más puedo ayudarte?\n\n"
            "1️⃣ Hacer Pedido\n2️⃣ Menú Principal"
        )
        await send_text(phone, info)
        return BotState.VIEWING_INFO, None

    if text in ["volver", "main", "menu principal", "atras"]:
        return await _show_main_menu(phone)

    return await _show_main_menu(phone)


async def _handle_viewing_menu(phone: str, text: str, session: Session) -> tuple[str, str | None]:
    if text in ["1", "si", "sí", "hacer_pedido", "hacer pedido", "pedido", "orden"]:
        return await _show_category_list(phone)

    if text in ["2", "no", "volver", "menu principal", "menu", "menú"]:
        return await _show_main_menu(phone)

    await send_text(phone, "Responde:\n1️⃣ Sí, quiero pedir\n2️⃣ Volver al menú")
    return BotState.VIEWING_MENU, None


async def _handle_viewing_info(phone: str, text: str, session: Session) -> tuple[str, str | None]:
    if text in ["1", "hacer_pedido", "hacer pedido", "pedido", "orden"]:
        return await _show_category_list(phone)

    if text in ["2", "volver", "menu principal", "menu", "menú"]:
        return await _show_main_menu(phone)

    await send_text(phone, "Responde:\n1️⃣ Hacer Pedido\n2️⃣ Menú Principal")
    return BotState.VIEWING_INFO, None


async def _show_category_list(phone: str) -> tuple[str, str | None]:
    sections = [
        {
            "title": cat.emoji + " " + cat.name,
            "rows": [
                {
                    "id": f"cat_{cat.name}",
                    "title": f"{cat.emoji} {cat.name}",
                    "description": f"Ver productos",
                }
            ],
        }
        for cat in MENU
    ]

    await send_list(
        phone,
        "🛒 Nuevo Pedido",
        "Selecciona una categoría:",
        "Ver categorías",
        sections,
    )
    return BotState.BROWSING_CATEGORY, None


async def _handle_category_selection(phone: str, text: str, session: Session) -> tuple[str, str | None]:
    if text in ["volver", "atras", "atrás", "cancelar", "salir", "menu", "menú"]:
        return await _show_main_menu(phone)

    # Mapeo numérico para fallback de texto
    cat_names = get_category_names()
    try:
        idx = int(text) - 1
        if 0 <= idx < len(cat_names):
            cat_name = cat_names[idx]
            session.current_category = cat_name
            cat_text = format_category_text(cat_name)
            if cat_text:
                await send_text(phone, cat_text)
                return BotState.SELECTING_PRODUCT, None
    except (ValueError, TypeError):
        pass

    if text.startswith("cat_"):
        category = text[4:]
        session.current_category = category
        cat_text = format_category_text(category)
        if cat_text:
            await send_text(phone, cat_text)
            return BotState.SELECTING_PRODUCT, None

    for cat_name in cat_names:
        cat_lower = cat_name.lower()
        cat_singular = cat_lower[:-1] if cat_lower.endswith('s') else cat_lower
        if cat_lower in text or text == cat_lower or cat_singular in text:
            session.current_category = cat_name
            cat_text = format_category_text(cat_name)
            if cat_text:
                await send_text(phone, cat_text)
                return BotState.SELECTING_PRODUCT, None

    await send_text(phone, "Elige una categoría de la lista 👆")
    return BotState.BROWSING_CATEGORY, None


async def _handle_product_selection(phone: str, text: str, session: Session) -> tuple[str, str | None]:
    if text in ["volver", "atras", "atrás"]:
        return await _show_category_list(phone)
    if text in ["cancelar", "salir", "menu", "menú"]:
        session.cart = []
        return await _show_main_menu(phone)

    products = get_products_by_category(session.current_category)
    if not products:
        await send_text(phone, "Error: categoría no encontrada. Intenta de nuevo.")
        return await _show_category_list(phone)

    try:
        idx = int(text) - 1
        if idx == len(products):
            return await _show_category_list(phone)
        if idx == len(products) + 1:
            session.cart = []
            await send_text(phone, "❌ *PEDIDO CANCELADO.* ¿Necesitas algo más?")
            return await _show_main_menu(phone)
        if 0 <= idx < len(products):
            product = products[idx]
        else:
            raise ValueError
    except (ValueError, TypeError):
        for product in products:
            if product.name.lower() in text.lower():
                idx = products.index(product)
                break
        else:
            emoji = get_category_emoji(session.current_category)
            await send_text(
                phone,
                f"Número inválido. Responde el *número* (1-{len(products) + 2}) de tu opción de {emoji} *{session.current_category}*:",
            )
            return BotState.SELECTING_PRODUCT, None

    product = products[idx]
    session.pending_item = CartItem(
        product_name=product.name,
        category=session.current_category,
        quantity=1,
        unit_price=product.price,
    )
    await send_text(
        phone,
        f"{format_product_detail(product)}\n\n¿Cuántas quieres? (responde un número)",
    )
    return BotState.SELECTING_QUANTITY, None


async def _handle_quantity(phone: str, text: str, session: Session) -> tuple[str, str | None]:
    if text in ["volver", "atras", "atrás"]:
        cat_text = format_category_text(session.current_category)
        if cat_text:
            await send_text(phone, cat_text)
            return BotState.SELECTING_PRODUCT, None
        return await _show_category_list(phone)
    if text in ["cancelar", "salir", "menu", "menú"]:
        session.cart = []
        session.pending_item = None
        return await _show_main_menu(phone)

    try:
        qty = int(text)
        if qty < 1 or qty > 99:
            raise ValueError
    except (ValueError, TypeError):
        await send_text(phone, "Por favor responde un número válido (1-99):")
        return BotState.SELECTING_QUANTITY, None

    session.pending_item.quantity = qty

    emoji = get_category_emoji(session.pending_item.category)
    name = session.pending_item.product_name
    subtotal = session.pending_item.subtotal

    await send_text(
        phone,
        f"{emoji} {qty}x *{name}* = ${subtotal:.0f}\n\n"
        "¿Alguna nota o extra? (ej: 'sin cebolla', 'bien cocida')\n"
        "O responde *no* si no necesitas nada:",
    )
    return BotState.ADDING_NOTES, None


async def _handle_notes(phone: str, text: str, session: Session) -> tuple[str, str | None]:
    if text in ["volver", "atras", "atrás"]:
        from app.menu import find_product
        product = find_product(session.pending_item.product_name)
        await send_text(
            phone,
            f"{format_product_detail(product)}\n\n¿Cuántas quieres? (responde un número)",
        )
        return BotState.SELECTING_QUANTITY, None
    if text in ["cancelar", "salir", "menu", "menú"]:
        session.cart = []
        session.pending_item = None
        return await _show_main_menu(phone)

    item = session.pending_item
    if text.lower() not in ["no", "nada", "ninguna", "ninguno", "sin notas"]:
        item.notes = text

    session.cart.append(item)
    session.pending_item = None

    total = sum(i.subtotal for i in session.cart)
    cart_lines = []
    for i in session.cart:
        line = f"   • {i.quantity}x *{i.product_name.upper()}* = *${i.subtotal:.0f}*"
        if i.notes:
            line += f"\n     └ 📝 _Nota: {i.notes}_"
        cart_lines.append(line)

    cart_text = "🛒 *RESUMEN DE TU PEDIDO:*\n\n" + "\n".join(cart_lines) + f"\n\n💰 *TOTAL: ${total:.0f}*"

    await send_text(phone, cart_text)
    await send_buttons(phone, "OPCIONES DISPONIBLES", "Selecciona una opción para continuar:", [
        {"type": "reply", "reply": {"id": "confirmar_pedido", "title": "CONFIRMAR Y ENVIAR PEDIDO"}},
        {"type": "reply", "reply": {"id": "agregar_mas", "title": "AGREGAR MÁS PRODUCTOS"}},
        {"type": "reply", "reply": {"id": "cancelar_pedido", "title": "CANCELAR PEDIDO"}},
    ])
    return BotState.CONFIRMING, None


async def _handle_confirmation(phone: str, text: str, session: Session) -> tuple[str, str | None]:
    if text in ["confirmar_pedido", "confirmar", "confirm", "1", "1️⃣"]:
        total = sum(i.subtotal for i in session.cart)
        summary_lines = []
        for i in session.cart:
            line = f"   • {i.quantity}x *{i.product_name.upper()}* = *${i.subtotal:.0f}*"
            if i.notes:
                line += f"\n     └ 📝 _Nota: {i.notes}_"
            summary_lines.append(line)

        summary = "📋 *RESUMEN DE TU PEDIDO*\n\n" + "\n".join(summary_lines) + f"\n\n💰 *TOTAL: ${total:.0f}*"
        summary += "\n\n⏳ *ESTADO: PENDIENTE DE CONFIRMACIÓN DEL LOCAL*"

        session.state = BotState.ORDER_PLACED
        save_session(session)
        return BotState.ORDER_PLACED, summary

    if text in ["agregar_mas", "agregar más", "2", "2️⃣"]:
        return await _show_category_list(phone)

    if text in ["cancelar_pedido", "cancelar", "cancel", "3", "3️⃣"]:
        session.cart = []
        session.state = BotState.MAIN_MENU
        save_session(session)
        await send_text(phone, "❌ *PEDIDO CANCELADO.* ¿Necesitas algo más?")
        await send_buttons(phone, "MENÚ PRINCIPAL", "", [
            {"type": "reply", "reply": {"id": "hacer_pedido", "title": "NUEVO PEDIDO"}},
            {"type": "reply", "reply": {"id": "volver", "title": "MENÚ PRINCIPAL"}},
        ])
        return BotState.MAIN_MENU, None

    await send_text(phone, "Opción no válida. Usa los números de la lista 👇")
    return BotState.CONFIRMING, None


async def _handle_adding_more(phone: str, text: str, session: Session) -> tuple[str, str | None]:
    return await _show_category_list(phone)


async def _handle_post_order(phone: str, text: str, session: Session) -> tuple[str, str | None]:
    if text in ["nuevo_pedido", "nuevo pedido", "otro pedido", "1", "1️⃣"]:
        session.cart = []
        return await _show_main_menu(phone)

    await send_text(
        phone,
        "Tu pedido ya fue enviado. Espera la confirmación del local. 🕐\n\n"
        "¿Quieres hacer otro pedido?",
    )
    await send_buttons(phone, "🔄 ¿Otro pedido?", "", [
        {"type": "reply", "reply": {"id": "nuevo_pedido", "title": "🛒 Nuevo Pedido"}},
    ])
    return BotState.ORDER_PLACED, None


def build_order_data(phone: str, name: str) -> dict:
    session = get_session(phone)
    total = sum(i.subtotal for i in session.cart)
    items_data = [
        {
            "product_name": i.product_name,
            "category": i.category,
            "quantity": i.quantity,
            "unit_price": i.unit_price,
            "notes": i.notes,
            "subtotal": i.subtotal,
        }
        for i in session.cart
    ]
    return {
        "phone": phone,
        "customer_name": name,
        "total": total,
        "items": items_data,
    }
