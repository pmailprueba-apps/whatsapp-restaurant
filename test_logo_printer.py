import os
import sys
import time
import paho.mqtt.client as mqtt

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.printer import build_test_ticket, build_escpos_ticket, send_test_ticket_to_printer
from app.logo_viky import get_logo_bytes

VPS_IP = "204.168.235.137"
TOPIC = "viky/printer/orders"

def test_logo_and_print():
    print("=" * 60)
    print("PRUEBA DE IMPRESIÓN CON LOGO UNIVERSAL (ESC *)")
    print("=" * 60)

    # 1. Validar bytecode del logo
    logo_bytes = get_logo_bytes()
    print(f"1. Logo bytecode verificado: {len(logo_bytes)} bytes generados.")

    # 2. Construir ticket con logo
    ticket_payload = build_test_ticket(include_logo=True)
    print(f"2. Ticket de prueba construido: {len(ticket_payload)} bytes totales.")

    # 3. Escuchar MQTT para verificar entrega
    received = []
    def on_connect(client, userdata, flags, rc, properties=None):
        client.subscribe(TOPIC)
        print(f"[MQTT Listener] Conectado y suscrito a {TOPIC}")

    def on_message(client, userdata, msg):
        print(f"[MQTT Listener] Ticket recibido en broker: {len(msg.payload)} bytes")
        received.append(msg.payload)

    listener = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2 if hasattr(mqtt, "CallbackAPIVersion") else None, client_id="test_logo_listener")
    listener.on_connect = on_connect
    listener.on_message = on_message
    listener.connect(VPS_IP, 1883, 10)
    listener.loop_start()
    time.sleep(1)

    # 4. Enviar a través de la función del sistema
    print("\n3. Publicando ticket de prueba con logo al broker MQTT...")
    success = send_test_ticket_to_printer(broker=VPS_IP, port=1883, include_logo=True)
    time.sleep(2)

    listener.loop_stop()
    listener.disconnect()

    if success and len(received) > 0:
        print("\n✅ ¡ÉXITO! Ticket con logo publicado correctamente al broker MQTT de la VPS.")
        print("La impresora térmica física (conectada al puente ESP32) debería estar imprimiendo el ticket con el logo arriba.")
    else:
        print(f"\n❌ Error al enviar ticket: success={success}, received={len(received)}")

if __name__ == "__main__":
    test_logo_and_print()
