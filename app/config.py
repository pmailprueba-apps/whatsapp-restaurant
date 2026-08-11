from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    whatsapp_provider: str = "direct"
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = "mi_verify_token_123"
    whatsapp_app_secret: str = ""
    whatsapp_business_phone: str = ""
    manychat_api_key: str = ""
    manychat_verify_token: str = ""
    webjs_port: int = 3001
    bridge_url: str = "http://localhost:3002"
    openwa_url: str = "http://localhost:2785"
    openwa_api_key: str = "dev-key-cambiar-en-prod"
    openwa_session_id: str = ""
    database_url: str = "sqlite:///data/restaurant.db"
    owner_phone: str = "5214446506790@c.us"
    app_name: str = "Cenaduría Viky Hamburguesas y Tacos"
    dashboard_user: str = "Admin"
    dashboard_password: str = "Amortiguador"
    secret_key: str = "viky_secret_session_key_2026_auth"

    def model_post_init(self, __context):
        self.whatsapp_token = self.whatsapp_token.strip()
        self.owner_phone = self.owner_phone.strip()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
