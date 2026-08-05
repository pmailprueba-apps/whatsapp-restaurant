# ROADMAP FASE 2: Producción y Escalabilidad del Bot (Restaurante Viky / Fábrica de Bots)

Este documento guarda las directrices y decisiones arquitectónicas tomadas para la "Fase 2" del proyecto, una vez que el cliente haya aceptado la demostración y haya pagado por el servicio de producción.

## 1. Topología del Hardware en el Local (Restaurante)
Para imprimir los tickets de los pedidos en el restaurante sin depender de una computadora local (que el cliente no tiene o no quiere asignar), la solución técnica aprobada es:

* **Impresora Térmica:** Debe ser una impresora con puerto Ethernet (LAN). Se conectará mediante un cable de red RJ45 directamente al módem de internet del restaurante (obteniendo una IP local y abriendo el puerto TCP 9100).
* **Microcontrolador (El Puente):** Se usará una placa **ESP32 (WROOM-32)** en lugar de una Raspberry Pi.
  * **Costo aprox:** $150 MXN (muy inferior a la Raspberry Pi).
  * **Conexión:** Se alimenta con un cargador de celular (5V) y se conecta por **WiFi** al módem del restaurante.
  * **Ventaja crítica:** No tiene sistema operativo que se corrompa en apagones o si desconectan el cable de golpe.
  * **Flujo de impresión:** El ESP32 hace peticiones al Bot (en la nube) y empuja los datos brutos (ESC/POS) a la IP local de la impresora.

## 2. Estrategia de Servidores y Red (De Piloto a Producción)
El mayor reto técnico es que el bot (servidor) y la impresora (ESP32) están en redes físicas distintas, separadas por el CGNAT de los proveedores de internet. La estrategia de migración es la siguiente:

### Fase 1: Demostración Comercial (Costo $0)
* **Dónde corre el bot:** En la PC de desarrollo (Windows, IP local `192.168.100.13`) mediante `PM2` (puertos 3001 para Bot-Service y 3006 para Bridge).
* **El Enlace de Red:** Dado que el ESP32 en el restaurante no puede "entrar" a la PC de desarrollo directamente, se configurará **Cloudflare Tunnel** o **Ngrok** en la PC Windows. Esto expondrá el bot a una URL pública temporal para que el ESP32 consulte los tickets.
* **Objetivo:** Demostrar el funcionamiento completo del sistema de principio a fin sin gastar un peso en infraestructura antes de firmar el proyecto.

### Fase 2: Producción y Escalabilidad (El VPS)
Una vez vendido el proyecto, se elimina la dependencia de la PC de desarrollo de la casa.
* **El Servidor:** Se contratará un **VPS en Hetzner (Modelo CAX11)**. Costo: ~€3.99 al mes, 2 vCPUs, 4GB RAM, 40GB SSD.
* **Migración:** Se mueve la base de datos (PostgreSQL/MySQL) y los procesos PM2 al VPS.
* **Actualización Hardware:** Se le cambia solo una línea de código al ESP32 para que, en lugar de apuntar a la URL de Cloudflare Tunnel de la casa, apunte directamente a la IP/Dominio del VPS.
* **Resultado:** Operatividad garantizada 24/7 sin las inestabilidades ni bloqueos de red de una PC casera.

## 3. Observabilidad, Métricas y Telemetría
Para controlar la salud del bot (para el desarrollador) y entregarle métricas de valor al dueño del restaurante, se desplegarán servicios en contenedores dentro del mismo VPS.

### Para el Dueño del Restaurante (Métricas de Negocio)
* **Objetivo:** Responder a "¿Cuánto vendí hoy?", "¿Cuál fue el producto más popular?", "¿Cuántos carritos se abandonaron?".
* **Herramienta:** **Metabase** (o un módulo de reportería en el Dashboard NestJS).
* **Cómo funciona:** Se conecta directamente a la base de datos donde el Bot-Service guarda las órdenes. Genera gráficas y tableros interactivos para que el dueño los consulte por una web privada, otorgándole valor premium al servicio.

### Para el Desarrollador (Salud Técnica)
* **Lo básico:** Uso de `pm2 monit` y `pm2 logs` directamente en la terminal SSH del VPS.
* **El Vigilante Activo:** **Uptime Kuma**. Estará haciendo peticiones constantes al bot. Si el servicio de Baileys se cuelga o el VPS falla, enviará una alerta automática vía Telegram al desarrollador antes de que el restaurante reporte el fallo.
* **Métricas Avanzadas (Nivel Dios):** Implementación de Prometheus + Grafana si se requiere controlar a detalle el uso de RAM y CPU de múltiples instancias de Baileys conforme se sumen clientes (Multi-tenant).
