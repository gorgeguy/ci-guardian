"""Tests for webhook handler."""

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from ci_guardian.main import create_app


@pytest.fixture
def test_settings(monkeypatch: pytest.MonkeyPatch):
    """Set up test environment variables."""
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test123")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")


@pytest.fixture
def client(test_settings):  # noqa: ARG001
    """Create test client with test settings."""
    # Clear the settings cache
    from ci_guardian.config import get_settings

    get_settings.cache_clear()

    app = create_app()
    return TestClient(app)


def _sign_payload(payload: bytes, secret: str) -> str:
    """Generate GitHub webhook signature."""
    return (
        "sha256="
        + hmac.new(
            secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
    )


def test_health_endpoint(client: TestClient):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_webhook_rejects_invalid_signature(client: TestClient):
    """Test that webhook rejects invalid signatures."""
    payload = {"action": "completed"}
    response = client.post(
        "/webhook/github",
        json=payload,
        headers={
            "X-Hub-Signature-256": "sha256=invalid",
            "X-GitHub-Event": "workflow_run",
        },
    )
    assert response.status_code == 401


def test_webhook_ignores_non_workflow_events(client: TestClient):
    """Test that webhook ignores non-workflow_run events."""
    payload = json.dumps({"action": "opened"}).encode()
    signature = _sign_payload(payload, "test-webhook-secret")

    response = client.post(
        "/webhook/github",
        content=payload,
        headers={
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": "pull_request",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


def test_webhook_ignores_successful_runs(client: TestClient):
    """Test that webhook ignores successful workflow runs."""
    payload = json.dumps(
        {
            "action": "completed",
            "workflow_run": {
                "id": 12345,
                "conclusion": "success",
            },
        }
    ).encode()
    signature = _sign_payload(payload, "test-webhook-secret")

    response = client.post(
        "/webhook/github",
        content=payload,
        headers={
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": "workflow_run",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


def test_webhook_accepts_failure_events(client: TestClient):
    """Test that webhook accepts and queues failure events."""
    payload = json.dumps(
        {
            "action": "completed",
            "workflow_run": {
                "id": 12345,
                "conclusion": "failure",
                "head_branch": "main",
                "head_sha": "abc123",
                "html_url": "https://github.com/owner/repo/actions/runs/12345",
            },
            "repository": {
                "full_name": "owner/repo",
            },
        }
    ).encode()
    signature = _sign_payload(payload, "test-webhook-secret")

    response = client.post(
        "/webhook/github",
        content=payload,
        headers={
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": "workflow_run",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert response.json()["run_id"] == "12345"
