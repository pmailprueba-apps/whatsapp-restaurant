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

# Cut commands: Feed lines then cut paper completely
FEED_AND_CUT = ESC + b"d\x05" + b"\n\n\n" + GS + b"V\x00" + b"\n"


def clean_text(text: str) -> str:
    """Sanitizes text to ASCII-compatible string to prevent garbled symbols on ESC/POS thermal printers."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_text.replace("\r", "")


def clean_phone(phone_str: str) -> str:
    """Formats raw WhatsApp numbers (e.g. 5216141073188@c.us) into human-readable phone format."""
    clean = str(phone_str or "").replace("@c.us", "").replace("@s.whatsapp.net", "").strip()
    if clean.startswith("521") and len(clean) == 13:
        return f"+52 ({clean[3:6]}) {clean[6:9]}-{clean[9:]}"
    elif clean.startswith("52") and len(clean) == 12:
        return f"+52 ({clean[2:5]}) {clean[5:8]}-{clean[8:]}"
    elif len(clean) == 10:
        return f"({clean[:3]}) {clean[3:6]}-{clean[6:]}"
    return clean


def format_pickup_time(time_str: str) -> str:
    """Formats pickup time cleanly (e.g. '12' -> '12:00 hrs', '19:30' -> '19:30 hrs')."""
    clean = clean_text(time_str).strip()
    if not clean:
        return ""
    if clean.isdigit() and len(clean) <= 2:
        return f"{int(clean):02d}:00 hrs"
    if not clean.lower().endswith("hrs") and not clean.lower().endswith("pm") and not clean.lower().endswith("am"):
        return f"{clean} hrs"
    return clean


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

    # Clean customer name and phone
    raw_name = clean_text(customer_name).strip()
    phone_clean = clean_phone(phone)
    if not raw_name or "@c.us" in raw_name or raw_name == phone:
        customer_clean = phone_clean
    else:
        customer_clean = raw_name

    notes_clean = clean_text(order_notes).strip()

    b = bytearray()
    b.extend(INIT)
    b.extend(b"\n")  # Top margin

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
    b.extend(f"Tel: {phone_clean}\n".encode("latin-1", "replace"))

    # Pickup time prominently if available
    formatted_time = format_pickup_time(pickup_time)
    if formatted_time:
        b.extend(b"--------------------------------\n")
        b.extend(BOLD_ON + DOUBLE_HEIGHT)
        b.extend(f"HORA RECOGIDA:\n{formatted_time}\n".encode("latin-1", "replace"))
        b.extend(BOLD_OFF + NORMAL_TYPE)

    if notes_clean:
        b.extend(b"--------------------------------\n")
        b.extend(f"Nota General: {notes_clean}\n".encode("latin-1", "replace"))

    b.extend(b"--------------------------------\n")

    # Items Table (32 columns width for standard 58mm/80mm POS)
    b.extend(ALIGN_LEFT)
    b.extend(BOLD_ON)
    b.extend(b"CANT  PRODUCTO             TOTAL\n")
    b.extend(BOLD_OFF)
    b.extend(b"--------------------------------\n")

    for item in items:
        qty = item.get("quantity", 1)
        name = clean_text(item.get("product_name", ""))[:18].upper()
        subtotal = f"${item.get('subtotal', 0):.0f}"

        # 4 chars qty + 2 chars space + 18 chars name + 2 chars space + 6 chars total = 32 chars
        line = f" {qty:2d}x  {name:<18s} {subtotal:>6s}\n"
        b.extend(line.encode("latin-1", "replace"))

        item_notes = clean_text(item.get("notes", "")).strip()
        if item_notes:
            b.extend(f"      * {item_notes}\n".encode("latin-1", "replace"))

    b.extend(b"--------------------------------\n")
    b.extend(ALIGN_CENTER)
    b.extend(BOLD_ON + DOUBLE_HEIGHT)
    b.extend(f"TOTAL: ${total:.0f}\n".encode("latin-1", "replace"))
    b.extend(BOLD_OFF + NORMAL_TYPE)
    b.extend(b"--------------------------------\n")
    b.extend(b"!Gracias por tu compra!\n")
    b.extend(b"Para recoger en local\n")

    # Extra Feed lines to safely pass the cutter blade before cutting
    b.extend(FEED_AND_CUT)

    return bytes(b)


def build_test_ticket() -> bytes:
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    b = bytearray()
    b.extend(INIT)
    b.extend(b"\n")
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
    b.extend(b"  1x  HAMBURGUESA ESP       $75\n")
    b.extend(b"      * Con todo, extra queso\n")
    b.extend(b"  2x  TACO DE BISTEC        $30\n")
    b.extend(b"--------------------------------\n")
    b.extend(ALIGN_CENTER)
    b.extend(BOLD_ON + DOUBLE_HEIGHT)
    b.extend(b"TOTAL: $105\n")
    b.extend(BOLD_OFF + NORMAL_TYPE)
    b.extend(b"--------------------------------\n")
    b.extend(b"!Prueba completada con exito!\n")
    b.extend(b"Corte de papel ajustado OK\n")
    b.extend(FEED_AND_CUT)
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
        print(f"[Printer] Error publishing ticket for Order #{order_id}: {e}")
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
        print(f"[Printer] Error publishing test ticket: {e}")
        return False
