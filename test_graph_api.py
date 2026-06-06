import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv("/Users/macbook/Proyectos/28-whatsapp-restaurant/.env")

async def main():
    token = os.getenv("WHATSAPP_TOKEN")
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    
    url = f"https://graph.facebook.com/v22.0/{phone_id}"
    print(f"Querying node {phone_id}...")
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            url,
            headers={"Authorization": f"Bearer {token}"}
        )
        print("Status:", resp.status_code)
        print("Response:", resp.json())

if __name__ == "__main__":
    asyncio.run(main())
