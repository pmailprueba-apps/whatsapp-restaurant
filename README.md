# WhatsApp Restaurant Bot

Sistema de pedidos para restaurante vía WhatsApp. Cliente pide por WhatsApp, dueño confirma desde dashboard con hora de recogida.

## 🚀 Deploy rápido (Render + GitHub)

### 1. Crear repo en GitHub

```bash
cd /Users/macbook/Proyectos/28-whatsapp-restaurant
git init
git add .
git commit -m "init: whatsapp restaurant bot"
gh repo create whatsapp-restaurant --public --source=. --push
```

### 2. Crear servicio en Render

1. Ve a [dashboard.render.com](https://dashboard.render.com) → **New Web Service**
2. Conecta tu GitHub repo
3. Render detecta `render.yaml` automáticamente (Infrastructure as Code)
4. Configura las variables de entorno manualmente:
   - `WHATSAPP_TOKEN` → Token de Meta
   - `WHATSAPP_PHONE_NUMBER_ID` → ID del número
   - `WHATSAPP_VERIFY_TOKEN` → Token de verificación webhook
   - `OWNER_PHONE` → Teléfono del dueño (ej: 5215512345678)
5. Render crea automáticamente la BD PostgreSQL (`whatsapp-db`)
6. Tu app queda en: `https://whatsapp-restaurant.onrender.com`

### 3. Configurar webhook en Meta

1. ngrok no es necesario en producción — Render ya da HTTPS
2. En Meta Developers → WhatsApp → Webhook:
   - **URL**: `https://whatsapp-restaurant.onrender.com/webhook/whatsapp`
   - **Verify Token**: el mismo de `WHATSAPP_VERIFY_TOKEN`

## 💻 Desarrollo local

```bash
source venv/bin/activate
./start.sh
# Abre http://localhost:8000/dashboard
```

Para webhook local (pruebas):

```bash
brew install ngrok
ngrok http 8000
# Copia la URL de ngrok y úsala en Meta Developers
```

## 📋 Flujo

```
WhatsApp                      Dashboard
══════════                    ════════════
Cliente: "Hola"              
Bot: muestra menú            
Cliente: elige productos     
Cliente: confirma pedido     
                  ──────►    Aparece pedido pendiente
                              Dueño: confirma + asigna hora
                  ◄──────    Cliente recibe confirmación
Cliente: recoge y paga       ✓
```

## 🗂️ Estructura

```
app/
├── main.py         # FastAPI
├── config.py       # Config (.env)
├── menu.py         # Catálogo de productos
├── models.py       # SQLAlchemy modelos
├── database.py     # CRUD pedidos
├── bot.py          # Bot conversacional
├── whatsapp.py     # Cliente WhatsApp API
├── webhook.py      # Webhook WhatsApp
├── dashboard.py    # Dashboard del dueño
└── templates/
    └── dashboard.html
```

## 🔧 Personalizar menú

Edita `app/menu.py` — cambia productos, precios y categorías.
