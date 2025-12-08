"""Configuration management using Pydantic settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Required settings
    github_webhook_secret: str = Field(
        ...,
        description="Secret for validating GitHub webhook signatures",
    )
    github_token: str = Field(
        ...,
        description="GitHub token with repo and workflow permissions",
    )
    anthropic_api_key: str = Field(
        ...,
        description="Anthropic API key for Claude",
    )
    slack_webhook_url: str = Field(
        ...,
        description="Slack incoming webhook URL for notifications",
    )

    # Optional settings
    allowed_repos: list[str] = Field(
        default_factory=list,
        description="Whitelist of repos (owner/repo format). Empty means all repos allowed.",
    )
    max_context_files: int = Field(
        default=20,
        description="Maximum number of files to include in Claude context",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )

    # Server settings
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")

    # Claude settings
    claude_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Claude model to use for analysis",
    )
    max_log_size: int = Field(
        default=50000,
        description="Maximum log size in characters before truncation",
    )

    def is_repo_allowed(self, repo_full_name: str) -> bool:
        """Check if a repository is in the allowed list."""
        if not self.allowed_repos:
            return True
        return repo_full_name in self.allowed_repos


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()  # type: ignore[call-arg]
