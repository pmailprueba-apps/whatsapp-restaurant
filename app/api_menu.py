from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.menu import MENU

router = APIRouter()


@router.get("/api/menu")
async def get_menu():
    data = []
    for cat in MENU:
        products = []
        for p in cat.products:
            products.append({
                "name": p.name,
                "price": p.price,
                "description": p.description,
            })
        data.append({
            "name": cat.name,
            "emoji": cat.emoji,
            "products": products,
        })
    return JSONResponse({"menu": data})
