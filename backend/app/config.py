from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    supabase_url: str
    supabase_jwt_secret: str

    r2_account_id: str = ""
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_bucket_name: str
    r2_endpoint_url: str

    deepseek_api_key: str
    deepseek_base_url: str = "https://api.deepseek.com"

    redis_url: str = "redis://localhost:6379"
    iucn_api_token: str = ""

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
