import os
import sys
import time
import paho.mqtt.client as mqtt

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.printer import build_escpos_ticket, build_test_ticket, send_ticket_to_printer, send_test_ticket_to_printer
from app.models import init_engine, init_db, SessionLocal, Order, Customer, OrderItem
from app.database import create_order, get_or_create_customer, confirm_order

VPS_IP = "204.168.235.137"
TOPIC = "viky/printer/orders"

def run_tests():
    print("=" * 60)
    print("PRUEBAS DE INTEGRACIÓN: IMPRESORA TÉRMICA & FLUJO DE PEDIDO")
    print("=" * 60)

    # 1. Configurar listener MQTT en background
    received_payloads = []

    def on_connect(client, userdata, flags, rc, properties=None):
        client.subscribe(TOPIC)
        print(f"[MQTT Listener] Conectado y suscrito a {TOPIC}")

    def on_message(client, userdata, msg):
        print(f"[MQTT Listener] Recibido mensaje en {msg.topic}: {len(msg.payload)} bytes")
        received_payloads.append(msg.payload)

    listener = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2 if hasattr(mqtt, 'CallbackAPIVersion') else None, client_id="test_runner_listener")
    listener.on_connect = on_connect
    listener.on_message = on_message
    listener.connect(VPS_IP, 1883, 10)
    listener.loop_start()
    time.sleep(1)

    # 2. Inicializar DB
    init_engine("sqlite:///data/restaurant.db")
    init_db()

    # 3. Simular cliente y pedido
    print("\n--- PASO 1: Creación de Pedido en DB ---")
    phone = "5214446506790"
    customer = get_or_create_customer(phone, "Alex Ramos (Prueba Impresora)")
    
    sample_items = [
        {
            "product_name": "Hamburguesa Hawaiana",
            "category": "Hamburguesas",
            "quantity": 2,
            "unit_price": 75.0,
            "notes": "Sin cebolla, bien dorada",
            "subtotal": 150.0,
        },
        {
            "product_name": "Sincronizada 619",
            "category": "Sincronizadas",
            "quantity": 1,
            "unit_price": 100.0,
            "notes": "Extra salsa verde",
            "subtotal": 100.0,
        },
        {
            "product_name": "Taco Barbacoa",
            "category": "Tacos",
            "quantity": 4,
            "unit_price": 16.0,
            "notes": "Con cebollita asada",
            "subtotal": 64.0,
        },
    ]
    total = sum(i["subtotal"] for i in sample_items)
    
    order = create_order(customer_id=customer.id, items=sample_items, total=total, notes="Cliente frecuente")
    print(f"✅ Pedido #{order.id} creado con éxito. Total: ${order.total:.0f}")

    # 4. Prueba: Enviar ticket de pedido nuevo (cuando cliente confirma en bot)
    print("\n--- PASO 2: Envío de Ticket de Nuevo Pedido a MQTT ---")
    pub_res = send_ticket_to_printer(
        order_id=order.id,
        customer_name=customer.name,
        phone=customer.phone,
        items=sample_items,
        total=order.total,
        order_notes=order.notes,
        broker=VPS_IP,
        port=1883,
    )
    print(f"Resultado de publicación pedido nuevo: {pub_res}")
    time.sleep(1.5)

    # 5. Prueba: Confirmar pedido desde el local (con hora de recogida)
    print("\n--- PASO 3: Confirmación de Pedido con Hora de Recogida ---")
    confirmed_order = confirm_order(order.id, pickup_time="20:15 hrs")
    print(f"✅ Pedido #{confirmed_order.id} confirmado con hora: {confirmed_order.pickup_time}")

    pub_confirm_res = send_ticket_to_printer(
        order_id=confirmed_order.id,
        customer_name=customer.name,
        phone=customer.phone,
        items=sample_items,
        total=confirmed_order.total,
        pickup_time=confirmed_order.pickup_time,
        order_notes=confirmed_order.notes,
        broker=VPS_IP,
        port=1883,
    )
    print(f"Resultado de publicación confirmación: {pub_confirm_res}")
    time.sleep(1.5)

    # 6. Prueba: Ticket de prueba del sistema
    print("\n--- PASO 4: Envío de Ticket de Prueba Autónomo ---")
    test_pub_res = send_test_ticket_to_printer(broker=VPS_IP, port=1883)
    print(f"Resultado ticket de prueba: {test_pub_res}")
    time.sleep(2)

    # 7. Validar recepción MQTT
    listener.loop_stop()
    listener.disconnect()

    print("\n" + "=" * 60)
    print(f"RESUMEN DE MENSAJES MQTT RECIBIDOS: {len(received_payloads)}/3")
    print("=" * 60)
    for i, payload in enumerate(received_payloads, 1):
        print(f"\n[Ticket #{i}] Tamaño: {len(payload)} bytes")
        print("--- Inicio de Contenido Imprimible ---")
        print(payload.decode("latin-1", "replace"))
        print("--- Fin de Contenido Imprimible ---")

    if len(received_payloads) == 3:
        print("\n🎉 TODAS LAS PRUEBAS DE IMPRESIÓN PASARON EXITOSAMENTE (3/3)")
    else:
        print(f"\n⚠️ Se esperaban 3 mensajes y se recibieron {len(received_payloads)}")

if __name__ == "__main__":
    run_tests()
