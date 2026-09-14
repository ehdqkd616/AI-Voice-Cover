from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://app:app_pass@localhost:5433/ai_voice_cover"
    redis_url: str = "redis://localhost:6380/0"

    s3_endpoint: str = "http://localhost:9010"
    s3_public_endpoint: str = "http://localhost:9010"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "ai-voice-cover-media"
    s3_region: str = "us-east-1"

    cors_origins: str = "http://localhost:3010"

    max_upload_mb: int = 200
    max_upload_duration_sec: int = 900
    max_youtube_duration_sec: int = 900
    anon_daily_download_limit: int = 100
    anon_daily_separate_limit: int = 50
    media_ttl_hours: int = 8760

    proxy_url: str = ""
    cookie_path: str = ""

    demucs_device: str = "cpu"
    demucs_fast_model: str = "htdemucs"
    demucs_hq_model: str = "htdemucs_ft"

    # Local named-volume directories the RVC convert worker resolves voice
    # model files from by filename (see services/workers/convert/engine.py).
    rvc_weight_root: str = "/srv/models/weights"
    rvc_index_root: str = "/srv/models/indices"
    rvc_default_f0_method: str = "rmvpe"
    rvc_default_index_rate: float = 0.75
    rvc_default_protect: float = 0.33
    rvc_default_rms_mix_rate: float = 0.25

    mix_default_output_format: str = "mp3-320"
    mix_default_vocal_gain_db: float = 0.0

    # Bootstrapped as an approved admin user on API startup if set and not already present.
    admin_email: str = ""
    admin_password: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
