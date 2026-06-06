from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = "mi_verify_token_123"
    whatsapp_business_phone: str = ""
    database_url: str = "sqlite:///data/restaurant.db"
    owner_phone: str = ""
    app_name: str = "Tacos y Hamburguesas El Compa"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
