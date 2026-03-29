"""
config.py

Hardened configuration system for SECMap.

Enhancements:
- Immutable config object
- Layered overrides (defaults → env → CLI)
- Full validation
- Logging of override sources
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, replace
from typing import Optional


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Default configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SECMapConfig:
    user_agent: str = "SECMap/1.0"
    max_retries: int = 3
    backoff_seconds: float = 1.5
    request_timeout_seconds: float = 30.0
    cache_dir: str = "./cache"
    log_level: str = "INFO"
    max_depth: int = 10          # supports up to 10-layer BOI lineage chains
    max_filings_per_cik: int = 20


DEFAULT_CONFIG = SECMapConfig()


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_positive_int(name: str, value: int):
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")


def _validate_max_depth(value: int):
    if value <= 0:
        raise ValueError(f"max_depth must be positive, got {value}")
    if value > 10:
        raise ValueError(f"max_depth cannot exceed 10 (got {value}); deeper chains are not supported by SEC filing structure")


def _validate_positive_float(name: str, value: float):
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")


def _validate_log_level(level: str):
    valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if level.upper() not in valid:
        raise ValueError(f"Invalid log level: {level}")


def validate_config(cfg: SECMapConfig) -> SECMapConfig:
    _validate_positive_int("max_retries", cfg.max_retries)
    _validate_positive_float("backoff_seconds", cfg.backoff_seconds)
    _validate_positive_float("request_timeout_seconds", cfg.request_timeout_seconds)
    _validate_max_depth(cfg.max_depth)
    _validate_positive_int("max_filings_per_cik", cfg.max_filings_per_cik)
    _validate_log_level(cfg.log_level)
    return cfg


# ---------------------------------------------------------------------------
# Environment overrides
# ---------------------------------------------------------------------------

def load_env_overrides(cfg: SECMapConfig) -> SECMapConfig:
    updates = {}

    for field in cfg.__dataclass_fields__:
        env_key = f"SECMAP_{field.upper()}"
        if env_key in os.environ:
            raw = os.environ[env_key]
            logger.info("Config override from environment: %s=%s", env_key, raw)

            # Convert types
            if isinstance(getattr(cfg, field), int):
                updates[field] = int(raw)
            elif isinstance(getattr(cfg, field), float):
                updates[field] = float(raw)
            else:
                updates[field] = raw

    return replace(cfg, **updates) if updates else cfg


# ---------------------------------------------------------------------------
# CLI overrides
# ---------------------------------------------------------------------------

def apply_cli_overrides(cfg: SECMapConfig, **kwargs) -> SECMapConfig:
    updates = {}

    for key, value in kwargs.items():
        if value is None:
            continue
        if hasattr(cfg, key):
            logger.info("Config override from CLI: %s=%s", key, value)
            updates[key] = value

    return replace(cfg, **updates) if updates else cfg


# ---------------------------------------------------------------------------
# Unified loader
# ---------------------------------------------------------------------------

def load_config(**cli_kwargs) -> SECMapConfig:
    cfg = DEFAULT_CONFIG
    cfg = load_env_overrides(cfg)
    cfg = apply_cli_overrides(cfg, **cli_kwargs)
    cfg = validate_config(cfg)
    return cfg
