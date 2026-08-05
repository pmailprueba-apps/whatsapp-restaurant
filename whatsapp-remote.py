from app.whatsapp_provider import get_provider, SimulatorProvider


def _get_provider_for(to: str):
    if to == "SIMULATOR_USER":
        return SimulatorProvider()
    return get_provider()


async def send_text(to: str, text: str) -> dict:
    return await _get_provider_for(to).send_text(to, text)


async def send_order_confirmation(
    to: str, order_id: int, items_text: str, total: float, pickup_time: str
) -> dict:
    return await _get_provider_for(to).send_order_confirmation(
        to, order_id, items_text, total, pickup_time
    )


async def send_order_cancellation(to: str, order_id: int) -> dict:
    return await _get_provider_for(to).send_order_cancellation(to, order_id)


async def send_buttons(to: str, header: str, body: str, buttons: list[dict]) -> dict:
    return await _get_provider_for(to).send_buttons(to, header, body, buttons)


async def send_list(
    to: str, header: str, body: str, button_text: str, sections: list[dict]
) -> dict:
    return await _get_provider_for(to).send_list(to, header, body, button_text, sections)

