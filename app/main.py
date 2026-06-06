from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.dashboard import router as dashboard_router
from app.models import init_db, init_engine
from app.webhook import router as webhook_router

app = FastAPI(title="WhatsApp Restaurant Bot")

app.include_router(webhook_router)
app.include_router(dashboard_router)

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.globals["now"] = datetime.now


@app.on_event("startup")
def startup():
    init_engine(settings.database_url)
    init_db()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "pending": [],
            "confirmed": [],
            "all_orders": [],
        },
    )


@app.get("/privacy", response_class=HTMLResponse)
async def privacy():
    return """<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Política de Privacidad - Restaurante Viky</title>
<style>body{font-family:-apple-system,sans-serif;max-width:800px;margin:0 auto;padding:20px;color:#333;line-height:1.6}h1{color:#128C7E}</style></head>
<body>
<h1>Política de Privacidad</h1>
<p><strong>Restaurante Viky</strong></p>
<p>Esta aplicación recolecta únicamente la información necesaria para procesar pedidos:</p>
<ul><li>Número de teléfono</li><li>Nombre del cliente</li><li>Detalles del pedido</li></ul>
<p>Los datos se usan exclusivamente para la gestión de pedidos y no se comparten con terceros.</p>
<p>Para solicitar la eliminación de tus datos, contáctanos al WhatsApp del negocio.</p>
<p><em>Última actualización: Junio 2026</em></p>
</body>
</html>"""


@app.get("/privacy-policy", response_class=HTMLResponse)
async def privacy_policy():
    return await privacy()
