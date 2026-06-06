from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.dashboard import router as dashboard_router
from app.models import init_db, init_engine
from app.webhook import router as webhook_router

app = FastAPI(title="WhatsApp Restaurant Bot")

app.include_router(webhook_router)
app.include_router(dashboard_router)

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.globals["now"] = datetime.now


@app.on_event("startup")
def startup():
    init_engine(settings.database_url)
    init_db()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "pending": [],
            "confirmed": [],
            "all_orders": [],
        },
    )
