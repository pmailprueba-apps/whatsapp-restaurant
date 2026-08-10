# Correcciones y Documentación de Estado Funcional — Bot WhatsApp Restaurant
**Fecha de Verificación:** 06 de Agosto, 2026  
**Estado:** 🟢 Funcional & Operativo en Producción (VPS)

---

## 📋 Resumen Ejecutivo
Se corrigió y validó el flujo de mensajería del Bot de WhatsApp para pedidos de restaurante tras la migración a **FastAPI** y servidor autónomo **WAHA (WhatsApp HTTP API)**.

---

## 🛠️ Correcciones Realizadas

### 1. Desbloqueo de Red y Firewall (UFW) en el VPS
* **Problema:** Los contenedores Docker (como `n8n`) no podían conectarse a la API de Python ejecutada en el puerto `8000/tcp` (`http://172.17.0.1:8000/chat`), generando timeouts.
* **Solución:** Se habilitó explícitamente el puerto en el firewall del VPS:
  ```bash
  ufw allow 8000/tcp
  ```

### 2. Redirección de Flujo en n8n
* **Problema:** Los webhooks de n8n no enviaban correctamente la carga de datos al bot en FastAPI.
* **Solución:** Se ejecutó el script de inyección `update_n8n_code.py`, configurando la regla en n8n para redirigir todo mensaje entrante a `http://172.17.0.1:8000/chat`.

### 3. Integración con Endpoint WAHA v3
* **Problema:** Endpoints obsoletos de enviar texto fallaban.
* **Solución:** Se estandarizó el envío de respuestas de texto mediante el endpoint oficial de WAHA:
  ```http
  POST /api/sessions/{session}/messages/send-text
  ```
  Payload enviado:
  ```json
  {
    "chatId": "<numero_telefono>@c.us",
    "text": "<mensaje_respuesta>"
  }
  ```

### 4. Política sobre Proveedor de WhatsApp
* **Regla Definitiva:** Se prohíbe el uso de Meta Cloud API oficial debido a expiración recurrente de tokens y limitaciones de infraestructura. Toda comunicación se realiza a través de **WAHA (Baileys / Web API local)**.

---

## ✅ Verificación de Flujo End-to-End Realizada
Se simuló un mensaje entrante completo:
1. `WhatsApp Entrante` ➔ `WAHA Webhook`
2. `WAHA` ➔ `n8n Workflow`
3. `n8n Workflow` ➔ `FastAPI (server.py:8000/chat)`
4. `FastAPI` ➔ `Bot Logic (bot-remote.py)`
5. `Bot Logic` ➔ `WAHA API (/api/sessions/default/messages/send-text)` ➔ `WhatsApp Saliente`

**Resultado:** Respuesta HTTP 200 OK y entrega confirmada de mensaje.
