from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    supabase_url: str

    r2_account_id: str = ""
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_bucket_name: str
    r2_endpoint_url: str

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # OpenRouter — vision fallback used when Gemini has no key or its call fails.
    # Field name matches the OPEN_ROUTER_API_KEY spelling already in .env.
    open_router_api_key: str = ""
    open_router_model: str = "google/gemma-4-31b-it:free"
    open_router_base_url: str = "https://openrouter.ai/api/v1"

    # Redis: set EITHER redis_url (Upstash / local docker) OR the discrete
    # host/port/username/password fields (Redis Cloud / redislabs gives these).
    # redis_url wins if set; otherwise redis_dsn assembles a URL from the parts.
    redis_url: str = ""
    redis_host: str = ""
    redis_port: str = "6379"
    redis_username: str = ""
    redis_password: str = ""

    # extra="ignore" so unused/extra keys in .env (e.g. the split REDIS_HOST/
    # REDIS_PORT/REDIS_USERNAME/REDIS_PASSWORD credentials) don't crash startup.
    # The app connects to Redis via REDIS_URL only.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def redis_dsn(self) -> str:
        if self.redis_url:
            return self.redis_url
        if self.redis_host:
            auth = f"{self.redis_username or 'default'}:{self.redis_password}@" if self.redis_password else ""
            return f"redis://{auth}{self.redis_host}:{self.redis_port}"
        return "redis://localhost:6379"


settings = Settings()
