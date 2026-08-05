# Actualización 2.0: Bot Inteligente para Restaurante Viky

## Nueva Arquitectura (Julio 2026)

Se ha migrado el bot de respuestas automáticas estáticas a un sistema inteligente completo basado en **n8n**, **OpenWA** y **Supabase**, alojado en un servidor propio en la nube de Hetzner.

### 1. Servidor (Hetzner)
- **Nombre:** fabrica-bots
- **IP Pública:** `204.168.235.137`
- **Dominio Dinámico:** `restauranteviky.duckdns.org`
- **Proxy/Seguridad:** Caddy (gestiona certificados SSL gratuitos mediante Let's Encrypt para el dominio).

### 2. Motor de Automatización (n8n)
- **URL de Acceso:** https://restauranteviky.duckdns.org
- **Despliegue:** Contenedor Docker (`n8n-duckdns-server`).
- **Red interna:** Conectado a `whatsapp-restaurant_default` para comunicarse con Caddy y otras herramientas.
- **Webhook de Pruebas (Oído del bot):** `https://restauranteviky.duckdns.org/webhook-test/whatsapp-entrada`

### 3. Base de Datos (Supabase)
- **Modo:** Supabase Cloud (Plan Gratis)
- **Proyecto:** `Restaurante Viky Bot`
- **Contraseña:** `Amortiguador`
- **Uso:** Almacenar historial de conversaciones, gestionar inventario de platillos y reconocer clientes frecuentes para darle memoria a la Inteligencia Artificial.

### 4. Conexión de WhatsApp (OpenWA)
- **Estado:** El antiguo bot de Python (`whatsapp-bot`) ha sido apagado permanentemente.
- **Flujo:** OpenWA recibe los mensajes de WhatsApp y los dispara directamente vía Webhook al flujo de n8n para que la Inteligencia Artificial procese la intención del usuario.

## Pasos pendientes
1. Configurar el Webhook final en la instancia de OpenWA hacia n8n.
2. Añadir nodo de OpenAI/ChatGPT en n8n con el Prompt del restaurante.
3. Conectar el nodo de respuesta (HTTP Request) para enviar texto de vuelta a OpenWA.
