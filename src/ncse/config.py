"""Read the project configuration (config.yaml)."""

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = PROJECT_ROOT / "config.yaml"


def load_config(path: Path = CONFIG_FILE) -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # Turn relative paths into absolute paths inside the project folder.
    cfg["paths"] = {key: PROJECT_ROOT / value for key, value in cfg["paths"].items()}
    return cfg
