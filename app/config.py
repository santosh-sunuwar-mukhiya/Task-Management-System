from pydantic_settings import BaseSettings, SettingsConfigDict

_base_config = SettingsConfigDict(
    env_file="./.env",
    env_ignore_empty=True,
    extra="ignore",
)

class Setting(BaseSettings):
    POSTGRES_SERVER: str
    POSTGRES_PORT: int
    POSTGRES_USERNAME:str
    POSTGRES_PASSWORD:str
    POSTGRES_DB: str

    model_config = _base_config

    @property
    # postgres_url = "postgresql+asyncpg://username:password@hostname:port/db_name"
    def POSTGRES_URL(self):
        return f"postgresql+asyncpg://{self.POSTGRES_USERNAME}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

class SecuritySettings(BaseSettings):
    JWT_SECRET: str
    JWT_ALGORITHM: str

    model_config = _base_config

db_settings = Setting()
security_settings = SecuritySettings()

print(db_settings.POSTGRES_URL)
print(db_settings.POSTGRES_SERVER)