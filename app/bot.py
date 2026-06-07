from dataclasses import dataclass, field

from app.menu import MENU


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
    cart: list[CartItem] = field(default_factory=list)
    state: str = ""


sessions: dict[str, Session] = {}


def get_session(phone: str) -> Session:
    if phone not in sessions:
        sessions[phone] = Session(phone=phone)
    return sessions[phone]


def reset_session(phone: str):
    if phone in sessions:
        del sessions[phone]


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
