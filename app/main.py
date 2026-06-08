from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api_menu import router as api_menu_router
from app.bot import init_sessions
from app.config import settings
from app.dashboard import router as dashboard_router
from app.models import init_db, init_engine
from app.webhook import router as webhook_router
from app.simulator import router as simulator_router

app = FastAPI(title="WhatsApp Restaurant Bot")

app.include_router(webhook_router)
app.include_router(simulator_router)
app.include_router(dashboard_router)
app.include_router(api_menu_router)

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.globals["now"] = datetime.now


@app.on_event("startup")
def startup():
    init_engine(settings.database_url)
    init_db()
    init_sessions()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return RedirectResponse(url="/dashboard", status_code=302)


@app.get("/privacy")
async def privacy():
    return HTMLResponse("""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Política de Privacidad - Restaurante Viky</title>
<style>body{font-family:-apple-system,sans-serif;max-width:800px;margin:0 auto;padding:20px;color:#333;line-height:1.6}h1{color:#128C7E}</style></head>
<body>
<h1>Política de Privacidad</h1>
<p><strong>Restaurante Viky</strong></p>
<p>Esta aplicaci&oacute;n recolecta &uacute;nicamente la informaci&oacute;n necesaria para procesar pedidos:</p>
<ul><li>N&uacute;mero de tel&eacute;fono</li><li>Nombre del cliente</li><li>Detalles del pedido</li></ul>
<p>Los datos se usan exclusivamente para la gesti&oacute;n de pedidos y no se comparten con terceros.</p>
<p>Para solicitar la eliminaci&oacute;n de tus datos, cont&aacute;ctanos al WhatsApp del negocio.</p>
<p><em>&Uacute;ltima actualizaci&oacute;n: Junio 2026</em></p>
</body>
</html>""")


@app.get("/privacy-policy")
async def privacy_policy():
    return await privacy()
