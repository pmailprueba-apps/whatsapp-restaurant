from fastapi import FastAPI, Request
import importlib
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
bot_remote = importlib.import_module("bot-remote")

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    bot_remote.init_sessions()

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    phone = data.get("phone")
    text = data.get("text")
    if not phone or text is None:
        return {"status": "error", "message": "Missing phone or text"}
    
    state, summary = await bot_remote.handle_message(phone, text)
    return {"status": "ok", "state": state, "summary": summary}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
