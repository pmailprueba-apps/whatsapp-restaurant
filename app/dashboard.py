from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import (
    cancel_order,
    confirm_order,
    get_all_orders,
    get_confirmed_orders,
    get_messages,
    get_order_by_id,
    get_pending_orders,
)
from app.whatsapp import send_order_cancellation, send_order_confirmation
from app.printer import send_ticket_to_printer, send_test_ticket_to_printer

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    pending = get_pending_orders()
    confirmed = get_confirmed_orders()
    all_orders = get_all_orders()
    messages = get_messages(100)
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "pending": pending,
            "confirmed": confirmed,
            "all_orders": all_orders,
            "messages": messages,
            "now": datetime.now,
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
        # Notify customer via WhatsApp
        await send_order_confirmation(
            to=order.customer.phone,
            order_id=order.id,
            items_text=items_text,
            total=order.total,
            pickup_time=pickup_time,
        )
        # Print confirmed ticket with pickup time
        try:
            items_data = [
                {
                    "product_name": i.product_name,
                    "category": i.category,
                    "quantity": i.quantity,
                    "unit_price": i.unit_price,
                    "notes": i.notes,
                    "subtotal": i.subtotal,
                }
                for i in order.items
            ]
            send_ticket_to_printer(
                order_id=order.id,
                customer_name=order.customer.name or order.customer.phone,
                phone=order.customer.phone,
                items=items_data,
                total=order.total,
                pickup_time=pickup_time,
                order_notes=order.notes or "",
            )
        except Exception as pe:
            print(f"[Dashboard] Error sending ticket to printer on confirm: {pe}")

    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/dashboard/print/{order_id}")
async def print_order_route(order_id: int):
    order = get_order_by_id(order_id)
    if order and order.customer:
        items_data = [
            {
                "product_name": i.product_name,
                "category": i.category,
                "quantity": i.quantity,
                "unit_price": i.unit_price,
                "notes": i.notes,
                "subtotal": i.subtotal,
            }
            for i in order.items
        ]
        send_ticket_to_printer(
            order_id=order.id,
            customer_name=order.customer.name or order.customer.phone,
            phone=order.customer.phone,
            items=items_data,
            total=order.total,
            pickup_time=order.pickup_time or "",
            order_notes=order.notes or "",
        )
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/dashboard/test-printer")
async def test_printer_route():
    send_test_ticket_to_printer()
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
