"""Tests for configuration management."""

import pytest
from pydantic import ValidationError

from ci_guardian.config import Settings


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch):
    """Test that settings load from environment variables."""
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test123")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")

    settings = Settings()

    assert settings.github_webhook_secret == "test-secret"
    assert settings.github_token == "ghp_test123"
    assert settings.anthropic_api_key == "sk-ant-test123"
    assert settings.slack_webhook_url == "https://hooks.slack.com/test"


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch):
    """Test default values for optional settings."""
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test123")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")

    settings = Settings()

    assert settings.max_context_files == 20
    assert settings.log_level == "INFO"
    assert settings.host == "0.0.0.0"
    assert settings.port == 8000
    assert settings.allowed_repos == []


def test_is_repo_allowed_empty_list(monkeypatch: pytest.MonkeyPatch):
    """Test that empty allowed_repos allows all repos."""
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test123")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")

    settings = Settings()

    assert settings.is_repo_allowed("any/repo") is True
    assert settings.is_repo_allowed("another/repo") is True


def test_is_repo_allowed_with_whitelist(monkeypatch: pytest.MonkeyPatch):
    """Test that allowed_repos whitelist works correctly."""
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test123")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    monkeypatch.setenv("ALLOWED_REPOS", '["owner/repo1", "owner/repo2"]')

    settings = Settings()

    assert settings.is_repo_allowed("owner/repo1") is True
    assert settings.is_repo_allowed("owner/repo2") is True
    assert settings.is_repo_allowed("other/repo") is False


def test_settings_requires_secrets(monkeypatch: pytest.MonkeyPatch):
    """Test that required settings raise errors when missing."""
    # Clear any existing env vars
    for key in ["GITHUB_WEBHOOK_SECRET", "GITHUB_TOKEN", "ANTHROPIC_API_KEY", "SLACK_WEBHOOK_URL"]:
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(ValidationError):
        Settings()
