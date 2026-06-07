from datetime import datetime, timezone

from sqlalchemy import desc
from sqlalchemy.orm import joinedload

from app import models


def _get_db():
    return models.SessionLocal()


def get_or_create_customer(phone: str, name: str = "") -> models.Customer:
    db = _get_db()
    try:
        customer = db.query(models.Customer).filter(models.Customer.phone == phone).first()
        if not customer:
            customer = models.Customer(phone=phone, name=name)
            db.add(customer)
            db.commit()
            db.refresh(customer)
        elif name and not customer.name:
            customer.name = name
            db.commit()
            db.refresh(customer)
        return customer
    finally:
        db.close()


def create_order(
    customer_id: int, items: list[dict], total: float, notes: str = ""
) -> models.Order:
    db = _get_db()
    try:
        order = models.Order(
            customer_id=customer_id,
            status="pending",
            total=total,
            notes=notes,
        )
        db.add(order)
        db.flush()

        for item in items:
            oi = models.OrderItem(
                order_id=order.id,
                product_name=item["product_name"],
                category=item["category"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                notes=item.get("notes", ""),
                subtotal=item["subtotal"],
            )
            db.add(oi)

        db.commit()
        db.refresh(order)
        return order
    finally:
        db.close()


def get_pending_orders():
    db = _get_db()
    try:
        return (
            db.query(models.Order)
            .options(joinedload(models.Order.customer), joinedload(models.Order.items))
            .filter(models.Order.status == "pending")
            .order_by(desc(models.Order.created_at))
            .all()
        )
    finally:
        db.close()


def get_confirmed_orders():
    db = _get_db()
    try:
        return (
            db.query(models.Order)
            .options(joinedload(models.Order.customer), joinedload(models.Order.items))
            .filter(models.Order.status.in_(["confirmed", "ready"]))
            .order_by(desc(models.Order.confirmed_at))
            .all()
        )
    finally:
        db.close()


def get_all_orders():
    db = _get_db()
    try:
        return (
            db.query(models.Order)
            .options(joinedload(models.Order.customer), joinedload(models.Order.items))
            .order_by(desc(models.Order.created_at))
            .all()
        )
    finally:
        db.close()


def get_order_by_id(order_id: int) -> models.Order | None:
    db = _get_db()
    try:
        return (
            db.query(models.Order)
            .options(joinedload(models.Order.customer), joinedload(models.Order.items))
            .filter(models.Order.id == order_id)
            .first()
        )
    finally:
        db.close()


def confirm_order(order_id: int, pickup_time: str) -> models.Order | None:
    db = _get_db()
    try:
        order = (
            db.query(models.Order)
            .options(joinedload(models.Order.customer), joinedload(models.Order.items))
            .filter(models.Order.id == order_id)
            .first()
        )
        if order:
            order.status = "confirmed"
            order.pickup_time = pickup_time
            order.confirmed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(order)
        return order
    finally:
        db.close()


def cancel_order(order_id: int) -> models.Order | None:
    db = _get_db()
    try:
        order = (
            db.query(models.Order)
            .options(joinedload(models.Order.customer), joinedload(models.Order.items))
            .filter(models.Order.id == order_id)
            .first()
        )
        if order:
            order.status = "cancelled"
            db.commit()
        return order
    finally:
        db.close()
