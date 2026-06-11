import os
import tomllib
import tomli_w
from pathlib import Path

CONFIG_DIR  = Path.home() / ".config" / "koda"
CONFIG_FILE = CONFIG_DIR / "config.toml"

DEFAULT_CONFIG = {
    "token": "",
    "player": "mpv",
    "quality": "720",
    "downloads_dir": str(Path.home() / "Downloads" / "Koda"),
}


def _load_dotenv(path: Path) -> dict[str, str]:
    """Parse a .env file into a dict. No external dependencies."""
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            result[key] = value
    return result


def load_config() -> dict:
    """Читает конфиг. Приоритет: env-переменные > .env > config.toml > defaults."""
    config = DEFAULT_CONFIG.copy()

    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "rb") as f:
            config.update(tomllib.load(f))

    dot_env = _load_dotenv(Path.cwd() / ".env")
    if token := dot_env.get("KODIK_TOKEN"):
        config["token"] = token

    if token := os.getenv("KODIK_TOKEN"):
        config["token"] = token

    return config

def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "wb") as f:
        tomli_w.dump(config, f)

def get_token() -> str:
    config = load_config()
    if not config["token"]:
        raise RuntimeError(
            "Токен не найден. Запусти 'koda' и введи токен при первом запуске."
        )
    return config["token"]