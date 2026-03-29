import os
import pytest
from secmap.config import (
    load_config,
    DEFAULT_CONFIG,
    SECMapConfig,
    validate_config,
)


def test_default_config_validates():
    cfg = validate_config(DEFAULT_CONFIG)
    assert cfg.max_retries > 0


def test_env_override(monkeypatch):
    monkeypatch.setenv("SECMAP_MAX_RETRIES", "7")
    cfg = load_config()
    assert cfg.max_retries == 7


def test_cli_override():
    cfg = load_config(max_depth=3)
    assert cfg.max_depth == 3


def test_cli_overrides_take_precedence(monkeypatch):
    monkeypatch.setenv("SECMAP_MAX_DEPTH", "1")
    cfg = load_config(max_depth=5)
    assert cfg.max_depth == 5


def test_invalid_log_level():
    with pytest.raises(ValueError):
        validate_config(SECMapConfig(log_level="INVALID"))


def test_invalid_numeric():
    with pytest.raises(ValueError):
        validate_config(SECMapConfig(max_retries=0))
