from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/syngene_hub"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 1440

    cors_origins: str = "http://localhost:5173"

    # Azure OpenAI (shared AI engine)
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2025-01-01-preview"
    azure_openai_deployment: str = "gpt-5.3-chat"
    default_model: str = "azure-gpt5.3"

    bootstrap_super_admin_email: str = "admin@localhost"
    bootstrap_super_admin_password: str = "changeme"
    bootstrap_super_admin_name: str = "Platform Admin"

    # Fernet key (url-safe base64, 44 chars) OR any passphrase (we'll derive one).
    # If empty, a dev-only key is derived from JWT_SECRET — fine for local, not prod.
    integrations_secret_key: str = ""

    # Paths (used by agents that load example corpora)
    base_dir: Path = Path(__file__).resolve().parent.parent.parent
    data_dir: Path = base_dir / "data"
    examples_dir: Path = data_dir / "examples"
    template_dir: Path = data_dir / "template"
    sop_dir: Path = data_dir / "sop"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
