from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "mysql+pymysql://root:@localhost:3306/recruitment_ai?charset=utf8mb4"
    JWT_SECRET: str = "dev-secret-change-me"
    JWT_EXPIRE_MINUTES: int = 720

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    LLM_CONCURRENCY: int = 4

    MAX_COMPARE_JOBS: int = 5
    MAX_ACTIVE_APPLICATIONS: int = 20


settings = Settings()
