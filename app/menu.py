from dataclasses import dataclass, field


@dataclass
class Product:
    name: str
    price: float
    category: str
    description: str = ""


@dataclass
class Category:
    name: str
    emoji: str
    products: list[Product] = field(default_factory=list)


MENU: list[Category] = [
    Category("Hamburguesas", "🍔", [
        Product("Sencilla", 50, "Hamburguesas",
            "Milanesa, jamón, queso amarillo, lechuga, jitomate y aderezos"),
        Product("Especial", 75, "Hamburguesas",
            "Sencilla + tocino, queso asadero, champiñones y aguacate"),
        Product("Hawaiana", 75, "Hamburguesas",
            "Sencilla + tocino, queso amarillo, queso asadero, piña y aguacate"),
        Product("Mixta", 85, "Hamburguesas",
            "Sencilla + piña, champiñones, tocino y aguacate"),
        Product("Imperial", 100, "Hamburguesas",
            "Sencilla + doble carne, tocino, champiñones, piña, aguacate, doble jamón, quesos y salchichón"),
    ]),
    Category("Sincronizadas", "🥙", [
        Product("Sencillas", 60, "Sincronizadas",
            "Doble tortilla de harina con jamón, queso asadero, queso amarillo y ensalada de lechuga"),
        Product("Especiales", 75, "Sincronizadas",
            "Sencillas + bistec y aguacate"),
        Product("619", 100, "Sincronizadas",
            "Sencillas + tocino, champiñones, bistec, salchicha, piña y aguacate"),
    ]),
    Category("Hotdogs", "🌭", [
        Product("Sencillo", 25, "Hotdogs",
            "Salchicha, jitomate, cebolla, tocino y aderezos"),
        Product("Especiales", 30, "Hotdogs",
            "Sencillo + queso asadero"),
        Product("Hawaiano", 45, "Hotdogs",
            "Sencillo + piña"),
        Product("Endiablado", 45, "Hotdogs",
            "Sencillo + salsa y chile habanero (muy picoso)"),
    ]),
    Category("Tacos", "🌮", [
        Product("Bistec", 15, "Tacos", ""),
        Product("Barbacoa", 16, "Tacos", ""),
        Product("Chorizo", 13, "Tacos", ""),
        Product("Combinado", 15, "Tacos",
            "Bistec con chorizo"),
    ]),
    Category("Gringas", "🌮", [
        Product("Sencilla", 28, "Gringas",
            "Guisos a elegir: Bistec, Barbacoa, Chorizo o Combinado"),
        Product("Doble", 43, "Gringas",
            "Guisos a elegir: Bistec, Barbacoa, Chorizo o Combinado"),
    ]),
    Category("Tortas", "🥖", [
        Product("Torta de lomo", 40, "Tortas",
            "Lomo, queso, aguacate, jitomate, cebolla y chile"),
        Product("Torta cubana", 45, "Tortas",
            "Doble jamón, lomo, aguacate, jitomate y cebolla"),
        Product("Torta especial", 75, "Tortas",
            "Doble jamón, lomo, tocino, salchicha, piña y aguacate"),
        Product("Torta hawaiana", 45, "Tortas",
            "Lomo, piña, aguacate, queso, jitomate y chile"),
        Product("Torta de bistec", 35, "Tortas", ""),
        Product("Torta de barbacoa", 38, "Tortas", ""),
        Product("Torta combinada", 35, "Tortas",
            "Bistec con chorizo"),
        Product("Torta de bistec con queso", 40, "Tortas", ""),
    ]),
]


def find_product(name: str) -> Product | None:
    for cat in MENU:
        for p in cat.products:
            if p.name.lower() == name.lower():
                return p
    return None


def format_menu_text() -> str:
    lines = [f"📋 *MENÚ COMPLETO*\n"]
    for cat in MENU:
        lines.append(f"\n{cat.emoji} *{cat.name}*")
        for p in cat.products:
            lines.append(f"   • {p.name} - ${p.price}")
    return "\n".join(lines)


def format_category_text(category_name: str) -> str | None:
    for cat in MENU:
        if cat.name.lower() == category_name.lower():
            lines = [f"{cat.emoji} *{cat.name}*\n"]
            for i, p in enumerate(cat.products, 1):
                lines.append(f"{i}️⃣ {p.name} - *${p.price}*")
                if p.description:
                    lines.append(f"   _{p.description}_")
            lines.append(f"\nResponde el *número* del producto que deseas:")
            return "\n".join(lines)
    return None


def format_product_detail(product: Product) -> str:
    detail = f"*{product.name}* — *${product.price}*"
    if product.description:
        detail += f"\n📝 {product.description}"
    return detail


def get_category_names() -> list[str]:
    return [c.name for c in MENU]


def get_products_by_category(category_name: str) -> list[Product]:
    for cat in MENU:
        if cat.name.lower() == category_name.lower():
            return cat.products
    return []


def get_category_emoji(category_name: str) -> str:
    for cat in MENU:
        if cat.name.lower() == category_name.lower():
            return cat.emoji
    return "📋"
