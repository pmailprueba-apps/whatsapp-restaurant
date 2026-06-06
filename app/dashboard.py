from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.database import (
    cancel_order,
    confirm_order,
    get_all_orders,
    get_confirmed_orders,
    get_order_by_id,
    get_pending_orders,
)
from app.whatsapp import send_text

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    pending = get_pending_orders()
    confirmed = get_confirmed_orders()
    all_orders = get_all_orders()
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "pending": pending,
            "confirmed": confirmed,
            "all_orders": all_orders,
        },
    )


@router.post("/dashboard/confirm/{order_id}")
async def confirm_order_route(order_id: int, pickup_time: str = Form(...)):
    order = confirm_order(order_id, pickup_time)
    if order and order.customer:
        items_text = "\n".join(
            f"• {i.quantity}x {i.product_name} = ${i.subtotal:.0f}"
            for i in order.items
        )
        msg = (
            f"✅ *PEDIDO # {order.id} CONFIRMADO*\n\n"
            f"{items_text}\n\n"
            f"*Total: ${order.total:.0f}*\n\n"
            f"🕐 *Recoge a las: {pickup_time}*\n\n"
            f"📍 Pasa al local y paga en efectivo. ¡Te esperamos! 🎉"
        )
        await send_text(order.customer.phone, msg)
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/dashboard/cancel/{order_id}")
async def cancel_order_route(order_id: int):
    order = cancel_order(order_id)
    if order and order.customer:
        await send_text(
            order.customer.phone,
            f"❌ *PEDIDO # {order.id} CANCELADO*\n\n"
            "Lo sentimos, tu pedido ha sido cancelado. "
            "Puedes hacer un nuevo pedido cuando quieras.",
        )
    return RedirectResponse(url="/dashboard", status_code=303)
