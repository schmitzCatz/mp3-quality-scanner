from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MP3QS_",
        env_file=".env",
        extra="ignore",
    )

    music_dir: Path = Path("/music")
    output_dir: Path = Path("/data")
    workers: int = 2


settings = Settings()
