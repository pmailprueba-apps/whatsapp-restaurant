from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    whatsapp_provider: str = "direct"
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = "mi_verify_token_123"
    whatsapp_business_phone: str = ""
    manychat_api_key: str = ""
    manychat_verify_token: str = ""
    webjs_port: int = 3001
    database_url: str = "sqlite:///data/restaurant.db"
    owner_phone: str = ""
    app_name: str = "Tacos y Hamburguesas El Compa"

    def model_post_init(self, __context):
        self.whatsapp_token = self.whatsapp_token.strip()
        self.owner_phone = self.owner_phone.strip()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
