from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "mysql+pymysql://app:apppass@localhost:3306/transfers"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_pre_ping: bool = True

    # App
    app_name: str = "Transfer Availability & Booking Service"
    log_level: str = "INFO"
    debug: bool = False

    model_config = {"env_prefix": ""}


settings = Settings()
