import os
import asyncio
from dotenv import load_dotenv

# load local .env
load_dotenv("/Users/macbook/Proyectos/28-whatsapp-restaurant/.env")

# import the send_text function
from app.whatsapp import send_text

async def main():
    owner = os.getenv("OWNER_PHONE")
    print(f"Sending test message to {owner}...")
    res = await send_text(owner, "Prueba desde script local")
    print("Response:", res)

if __name__ == "__main__":
    asyncio.run(main())
