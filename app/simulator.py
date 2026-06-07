from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import json

from app.bot import (
    BotState,
    build_order_data,
    get_session,
    reset_session,
    handle_message,
)
from app.config import settings
from app.database import create_order, get_or_create_customer
from app.whatsapp import send_text

router = APIRouter()

HTML_CONTENT = r"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Simulador de WhatsApp</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #e5ddd5; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }
        .chat-container { width: 100%; max-width: 400px; height: 100vh; background: #ece5dd; display: flex; flex-direction: column; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        .chat-header { background: #075e54; color: white; padding: 15px; font-size: 18px; font-weight: bold; text-align: center; }
        .chat-messages { flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
        .message { padding: 10px 15px; border-radius: 10px; max-width: 80%; word-wrap: break-word; font-size: 14px; position: relative; }
        .message.bot { background: #fff; align-self: flex-start; border-top-left-radius: 0; }
        .message.user { background: #dcf8c6; align-self: flex-end; border-top-right-radius: 0; }
        .chat-input { display: flex; padding: 10px; background: #f0f0f0; }
        .chat-input input { flex: 1; padding: 10px; border: none; border-radius: 20px; outline: none; font-size: 14px; }
        .chat-input button { background: #128C7E; color: white; border: none; padding: 10px 15px; border-radius: 50%; margin-left: 10px; cursor: pointer; }
        .buttons-container { display: flex; flex-direction: column; gap: 5px; margin-top: 10px; }
        .ws-button { background: #f8f9fa; border: 1px solid #ddd; padding: 8px; border-radius: 5px; cursor: pointer; color: #007bff; text-align: center; font-weight: bold; }
        .ws-button:hover { background: #e2e6ea; }
    </style>
</head>
<body>

<div class="chat-container">
    <div class="chat-header">🍔 Restaurante Bot (Simulador)</div>
    <div class="chat-messages" id="messages"></div>
    <div class="chat-input">
        <input type="text" id="messageInput" placeholder="Escribe un mensaje..." onkeypress="handleKeyPress(event)">
        <button onclick="sendMessage()">➤</button>
    </div>
</div>

<script>
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${wsProtocol}//${window.location.host}/ws/chat`);
    const messagesDiv = document.getElementById("messages");

    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        if (data.type === 'text') {
            appendMessage(data.text, 'bot');
        } else if (data.type === 'buttons') {
            let content = data.body;
            let buttonsHtml = '<div class="buttons-container">';
            data.buttons.forEach(btn => {
                let title = btn.reply.title;
                buttonsHtml += `<button class="ws-button" onclick="sendInteractive('${title}', '${btn.reply.id}')">${title}</button>`;
            });
            buttonsHtml += '</div>';
            appendMessage(content + buttonsHtml, 'bot', true);
        } else if (data.type === 'list') {
            let content = data.body + '<br><br><b>' + data.button_text + '</b>';
            let listHtml = '<div class="buttons-container">';
            data.sections.forEach(sec => {
                listHtml += `<div><i>${sec.title}</i></div>`;
                sec.rows.forEach(row => {
                    let title = row.title;
                    listHtml += `<button class="ws-button" onclick="sendInteractive('${title}', '${row.id}')">${title}</button>`;
                });
            });
            listHtml += '</div>';
            appendMessage(content + listHtml, 'bot', true);
        }
    };

    function appendMessage(text, sender, isHtml = false) {
        const msgDiv = document.createElement("div");
        msgDiv.className = `message ${sender}`;
        
        // Convert *bold* to <b>bold</b> and \n to <br>
        let formatted = text
            .replace(/\\n/g, '<br>')
            .replace(/\n/g, '<br>')
            .replace(/\*(.*?)\*/g, '<b>$1</b>');

        msgDiv.innerHTML = formatted;
        messagesDiv.appendChild(msgDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }

    function sendMessage() {
        const input = document.getElementById("messageInput");
        if (input.value.trim() !== "") {
            appendMessage(input.value, 'user');
            ws.send(JSON.stringify({ type: "text", text: input.value }));
            input.value = "";
        }
    }

    function sendInteractive(title, payload) {
        appendMessage(title, 'user');
        ws.send(JSON.stringify({ type: "interactive", payload: payload, title: title }));
    }

    function handleKeyPress(event) {
        if (event.key === "Enter") {
            sendMessage();
        }
    }

    // Auto-welcome message when page loads
    window.onload = function() {
        setTimeout(() => {
            appendMessage("Envía *Hola* para comenzar a interactuar con el menú.", "bot");
        }, 500);
    }
</script>

</body>
</html>
"""

@router.get("/chat", response_class=HTMLResponse)
async def chat_ui():
    return HTML_CONTENT


@router.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    from app.whatsapp_provider import active_websockets
    active_websockets.append(websocket)
    phone = "SIMULATOR_USER"
    profile_name = "Cliente Simulador"
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            
            text = ""
            if payload["type"] == "text":
                text = payload["text"]
            elif payload["type"] == "interactive":
                text = payload["payload"]
            
            if not text:
                continue

            try:
                state, summary = await handle_message(phone, text)
            except Exception as e:
                print(f"Error handling simulator message: {e}")
                continue

            if state == BotState.ORDER_PLACED and summary:
                try:
                    order_data = build_order_data(phone, profile_name)
                    customer = get_or_create_customer(phone, profile_name)
                    order = create_order(
                        customer_id=customer.id,
                        items=order_data["items"],
                        total=order_data["total"],
                    )

                    order_summary = (
                        f"📋 *PEDIDO # {order.id}*\n\n"
                        + "\n".join(
                            f"   • {i['quantity']}x {i['product_name']} = ${i['subtotal']:.0f}"
                            for i in order_data["items"]
                        )
                        + f"\n\n*Total: ${order_data['total']:.0f}*"
                        + "\n\n⏳ *Pendiente de confirmación*"
                        + "\n\nTe notificaremos cuando el local confirme tu pedido."
                    )
                    await send_text(phone, order_summary)

                    if settings.owner_phone:
                        owner_msg = (
                            f"🛑 *NUEVO PEDIDO # {order.id}*\n\n"
                            + "\n".join(
                                f"• {i['quantity']}x {i['product_name']} (${i['subtotal']:.0f})"
                                for i in order_data["items"]
                            )
                            + f"\n\n*Total: ${order_data['total']:.0f}*"
                            + f"\n👤 Cliente: {profile_name} ({phone})"
                            + f"\n📱 Confirma desde el dashboard"
                        )
                        await send_text(settings.owner_phone, owner_msg)
                except Exception as e:
                    print(f"Error processing simulator order: {e}")
    except WebSocketDisconnect:
        active_websockets.remove(websocket)
