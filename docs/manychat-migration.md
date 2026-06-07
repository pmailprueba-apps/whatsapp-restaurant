# ManyChat Migration — WhatsApp Restaurant Bot

## Architecture Overview

El bot usa un **provider abstraction** para enviar mensajes de WhatsApp.
Dos modos: `manychat` y `direct` (ambos usan Meta Graph API para enviar).

```
ManyChat (flows visuales)          Direct (Meta API)
        │                                │
        │ lead_property_updated           │ webhook entrante
        ▼                                ▼
  ┌─────────────────────────────────────────┐
  │       FastAPI Webhook Handler           │
  │  (app/webhook.py)                       │
  └────────────┬────────────────────────────┘
               │
               ▼
  ┌─────────────────────────────────────────┐
  │         Provider Layer                  │
  │  (app/whatsapp_provider.py)             │
  │  Muchos envían por Meta Graph API       │
  │  ManyChat solo para webhooks + IDs      │
  └────────────┬────────────────────────────┘
               │
               ▼
  ┌─────────────────────────────────────────┐
  │      Dashboard (app/dashboard.py)       │
  │    Dueño confirma/cancela pedidos       │
  └─────────────────────────────────────────┘
```

> **Nota importante:** La API de ManyChat para enviar mensajes es **Pro**.
> Este proyecto usa Meta Graph API (gratis) para los mensajes salientes
> desde el dashboard. ManyChat se usa solo para los flows conversacionales
> entrantes y los webhooks. El plan gratis de ManyChat es suficiente.

## Key Changes

### 1. `app/models.py` — Added `manychat_id`
```python
manychat_id = Column(String(50), nullable=True, index=True)
```
ManyChat usa `subscriber_id` interno, no número de teléfono.
Este campo se llena automáticamente cuando ManyChat envía un webhook.

### 2. `app/config.py` — New env vars
- `WHATSAPP_PROVIDER` — `"manychat"` | `"direct"`
- `MANYCHAT_API_KEY` — API key de ManyChat
- `MANYCHAT_VERIFY_TOKEN` — Token de verificación webhook

### 3. `app/whatsapp_provider.py` — NEW
Provider pattern:
- `BaseProvider` — ABC con `send_text()`, `send_order_confirmation()`, `send_order_cancellation()`
- `ManyChatProvider` — usa `api.manychat.com/fb/sending/sendMessage` con `subscriber_id`
- `DirectProvider` — usa `graph.facebook.com/v22.0/.../messages`
- `get_provider()` — factory singleton según `WHATSAPP_PROVIDER`

### 4. `app/whatsapp.py` — Simplified
Delega al provider activo. Ya no tiene lógica de API directamente.

### 5. `app/webhook.py` — Dual handler
- **ManyChat events**: `lead_property_updated` con `custom_field_order_data`
- **Meta webhook**: Legacy support (responde con mensaje de migración)

### 6. `app/bot.py` — Stripped
Se eliminó la máquina de estados. El flow conversacional ahora vive en ManyChat.
Solo quedan `CartItem`, `Session`, `build_order_data()`.

### 7. `app/api_menu.py` — NEW
`GET /api/menu` — Sirve el menú en JSON para que ManyChat lo consuma dinámicamente.

### 8. `app/dashboard.py` — Updated
Usa `send_order_confirmation()` / `send_order_cancellation()` del provider.

## Setup ManyChat

### 1. Crear cuenta
1. Ve a [manychat.com](https://manychat.com) y crea cuenta
2. Plan gratuito: hasta 1,000 contactos
3. Conecta WhatsApp Business API

### 2. Configurar webhook
1. En ManyChat → Settings → Webhooks
2. URL: `https://tu-dominio.onrender.com/webhook/whatsapp`
3. Verify Token: el mismo de `MANYCHAT_VERIFY_TOKEN`

### 3. Crear custom fields
En ManyChat → Custom Fields, crear:
- `order_data` (text) — JSON con items del pedido
- `subscriber_phone` (phone) — número del cliente

### 4. Crear flows
Flujos necesarios en el builder visual:

| Flow | Descripción |
|------|------------|
| Welcome | Saludo + menú principal |
| Show Menu | Muestra categorías (consume GET /api/menu) |
| Select Category | Muestra productos de la categoría |
| Select Product | Pide cantidad + notas |
| Confirm Order | Muestra resumen, botón confirmar |
| Order Placed | Guarda en custom field `order_data` + dispara webhook |

### 5. Template message (24h window)
Crear template en ManyChat → WhatsApp Templates:
```
Nombre: order_confirmed
Idioma: Español (México)
Cuerpo: ✅ Pedido #{{order_id}} confirmado.
Recoge a las {{pickup_time}}.
Total: ${{total}}
```

## Data Flow (Order Lifecycle)

```
1. Cliente escribe al WhatsApp
2. ManyChat Welcome Flow se activa
3. Cliente navega menú → selecciona productos → confirma
4. ManyChat guarda order_data como JSON en custom field
5. ManyChat dispara lead_property_updated → webhook
6. FastAPI recibe el evento, guarda Order en DB
7. FastAPI notifica al dueño
8. Dueño confirma desde /dashboard
9. FastAPI envía confirmación al cliente vía ManyChat API
```

## Rollback

Para volver al modo directo (Meta API):
1. Cambiar `WHATSAPP_PROVIDER=direct` en `.env`
2. Configurar `WHATSAPP_TOKEN` y `WHATSAPP_PHONE_NUMBER_ID`
3. Desconectar ManyChat de WhatsApp Business
4. Conectar Meta directamente
