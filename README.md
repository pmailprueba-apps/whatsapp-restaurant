# 🍔 Cenaduría Viky — Bot de WhatsApp + Dashboard POS + Impresora Térmica

Sistema integral de pedidos en tiempo real para **Cenaduría Viky (Hamburguesas y Tacos)**.  
El cliente pide interactivamente por WhatsApp, la cocina recibe y gestiona los pedidos en un Dashboard seguro, y los tickets térmicos se imprimen automáticamente vía MQTT hacia un puente ESP32 conectado a una impresora POS-8360 (Kinwodon).

---

## 🌐 Servicios en Producción (VPS Hetzner `204.168.235.137`)

| Componente | URL / Puerto | Descripción |
|---|---|---|
| **Dashboard de Cocina** | `http://204.168.235.137:8000/dashboard` | Gestión de pedidos pendientes, tiempos de entrega y reimpresión |
| **Módulo de Ventas** | `http://204.168.235.137:8000/dashboard/ventas` | Reporte financiero con filtros (Hoy, Semana, Mes, Histórico) y Ranking de platillos |
| **WhatsApp Bot (WAHA)** | `+52 1 444 650 6790` | Motor WhatsApp basado en WAHA Core 24/7 |
| **Broker MQTT** | `204.168.235.137:1883` | Cola de impresión (`viky/printer/orders`) con QoS 1 |
| **Proceso PM2** | `classic_bot` | Proceso gestionado vía `pm2 restart classic_bot` |

---

## 🔐 Seguridad y Acceso al Dashboard

* **Pantalla de Login:** `http://204.168.235.137:8000/login`
* **Usuario:** `Admin`
* **Contraseña:** `Amortiguador`
* **Sesión:** Cookie segura con firma criptográfica HMAC-SHA256 (`viky_session`, 30 días de persistencia).

---

## 🖨️ Arquitectura de Impresión Térmica

```
[Cliente WhatsApp] ──► [WAHA / FastAPI VPS] ──► [MQTT Broker: 1883]
                                                        │
                                                        ▼
[Impresora Kinwodon POS-8360] ◄── [TCP 9100] ◄── [ESP32 Bridge (WiFi)]
```

### Características del Ticket ESC/POS:
* **Margen de avance de corte (`FEED_AND_CUT`):** Avance de 8 líneas (`ESC d 5` + saltos) previo al corte con guillotina (`GS V \x00`), evitando mutilar el pie de página.
* **Formato limpio:** Sanitización ASCII de caracteres especiales y formato telefónico `+52 (614) 107-3188`.
* **Hora destacada:** Doble altura para hora de recogida acordada (`HORA RECOGIDA: 20:30 hrs`).
* **Notas de cocina:** Desglose detallado de ingredientes especiales por platillo.

---

## 🎛️ Acciones de Pedido en Dashboard

* **`✅ Confirmar & Imprimir` (Verde):** Guarda el tiempo de entrega, avisa al cliente por WhatsApp y manda el ticket a la impresora térmica.
* **`✓ Solo Confirmar` (Azul):** Guarda el tiempo de entrega y avisa al cliente por WhatsApp sin mandar a imprimir.
* **`🖨️ Reimprimir Ticket` (Celeste):** Imprime el ticket físico en cualquier momento.
* **`❌ Cancelar` (Rojo):** Cancela el pedido y notifica al cliente.

---

## 📊 Módulo Administrativo de Ventas

Accesible directamente desde la barra superior del Dashboard:
* **Filtros rápidos:** `☀️ Ventas de Hoy`, `📅 Esta Semana`, `🗓️ Este Mes`, `📈 Histórico Total`.
* **Tarjetas de KPI:** Ventas Cobradas ($), Pedidos Completados, Ticket Promedio ($) y Platillo Estrella.
* **Ranking de Platillos:** Clasificación por unidades vendidas e ingresos totales.
* **Detalle de Órdenes:** Tabla completa con desglose de ítems, hora y estados.

---

## 📁 Estructura del Proyecto

```
28-whatsapp-restaurant/
├── app/
│   ├── config.py             # Configuración, credenciales y variables de entorno
│   ├── dashboard.py          # Rutas del Dashboard, Login, Ventas y acciones
│   ├── database.py           # Consultas SQLite, CRUD de pedidos y métricas de ventas
│   ├── models.py             # Modelos SQLAlchemy (Order, OrderItem, Customer)
│   ├── menu.py               # Catálogo de platillos, precios y categorías
│   ├── printer.py            # Generador ESC/POS y publicador MQTT
│   ├── webhook.py            # Receptor de mensajes de WhatsApp
│   ├── whatsapp_provider.py  # Integración WAHA / WhatsApp Web
│   └── templates/
│       ├── dashboard.html    # Vista principal de cocina y pedidos
│       ├── login.html        # Pantalla de inicio de sesión
│       └── ventas.html       # Panel de métricas administrativas
├── server.py                 # Punto de entrada FastAPI unificado
├── Procfile / render.yaml    # Configuración de respaldo Render
└── requirements.txt          # Dependencias (FastAPI, SQLAlchemy, Paho-MQTT, etc.)
```

---

## 🚀 Despliegue en Servidor

Para sincronizar cambios locales al VPS Hetzner:

```bash
scp -r app/ root@204.168.235.137:/root/classic_bot/
scp server.py root@204.168.235.137:/root/classic_bot/
ssh root@204.168.235.137 "pm2 restart classic_bot"
```
