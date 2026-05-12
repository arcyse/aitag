from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    model_path: str = "./model/distilbert_model"
    confidence_threshold: float = 0.70
    max_token_length: int = 128
    hash_length: int = 8        # hex chars of SHA-256 stored in watermark
    device: str = "auto"        # "auto" | "cpu" | "cuda"

    class Config:
        env_file = ".env"
        env_prefix = "AITAG_"   # e.g. AITAG_MODEL_PATH=...


settings = Settings()
