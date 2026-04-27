import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./reddit.db")


class Settings:
    database_url: str = DATABASE_URL

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")


settings = Settings()
