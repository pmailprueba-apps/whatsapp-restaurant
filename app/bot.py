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


async def handle_message(phone: str, text: str) -> tuple[str, str | None]:
    session = get_session(phone)
    text = text.strip().lower()
    
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
        "🍽️ *Tacos y Hamburguesas El Compa*\n\n"
        "¡Bienvenido! 🎉 Elige una opción:\n\n"
        "1️⃣ *Ver Menú*\n"
        "2️⃣ *Hacer Pedido*\n"
        "3️⃣ *Información*\n\n"
        "Responde el *número* de tu opción:"
    )
    await send_text(phone, menu)
    return BotState.MAIN_MENU, None


async def _handle_main_menu(phone: str, text: str, session: Session) -> tuple[str, str | None]:
    if text in ["ver_menu", "ver menú", "menu", "menú", "1"]:
        menu_text = format_menu_text()
        menu_text += "\n\n¿Quieres hacer un pedido?"
        await send_text(phone, menu_text)
        await send_text(phone, "¿Quieres hacer un pedido? Responde:\n1️⃣ Sí\n2️⃣ Volver al menú")
        return BotState.VIEWING_MENU, None

    if text in ["hacer_pedido", "hacer pedido", "pedido", "orden", "2"]:
        return await _show_category_list(phone)

    if text in ["informacion", "información", "info", "horario", "direccion", "3"]:
        info = (
            "📍 *Dirección:* Calle Melchor Ocampo 120, Zona Centro\n"
            "🕐 *Horario:* Lunes a Domingo 11:00 AM - 11:00 PM\n"
            "📱 *Teléfono:* +52 1 444 650 6790\n"
            "💵 *Forma de pago:* Efectivo en local\n\n"
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

    if text.startswith("cat_"):
        category = text[4:]
        session.current_category = category
        cat_text = format_category_text(category)
        if cat_text:
            await send_text(phone, cat_text)
            return BotState.SELECTING_PRODUCT, None

    for cat_name in get_category_names():
        if cat_name.lower() in text or text == cat_name.lower():
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
                f"Número inválido. Responde el *número* (1-{len(products)}) del producto que deseas de {emoji} *{session.current_category}*:",
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
    cart_lines = [f"   • {i.quantity}x {i.product_name} = ${i.subtotal:.0f}" for i in session.cart]
    cart_text = "🛒 *Tu pedido:*\n" + "\n".join(cart_lines) + f"\n\n*Total: ${total:.0f}*"

    await send_text(phone, cart_text)
    await send_buttons(phone, "📋 ¿Qué sigue?", "¿Quieres agregar algo más?", [
        {"type": "reply", "reply": {"id": "agregar_mas", "title": "✅ Agregar más"}},
        {"type": "reply", "reply": {"id": "confirmar_pedido", "title": "📋 Confirmar"}},
        {"type": "reply", "reply": {"id": "cancelar_pedido", "title": "🗑️ Cancelar"}},
    ])
    return BotState.CONFIRMING, None


async def _handle_confirmation(phone: str, text: str, session: Session) -> tuple[str, str | None]:
    if text in ["agregar_mas", "agregar más", "si", "sí"]:
        return await _show_category_list(phone)

    if text in ["confirmar_pedido", "confirmar", "confirm"]:
        total = sum(i.subtotal for i in session.cart)
        summary_lines = [f"   • {i.quantity}x {i.product_name} = ${i.subtotal:.0f}" for i in session.cart]
        summary = "📋 *RESUMEN DE TU PEDIDO*\n\n" + "\n".join(summary_lines) + f"\n\n*Total: ${total:.0f}*"
        summary += "\n\n✅ Pedido enviado. Espera la confirmación del local con la hora de recogida."

        session.state = BotState.ORDER_PLACED
        save_session(session)
        return BotState.ORDER_PLACED, summary

    if text in ["cancelar_pedido", "cancelar", "cancel"]:
        session.cart = []
        session.state = BotState.MAIN_MENU
        save_session(session)
        await send_text(phone, "❌ Pedido cancelado. ¿Necesitas algo más?")
        await send_buttons(phone, "🔙 Volver", "", [
            {"type": "reply", "reply": {"id": "hacer_pedido", "title": "🛒 Nuevo Pedido"}},
            {"type": "reply", "reply": {"id": "volver", "title": "🔙 Menú Principal"}},
        ])
        return BotState.MAIN_MENU, None

    await send_text(phone, "Opción no válida. Usa los botones de abajo 👇")
    return BotState.CONFIRMING, None


async def _handle_adding_more(phone: str, text: str, session: Session) -> tuple[str, str | None]:
    return await _show_category_list(phone)


async def _handle_post_order(phone: str, text: str, session: Session) -> tuple[str, str | None]:
    if text in ["nuevo_pedido", "nuevo pedido", "otro pedido"]:
        session.cart = []
        session.state = BotState.MAIN_MENU
        save_session(session)
        return await _show_category_list(phone)

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
