import os
from dataclasses import dataclass
from urllib.parse import urlsplit


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class Config:
    database_url: str
    s3_endpoint: str
    s3_bucket: str
    s3_access_key: str
    s3_secret_key: str
    s3_region: str = "us-east-1"

    @staticmethod
    def database_url_from_env() -> str:
        database_url = os.getenv("DATABASE_URL", "")
        if not database_url.startswith("postgresql+psycopg://") or not urlsplit(database_url).hostname:
            raise ConfigurationError("invalid_database_dialect")
        return database_url

    @classmethod
    def from_env(cls) -> "Config":
        database_url = cls.database_url_from_env()
        keys = ("S3_ENDPOINT", "S3_BUCKET", "S3_ACCESS_KEY", "S3_SECRET_KEY")
        if any(not os.getenv(key) for key in keys):
            raise ConfigurationError("missing_artifact_configuration")
        return cls(database_url, *(os.environ[key] for key in keys), os.getenv("S3_REGION", "us-east-1"))
