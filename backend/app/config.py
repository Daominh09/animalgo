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

    # Redis: set EITHER redis_url (Upstash / local docker) OR the discrete
    # host/port/username/password fields (Redis Cloud / redislabs gives these).
    # redis_url wins if set; otherwise redis_dsn assembles a URL from the parts.
    redis_url: str = ""
    redis_host: str = ""
    redis_port: str = "6379"
    redis_username: str = ""
    redis_password: str = ""

    model_config = SettingsConfigDict(env_file=".env")

    @property
    def redis_dsn(self) -> str:
        if self.redis_url:
            return self.redis_url
        if self.redis_host:
            auth = f"{self.redis_username or 'default'}:{self.redis_password}@" if self.redis_password else ""
            return f"redis://{auth}{self.redis_host}:{self.redis_port}"
        return "redis://localhost:6379"


settings = Settings()
