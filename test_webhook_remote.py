import httpx
import json
import asyncio

async def test_webhook():
    url = "https://whatsapp-restaurant-iox6.onrender.com/webhook/whatsapp"
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "1074350692438267",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": "1074350692438267"
                            },
                            "contacts": [
                                {
                                    "profile": {
                                        "name": "Test User"
                                    },
                                    "wa_id": "524441234567"
                                }
                            ],
                            "messages": [
                                {
                                    "from": "524441234567",
                                    "id": "wamid.HBgLNTI0NDQ2NTA2Nzkw...",
                                    "timestamp": "1691234567",
                                    "text": {
                                        "body": "Hola"
                                    },
                                    "type": "text"
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    
    print(f"Sending POST request to {url}...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10.0)
            print(f"Status Code: {response.status_code}")
            print(f"Response Body: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_webhook())
