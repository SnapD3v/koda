import os
import tomllib
import tomli_w
from pathlib import Path

CONFIG_DIR  = Path.home() / ".config" / "koda"
CONFIG_FILE = CONFIG_DIR / "config.toml"

DEFAULT_CONFIG = {
    "token":   "",
    "player":  "mpv",
    "quality": "720",  # предпочитаемое качество
    "downloads_dir": str(Path.home() / "Videos" / "Koda"),
}

def load_config() -> dict:
    """Читает конфиг. Env-переменные имеют приоритет."""
    config = DEFAULT_CONFIG.copy()

    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "rb") as f:
            config.update(tomllib.load(f))

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