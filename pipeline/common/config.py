"""Config and path helpers. All thresholds live in config/*.yaml, never in code."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
CACHE_DIR = Path(os.environ.get("SMOULDER_CACHE", ROOT / "cache"))
USER_AGENT = "Smoulder/0.1 (landfill fire record; github.com/smoulder)"


@lru_cache(maxsize=None)
def load(name: str) -> dict:
    with open(CONFIG_DIR / f"{name}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_env() -> None:
    """Load KEY=VALUE pairs from .env into os.environ (without overriding)."""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def firms_key() -> str:
    """FIRMS MAP_KEY: env var locally, SSM SecureString in AWS."""
    load_env()
    key = os.environ.get("FIRMS_MAP_KEY")
    if key:
        return key
    param = os.environ.get("FIRMS_MAP_KEY_PARAM")
    if param:
        import boto3

        ssm = boto3.client("ssm")
        return ssm.get_parameter(Name=param, WithDecryption=True)["Parameter"]["Value"]
    raise RuntimeError("No FIRMS key: set FIRMS_MAP_KEY (local) or FIRMS_MAP_KEY_PARAM (AWS)")
