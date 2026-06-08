import json
from datetime import datetime, timezone

from app import models


def _serialize_cart(items):
    return json.dumps([
        {
            "product_name": i.product_name,
            "category": i.category,
            "quantity": i.quantity,
            "unit_price": i.unit_price,
            "notes": i.notes,
        }
        for i in items
    ])


def _deserialize_cart(data: str):
    from app.bot import CartItem
    try:
        items = json.loads(data) if data else []
        return [CartItem(**i) for i in items]
    except (json.JSONDecodeError, TypeError):
        return []


def _serialize_pending(item):
    if item is None:
        return None
    return json.dumps({
        "product_name": item.product_name,
        "category": item.category,
        "quantity": item.quantity,
        "unit_price": item.unit_price,
        "notes": item.notes,
    })


def _deserialize_pending(data: str | None):
    from app.bot import CartItem
    if not data:
        return None
    try:
        return CartItem(**json.loads(data))
    except (json.JSONDecodeError, TypeError):
        return None


def load_session(phone: str):
    from app.bot import Session
    db = models.SessionLocal()
    try:
        row = db.query(models.BotSession).filter(models.BotSession.phone == phone).first()
        if not row:
            return None
        session = Session(phone=phone)
        session.state = row.state
        session.current_category = row.current_category or ""
        session.cart = _deserialize_cart(row.cart_data or "[]")
        session.pending_item = _deserialize_pending(row.pending_item_data)
        return session
    finally:
        db.close()


def save_session(session):
    db = models.SessionLocal()
    try:
        row = db.query(models.BotSession).filter(models.BotSession.phone == session.phone).first()
        if not row:
            row = models.BotSession(phone=session.phone)
            db.add(row)
        row.state = session.state
        row.current_category = session.current_category
        row.cart_data = _serialize_cart(session.cart)
        row.pending_item_data = _serialize_pending(session.pending_item)
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def delete_session(phone: str):
    db = models.SessionLocal()
    try:
        db.query(models.BotSession).filter(models.BotSession.phone == phone).delete()
        db.commit()
    finally:
        db.close()


def load_all_sessions() -> dict:
    from app.bot import Session
    db = models.SessionLocal()
    try:
        rows = db.query(models.BotSession).all()
        result = {}
        for row in rows:
            session = Session(phone=row.phone)
            session.state = row.state
            session.current_category = row.current_category or ""
            session.cart = _deserialize_cart(row.cart_data or "[]")
            session.pending_item = _deserialize_pending(row.pending_item_data)
            result[row.phone] = session
        return result
    finally:
        db.close()
