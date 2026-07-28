from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    supabase_url: str

    r2_account_id: str = ""
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_bucket_name: str
    r2_endpoint_url: str

    deepseek_api_key: str
    deepseek_base_url: str = "https://api.deepseek.com"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    redis_url: str = "redis://localhost:6379"
    iucn_api_token: str = ""

    # extra="ignore" so unused/extra keys in .env (e.g. the split REDIS_HOST/
    # REDIS_PORT/REDIS_USERNAME/REDIS_PASSWORD credentials) don't crash startup.
    # The app connects to Redis via REDIS_URL only.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
