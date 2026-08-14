from datetime import datetime
import hashlib
import hmac
import os
from pathlib import Path
from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database import (
    cancel_order,
    confirm_order,
    get_all_orders,
    get_confirmed_orders,
    get_messages,
    get_order_by_id,
    get_pending_orders,
    get_sales_analytics,
)
from app.whatsapp import send_order_cancellation, send_order_confirmation
from app.printer import send_ticket_to_printer, send_test_ticket_to_printer
from app.bot import reset_session

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

def _to_slp_time(dt) -> str:
    if not dt:
        return ""
    try:
        from zoneinfo import ZoneInfo
        from datetime import timezone
        if dt.tzinfo is None:
            dt_utc = dt.replace(tzinfo=timezone.utc)
        else:
            dt_utc = dt
        dt_slp = dt_utc.astimezone(ZoneInfo("America/Mexico_City"))
        return dt_slp.strftime("%d/%m/%Y %I:%M %p")
    except Exception:
        return dt.strftime("%d/%m/%Y %H:%M") if hasattr(dt, "strftime") else str(dt)

def _format_display_phone(phone_str: str) -> str:
    if not phone_str:
        return "Cliente"
    clean = str(phone_str).replace("@c.us", "").replace("@s.whatsapp.net", "").replace("@lid", "").strip()
    if clean.startswith("521") and len(clean) == 13:
        return f"+52 ({clean[3:6]}) {clean[6:9]}-{clean[9:]}"
    elif clean.startswith("52") and len(clean) == 12:
        return f"+52 ({clean[2:5]}) {clean[5:8]}-{clean[8:]}"
    elif len(clean) == 10:
        return f"({clean[:3]}) {clean[3:6]}-{clean[6:]}"
    return clean

templates.env.filters["slp_time"] = _to_slp_time
templates.env.filters["display_phone"] = _format_display_phone

COOKIE_NAME = "viky_session"


def _generate_token(username: str) -> str:
    secret = getattr(settings, "secret_key", "viky_secret_session_key_2026_auth")
    sig = hmac.new(secret.encode(), username.lower().strip().encode(), hashlib.sha256).hexdigest()
    return f"{username}:{sig}"


def _is_authenticated(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME)
    if not token or ":" not in token:
        return False
    username, sig = token.split(":", 1)
    expected_token = _generate_token(username)
    expected_sig = expected_token.split(":", 1)[1]
    if not hmac.compare_digest(sig, expected_sig):
        return False
    allowed_user = getattr(settings, "dashboard_user", "Admin").lower().strip()
    return username.lower().strip() == allowed_user


# --- AUTH ROUTES ---

@router.get("/qr", response_class=HTMLResponse)
async def qr_page(request: Request):
    import httpx, base64
    qr_img = ""
    status = "desconocido"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                "http://localhost:2785/api/sessions/0f97e6b0-4c49-47f7-a3fa-61ae42969add/qr",
                headers={"X-API-Key": "dev-key-cambiar-en-prod"}
            )
            data = resp.json()
            qr_img = data.get("qrCode") or data.get("qr") or ""
            status = data.get("status") or "qr_ready"
    except Exception as e:
        status = f"Error: {e}"

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Escanear QR WhatsApp - Cenaduría Viky</title>
    <meta http-equiv="refresh" content="4">
    <style>
        body {{ background: #0f172a; color: white; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; box-sizing: border-box; text-align: center; }}
        .card {{ background: #1e293b; padding: 36px 28px; border-radius: 24px; box-shadow: 0 20px 40px rgba(0,0,0,0.6); max-width: 420px; width: 100%; border: 1px solid rgba(255,255,255,0.1); }}
        h1 {{ color: #25D366; font-size: 22px; margin-top: 0; margin-bottom: 8px; }}
        p {{ color: #94a3b8; font-size: 14px; line-height: 1.5; margin-bottom: 20px; }}
        .qr-box {{ background: white; padding: 16px; border-radius: 16px; display: inline-block; box-shadow: 0 4px 20px rgba(0,0,0,0.3); }}
        img {{ max-width: 280px; width: 100%; height: auto; display: block; }}
        .badge {{ display: inline-block; background: rgba(37, 211, 102, 0.15); color: #25D366; padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; margin-bottom: 16px; }}
        .note {{ font-size: 12px; color: #64748b; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="badge">● Estado: {status}</div>
        <h1>📱 Vincular WhatsApp</h1>
        <p>Abre WhatsApp en el celular del restaurante (<b>+52 444 650 6790</b>)<br>Ve a <b>Dispositivos vinculados</b> &gt; <b>Vincular un dispositivo</b></p>
        <div class="qr-box">
            <img src="{qr_img}" alt="Código QR WhatsApp" />
        </div>
        <div class="note">Esta página se actualiza automáticamente cada 4 segundos.</div>
    </div>
</body>
</html>"""
    return HTMLResponse(content=html)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if _is_authenticated(request):
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": None},
    )


@router.post("/login")
async def login_submit(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
):
    expected_user = getattr(settings, "dashboard_user", "Admin").strip()
    expected_pass = getattr(settings, "dashboard_password", "Amortiguador").strip()

    if username.strip().lower() == expected_user.lower() and password.strip() == expected_pass:
        token = _generate_token(expected_user)
        redirect = RedirectResponse(url="/dashboard", status_code=303)
        # 30 days session
        redirect.set_cookie(
            key=COOKIE_NAME,
            value=token,
            max_age=60 * 60 * 24 * 30,
            httponly=True,
            samesite="lax",
        )
        return redirect

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": "Usuario o contraseña incorrectos. Intenta de nuevo."},
        status_code=401,
    )


@router.get("/logout")
async def logout():
    redirect = RedirectResponse(url="/login", status_code=303)
    redirect.delete_cookie(key=COOKIE_NAME)
    return redirect


# --- DASHBOARD ROUTES (PROTECTED) ---

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)

    pending = get_pending_orders()
    confirmed = get_confirmed_orders()
    all_orders = get_all_orders()
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "pending": pending,
            "confirmed": confirmed,
            "all_orders": all_orders,
            "now": datetime.now,
        },
    )


@router.get("/dashboard/ventas", response_class=HTMLResponse)
async def sales_report(request: Request, period: str = "today"):
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)

    metrics = get_sales_analytics(period=period)
    return templates.TemplateResponse(
        request=request,
        name="ventas.html",
        context={
            "metrics": metrics,
            "period": period,
            "now": datetime.now,
        },
    )


@router.post("/dashboard/confirm/{order_id}")
async def confirm_order_route(
    request: Request,
    order_id: int,
    pickup_time: str = Form(...),
    print_ticket: str = Form("true"),
):
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)

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
        # Print confirmed ticket with pickup time only if print_ticket is true
        should_print = str(print_ticket).strip().lower() in ("true", "1", "yes", "on")
        if should_print:
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

        # Reset the user's bot session so they can start a new order next time they message
        reset_session(order.customer.phone)

    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/dashboard/print/{order_id}")
async def print_order_route(request: Request, order_id: int):
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)

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
async def test_printer_route(request: Request):
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)

    send_test_ticket_to_printer()
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/dashboard/cancel/{order_id}")
async def cancel_order_route(request: Request, order_id: int):
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)

    order = cancel_order(order_id)
    if order and order.customer:
        await send_order_cancellation(
            to=order.customer.phone,
            order_id=order.id,
        )
        reset_session(order.customer.phone)
    return RedirectResponse(url="/dashboard", status_code=303)
