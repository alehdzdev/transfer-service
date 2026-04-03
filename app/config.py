from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "mysql+pymysql://app:apppass@localhost:3306/transfers"

    model_config = {"env_prefix": ""}


settings = Settings()
