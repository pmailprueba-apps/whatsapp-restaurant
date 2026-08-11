from datetime import datetime, timezone

from sqlalchemy import desc
from sqlalchemy.orm import joinedload

from app import models


def _get_db():
    if models.SessionLocal is None:
        from app.config import settings
        models.init_engine(settings.database_url)
        models.init_db()
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


def save_message(phone: str, name: str, text: str, msg_type: str = "text"):
    db = _get_db()
    try:
        msg = models.Message(phone=phone, name=name, text=text, msg_type=msg_type)
        db.add(msg)
        db.commit()
    finally:
        db.close()


def get_messages(limit: int = 50):
    db = _get_db()
    try:
        return (
            db.query(models.Message)
            .order_by(desc(models.Message.created_at))
            .limit(limit)
            .all()
        )
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


def get_sales_analytics(period: str = "today") -> dict:
    from datetime import timedelta
    db = _get_db()
    try:
        now_local = datetime.now()
        
        if period == "today":
            start_dt = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
            period_label = f"Hoy ({now_local.strftime('%d/%m/%Y')})"
        elif period == "week":
            start_dt = (now_local - timedelta(days=now_local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            period_label = f"Esta Semana (desde {start_dt.strftime('%d/%m/%Y')})"
        elif period == "month":
            start_dt = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            period_label = f"Este Mes ({now_local.strftime('%B %Y')})"
        else:  # "all"
            period = "all"
            start_dt = datetime(2000, 1, 1)
            period_label = "Histórico Total"

        query = (
            db.query(models.Order)
            .options(joinedload(models.Order.customer), joinedload(models.Order.items))
            .order_by(desc(models.Order.created_at))
        )
        
        all_period_orders = []
        for o in query.all():
            o_dt = o.created_at
            if o_dt.tzinfo is not None:
                o_dt = o_dt.astimezone().replace(tzinfo=None)
            if o_dt >= start_dt:
                all_period_orders.append(o)

        confirmed_orders = [o for o in all_period_orders if o.status in ("confirmed", "ready")]
        pending_orders = [o for o in all_period_orders if o.status == "pending"]
        cancelled_orders = [o for o in all_period_orders if o.status == "cancelled"]

        total_sales = sum(o.total for o in confirmed_orders)
        total_orders_count = len(confirmed_orders)
        avg_ticket = (total_sales / total_orders_count) if total_orders_count > 0 else 0.0

        # Top products breakdown
        product_stats = {}
        for o in confirmed_orders:
            for item in o.items:
                pname = item.product_name
                if pname not in product_stats:
                    product_stats[pname] = {
                        "name": pname,
                        "category": item.category or "General",
                        "quantity": 0,
                        "revenue": 0.0,
                    }
                product_stats[pname]["quantity"] += item.quantity
                product_stats[pname]["revenue"] += item.subtotal

        top_products = sorted(product_stats.values(), key=lambda x: x["quantity"], reverse=True)
        top_product_name = top_products[0]["name"] if top_products else "Sin ventas aún"

        return {
            "period": period,
            "period_label": period_label,
            "total_sales": total_sales,
            "total_orders": total_orders_count,
            "avg_ticket": avg_ticket,
            "top_product_name": top_product_name,
            "pending_count": len(pending_orders),
            "cancelled_count": len(cancelled_orders),
            "top_products": top_products,
            "orders": all_period_orders,
        }
    finally:
        db.close()

