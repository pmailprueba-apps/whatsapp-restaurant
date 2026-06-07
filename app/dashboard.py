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
from app.whatsapp import send_order_cancellation, send_order_confirmation

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
        await send_order_confirmation(
            to=order.customer.phone,
            order_id=order.id,
            items_text=items_text,
            total=order.total,
            pickup_time=pickup_time,
        )
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/dashboard/cancel/{order_id}")
async def cancel_order_route(order_id: int):
    order = cancel_order(order_id)
    if order and order.customer:
        await send_order_cancellation(
            to=order.customer.phone,
            order_id=order.id,
        )
    return RedirectResponse(url="/dashboard", status_code=303)
