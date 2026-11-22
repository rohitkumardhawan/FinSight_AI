import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True, extra="ignore")

    PROJECT_NAME: str = "FinSight AI Backend"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    PORT: int = int(os.getenv("BACKEND_PORT", 8000))
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    FRONTEND_ORIGIN: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
    ADMIN_API_KEY: str = os.getenv("ADMIN_API_KEY", "")
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
    SEC_USER_AGENT: str = os.getenv("SEC_USER_AGENT", "FinSightAI research@finsight.local")

    @property
    def allowed_origins_list(self) -> list[str]:
        """Returns normalized list of allowed CORS origins based on environment."""
        origins = [o.strip() for o in self.FRONTEND_ORIGIN.split(",") if o.strip()]
        if self.ENVIRONMENT.lower() != "production":
            for local_origin in ["http://localhost:3000", "http://127.0.0.1:3000"]:
                if local_origin not in origins:
                    origins.append(local_origin)
        return origins

    # Neon PostgreSQL Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    DATABASE_URL_UNPOOLED: str = os.getenv("DATABASE_URL_UNPOOLED", "")
    NEON_BRANCH: str = os.getenv("NEON_BRANCH", "production")
    NEON_BRANCH_ID: str = os.getenv("NEON_BRANCH_ID", "")

    def get_sqlalchemy_database_url(self, unpooled: bool = False) -> str:
        """
        Returns clean connection string formatted for SQLAlchemy with psycopg3.
        Neon provides postgresql:// which needs postgresql+psycopg:// for Psycopg 3.
        """
        raw_url = self.DATABASE_URL_UNPOOLED if (unpooled and self.DATABASE_URL_UNPOOLED) else self.DATABASE_URL
        url = raw_url.strip('"\' ')
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        return url

settings = Settings()
