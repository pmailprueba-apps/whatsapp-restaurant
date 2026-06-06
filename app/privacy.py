from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

privacy_html = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Política de Privacidad - Restaurante Viky</title>
    <style>
        body { font-family: -apple-system, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; color: #333; line-height: 1.6; }
        h1 { color: #128C7E; }
    </style>
</head>
<body>
    <h1>Política de Privacidad</h1>
    <p><strong>Restaurante Viky</strong></p>
    <p>Esta aplicación de pedidos por WhatsApp recolecta únicamente la información necesaria para procesar pedidos:</p>
    <ul>
        <li>Número de teléfono</li>
        <li>Nombre del cliente</li>
        <li>Detalles del pedido</li>
    </ul>
    <p>Los datos se utilizan exclusivamente para la gestión de pedidos y no se comparten con terceros.</p>
    <p>Para solicitar la eliminación de tus datos, contáctanos al número de WhatsApp del negocio.</p>
    <p><em>Última actualización: Junio 2026</em></p>
</body>
</html>
"""


@router.get("/privacy", response_class=HTMLResponse)
async def privacy():
    return privacy_html


@router.get("/privacy-policy", response_class=HTMLResponse)
async def privacy_policy():
    return privacy_html
