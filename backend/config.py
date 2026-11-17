from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_WEAK_SECRETS = {"", "dev-secret-change-me", "replace-with-a-random-secret"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "dev"  # đặt "prod" để bật kiểm tra cấu hình an toàn
    DATABASE_URL: str = "mysql+pymysql://root:@localhost:3306/recruitment_ai?charset=utf8mb4"
    JWT_SECRET: str = "dev-secret-change-me"
    JWT_EXPIRE_MINUTES: int = 720
    CORS_ORIGINS: str = "http://localhost:8501,http://127.0.0.1:8501"

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    LLM_CONCURRENCY: int = 4

    MAX_COMPARE_JOBS: int = 5
    MAX_ACTIVE_APPLICATIONS: int = 20

    @model_validator(mode="after")
    def _check_secret(self):
        if self.APP_ENV.lower() == "prod" and self.JWT_SECRET in _WEAK_SECRETS:
            raise ValueError("JWT_SECRET đang dùng giá trị mặc định; hãy đặt chuỗi bí mật ngẫu nhiên khi APP_ENV=prod.")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
