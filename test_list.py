import requests

# Test sending a list message via WAHA
url = "http://204.168.235.137:2785/api/sessions/6c3ad97b-babe-4436-b85c-3bbc195f9d7b/messages/send-list"
headers = {
    "X-API-Key": "dev-key-cambiar-en-prod",
    "Content-Type": "application/json"
}
payload = {
    "chatId": "5216141073188@c.us",
    "title": "Menú Restaurante Viky",
    "description": "Selecciona una categoría",
    "buttonText": "Ver Categorías",
    "sections": [
        {
            "title": "Categorías",
            "rows": [
                {
                    "title": "Hamburguesas",
                    "description": "Sencilla, Especial, Hawaiana...",
                    "rowId": "cat_hamburguesas"
                },
                {
                    "title": "Sincronizadas",
                    "description": "Sencillas, Especiales, 619",
                    "rowId": "cat_sincronizadas"
                }
            ]
        }
    ]
}

response = requests.post(url, headers=headers, json=payload)
print(response.status_code)
print(response.text)
