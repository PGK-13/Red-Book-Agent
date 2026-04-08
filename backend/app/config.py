from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # 应用
    app_env: str = "development"
    app_debug: bool = True
    log_level: str = "INFO"

    # 数据库
    database_url: str = "postgresql+asyncpg://xhs:xhs_dev_password@localhost:5432/xhs_marketing"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # RabbitMQ
    rabbitmq_url: str = "amqp://xhs:xhs_dev_password@localhost:5672/"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    # LLM
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # 加密
    encryption_key: str = ""

    # JWT
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # 小红书
    xhs_webhook_secret: str = ""


settings = Settings()
