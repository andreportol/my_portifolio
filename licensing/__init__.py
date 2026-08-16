import os
from pathlib import Path


APP_NAME = "GestaoOficina"
TOKEN_PREFIX = "GOF1"
BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file(name: str, default: str | None = None) -> str | None:
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        try:
            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:].lstrip()
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip() != name:
                    continue
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                    value = value[1:-1]
                return value
        except OSError:
            pass
    return os.getenv(name, default)


def _read_env(name: str, default: str | None = None) -> str | None:
    return _load_env_file(name, default)


LICENSE_SECRET = (
    _read_env("GESTAO_OFICINA_LICENSE_SECRET")
    or "gestao-oficina-license-secret-v1"
)
