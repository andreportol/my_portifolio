import os
from pathlib import Path

from decouple import Config, RepositoryEnv


APP_NAME = "GestaoOficina"
TOKEN_PREFIX = "GOF1"
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = Config(RepositoryEnv(str(BASE_DIR / ".env"))) if (BASE_DIR / ".env").exists() else None


def _read_env(name: str, default: str | None = None) -> str | None:
    if ENV_FILE is not None:
        try:
            value = ENV_FILE(name)
            if value is not None:
                return value
        except Exception:
            pass
    return os.getenv(name, default)


LICENSE_SECRET = (
    _read_env("GESTAO_OFICINA_LICENSE_SECRET")
    or "gestao-oficina-license-secret-v1"
)
