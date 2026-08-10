import os
import unicodedata
from datetime import datetime
import paho.mqtt.publish as publish

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "viky/printer/orders")

# ESC/POS Commands
ESC = b"\x1b"
GS = b"\x1d"

INIT = ESC + b"@"
ALIGN_CENTER = ESC + b"a\x01"
ALIGN_LEFT = ESC + b"a\x00"
ALIGN_RIGHT = ESC + b"a\x02"
DOUBLE_HEIGHT = ESC + b"!\x10"
DOUBLE_WIDTH = ESC + b"!\x20"
DOUBLE_SIZE = ESC + b"!\x30"
BOLD_ON = ESC + b"E\x01"
BOLD_OFF = ESC + b"E\x00"
NORMAL_TYPE = ESC + b"!\x00"
CUT_PAPER = GS + b"V\x00"


def clean_text(text: str) -> str:
    """Sanitizes text to ASCII-compatible string to prevent garbled symbols on ESC/POS thermal printers."""
    if not text:
        return ""
    # Normalize unicode to separate base characters and diacritics
    nfkd = unicodedata.normalize("NFKD", str(text))
    # Filter out diacritic marks and convert to ASCII
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_text


def build_escpos_ticket(
    order_id: int,
    customer_name: str,
    phone: str,
    items: list[dict],
    total: float,
    pickup_time: str = "",
    order_notes: str = "",
) -> bytes:
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    customer_clean = clean_text(customer_name)
    notes_clean = clean_text(order_notes)

    b = bytearray()
    b.extend(INIT)

    # Header
    b.extend(ALIGN_CENTER)
    b.extend(BOLD_ON + DOUBLE_HEIGHT)
    b.extend(b"CENADURIA VIKY\n")
    b.extend(BOLD_OFF + NORMAL_TYPE)
    b.extend(b"Hamburguesas y Tacos\n")
    b.extend(b"Prol. Moctezuma 2140, 3ra Grande 2\n")
    b.extend(b"78143 San Luis Potosi, S.L.P.\n")
    b.extend(b"Tel: 444 650 6790\n")
    b.extend(b"--------------------------------\n")

    # Order Info
    b.extend(BOLD_ON)
    b.extend(f"TICKET DE PEDIDO #{order_id}\n".encode("latin-1", "replace"))
    b.extend(BOLD_OFF)
    b.extend(f"Fecha: {now}\n".encode("latin-1", "replace"))
    b.extend(f"Cliente: {customer_clean}\n".encode("latin-1", "replace"))
    b.extend(f"Tel: {phone}\n".encode("latin-1", "replace"))

    # Pickup time if available
    if pickup_time:
        b.extend(b"--------------------------------\n")
        b.extend(BOLD_ON + DOUBLE_HEIGHT)
        b.extend(f"HORA RECOGIDA: {clean_text(pickup_time)}\n".encode("latin-1", "replace"))
        b.extend(BOLD_OFF + NORMAL_TYPE)

    if notes_clean:
        b.extend(f"Nota Pedido: {notes_clean}\n".encode("latin-1", "replace"))

    b.extend(b"--------------------------------\n")

    # Items
    b.extend(ALIGN_LEFT)
    b.extend(BOLD_ON)
    b.extend(b"CANT PRODUCTO               SUBT\n")
    b.extend(BOLD_OFF)
    b.extend(b"--------------------------------\n")

    for item in items:
        qty = item.get("quantity", 1)
        name = clean_text(item.get("product_name", "")[:20]).upper()
        subtotal = f"${item.get('subtotal', 0):.0f}"

        line = f"{qty:2d}x {name:<20s} {subtotal:>5s}\n"
        b.extend(line.encode("latin-1", "replace"))

        item_notes = clean_text(item.get("notes", ""))
        if item_notes:
            b.extend(f"    * Nota: {item_notes}\n".encode("latin-1", "replace"))

    b.extend(b"--------------------------------\n")
    b.extend(ALIGN_CENTER)
    b.extend(BOLD_ON + DOUBLE_HEIGHT)
    b.extend(f"TOTAL: ${total:.0f}\n".encode("latin-1", "replace"))
    b.extend(BOLD_OFF + NORMAL_TYPE)
    b.extend(b"--------------------------------\n")
    b.extend(b"!Gracias por tu compra!\n")
    b.extend(b"Para recoger en local\n\n\n\n")
    b.extend(CUT_PAPER)

    return bytes(b)


def build_test_ticket() -> bytes:
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    b = bytearray()
    b.extend(INIT)
    b.extend(ALIGN_CENTER)
    b.extend(BOLD_ON + DOUBLE_HEIGHT)
    b.extend(b"CENADURIA VIKY\n")
    b.extend(BOLD_OFF + NORMAL_TYPE)
    b.extend(b"PRUEBA DE IMPRESION POS\n")
    b.extend(b"--------------------------------\n")
    b.extend(BOLD_ON)
    b.extend(b"ESTADO: IMPRESORA CONECTADA\n")
    b.extend(BOLD_OFF)
    b.extend(f"Fecha: {now}\n".encode("latin-1", "replace"))
    b.extend(b"MQTT: viky/printer/orders\n")
    b.extend(b"Puente: ESP32 WiFi -> TCP 9100\n")
    b.extend(b"--------------------------------\n")
    b.extend(ALIGN_LEFT)
    b.extend(b"1x HAMBURGUESA ESPECIAL    $75\n")
    b.extend(b"    * Nota: Con todo, extra queso\n")
    b.extend(b"2x TACO DE BISTEC          $30\n")
    b.extend(b"--------------------------------\n")
    b.extend(ALIGN_CENTER)
    b.extend(BOLD_ON + DOUBLE_HEIGHT)
    b.extend(b"TOTAL: $105\n")
    b.extend(BOLD_OFF + NORMAL_TYPE)
    b.extend(b"--------------------------------\n")
    b.extend(b"!Prueba completada con exito!\n\n\n\n")
    b.extend(CUT_PAPER)
    return bytes(b)


def send_ticket_to_printer(
    order_id: int,
    customer_name: str,
    phone: str,
    items: list[dict],
    total: float,
    pickup_time: str = "",
    order_notes: str = "",
    broker: str = None,
    port: int = None,
) -> bool:
    target_broker = broker or MQTT_BROKER
    target_port = port or MQTT_PORT
    try:
        payload = build_escpos_ticket(
            order_id=order_id,
            customer_name=customer_name,
            phone=phone,
            items=items,
            total=total,
            pickup_time=pickup_time,
            order_notes=order_notes,
        )
        publish.single(
            MQTT_TOPIC,
            payload=payload,
            hostname=target_broker,
            port=target_port,
            qos=1,
        )
        print(f"[Printer] Ticket for Order #{order_id} published to MQTT ({target_broker}:{target_port} -> {MQTT_TOPIC})")
        return True
    except Exception as e:
        print(f"[Printer] Failed to publish ticket to MQTT ({target_broker}:{target_port}): {e}")
        return False


def send_test_ticket_to_printer(broker: str = None, port: int = None) -> bool:
    target_broker = broker or MQTT_BROKER
    target_port = port or MQTT_PORT
    try:
        payload = build_test_ticket()
        publish.single(
            MQTT_TOPIC,
            payload=payload,
            hostname=target_broker,
            port=target_port,
            qos=1,
        )
        print(f"[Printer] Test ticket published to MQTT ({target_broker}:{target_port} -> {MQTT_TOPIC})")
        return True
    except Exception as e:
        print(f"[Printer] Failed to publish test ticket: {e}")
        return False
